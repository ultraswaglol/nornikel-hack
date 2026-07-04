# ui/views/import_view.py
import streamlit as st
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.pipeline.document_loader import document_loader
from src.pipeline.text_splitter import text_splitter
from src.pipeline.entity_extractor import entity_extractor
from src.pipeline.entity_linker import entity_linker
from src.core.yandex_ai import yandex_ai  # Считываем режим отсюда
from src.core.qdrant_client import vector_client
from src.core.neo4j_client import neo4j_client
from src.models.ontology import SecurityLevel, TrustLevel

def map_folder_to_metadata(filepath: str) -> tuple:
    path_lower = filepath.lower()
    security = SecurityLevel.PUBLIC
    trust = TrustLevel.LEVEL_B
    
    if "журналы" in path_lower or "статьи" in path_lower:
        trust = TrustLevel.LEVEL_A
    elif "доклады" in path_lower or "конференций" in path_lower:
        trust = TrustLevel.LEVEL_B
    elif "обзоры" in path_lower:
        trust = TrustLevel.LEVEL_B
        
    return security, trust

def render_folder_navigator():
    if "bulk_folder_path" not in st.session_state or not st.session_state.bulk_folder_path:
        st.session_state.bulk_folder_path = os.path.expanduser("~")

    current_path = st.session_state.bulk_folder_path
    if not os.path.exists(current_path):
        current_path = os.path.expanduser("~")
        st.session_state.bulk_folder_path = current_path

    st.markdown(f"📂 **Выбранный путь:** `{current_path}`")

    try:
        subdirs = [d for d in os.listdir(current_path) if os.path.isdir(os.path.join(current_path, d)) and not d.startswith(".")]
        subdirs.sort()
    except Exception as e:
        st.error(f"Не удалось прочитать папку: {e}")
        subdirs = []

    options = ["-- Выберите папку для перехода ниже --"]
    if current_path != os.path.abspath(os.sep):
        options.append("⬅️ На уровень вверх (..)")
    options.extend(subdirs)

    selected_item = st.selectbox("Навигация по папкам компьютера (нажимайте для перехода):", options, key="folder_nav_select")

    if selected_item == "⬅️ На уровень вверх (..)":
        parent_dir = os.path.dirname(current_path)
        st.session_state.bulk_folder_path = parent_dir
        st.rerun()
    elif selected_item != "-- Выберите папку для перехода ниже --":
        new_path = os.path.join(current_path, selected_item)
        st.session_state.bulk_folder_path = new_path
        st.rerun()

def process_and_save_chunk(chunk: dict, doc_metadata: dict, security_level: SecurityLevel):
    try:
        vector = yandex_ai.get_embedding(chunk["text"], is_query=False)
        vector_client.save_chunk(
            text_chunk=chunk["text"],
            vector=vector,
            metadata={
                "title": doc_metadata["title"],
                "security_level": security_level.value,
                "year": doc_metadata["year"]
            }
        )
        extracted_graph = entity_extractor.extract_from_chunk(chunk["text"], doc_metadata)
        normalized_graph = entity_linker.normalize_graph(extracted_graph)
        neo4j_client.save_graph(normalized_graph)
    except Exception as e:
        print(f"Ошибка при параллельной обработке чанка: {e}")

def render_import_view():
    st.subheader("📥 Управление импортом R&D документов")
    
    if "bulk_folder_path" not in st.session_state:
        st.session_state.bulk_folder_path = os.path.expanduser("~")
        
    import_mode = st.radio(
        "Выберите режим импорта знаний:",
        ["Импорт единичного документа через браузер", "Пакетное сканирование локальной папки на сервере (для больших архивов)"],
        horizontal=True
    )
    
    # ФИКС ПОТОКОВ: Считываем параметры из активного синглтона ИИ
    if yandex_ai.mock_mode:
        max_workers = 12
    elif yandex_ai.ai_mode == "LOCAL":
        max_workers = 5
    else:
        max_workers = 3
        
    if import_mode == "Импорт единичного документа через браузер":
        col1, col2 = st.columns(2)
        with col1:
            security_level = st.selectbox("Класс конфиденциальности документа:", list(SecurityLevel))
        with col2:
            trust_level = st.selectbox("Уровень достоверности источника:", list(TrustLevel))
            
        uploaded_file = st.file_uploader("Выберите PDF-файл для анализа (до 200 МБ):", type=["pdf"])
        
        if uploaded_file is not None:
            temp_dir = "temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, uploaded_file.name)
            
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            if st.button("Запустить анализ документа и импорт в Базу Знаний", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    status_text.text("1/4 Чтение текста и метаданных PDF...")
                    raw_text, doc_metadata = document_loader.load_pdf(
                        file_path, 
                        security_level=security_level, 
                        trust_level=trust_level
                    )
                    progress_bar.progress(25)
                    
                    status_text.text("2/4 Сегментация текста на чанки...")
                    chunks = text_splitter.split_text(raw_text, doc_metadata)
                    progress_bar.progress(50)
                    
                    status_text.text(f"3/4 Индексация текстовых чанков в параллельном режиме ({max_workers} потоков)...")
                    total_chunks = len(chunks)
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = [executor.submit(process_and_save_chunk, chunk, doc_metadata, security_level) for chunk in chunks]
                        for idx, future in enumerate(as_completed(futures)):
                            progress_bar.progress(50 + int((idx + 1) / total_chunks * 50))
                    
                    progress_bar.progress(100)
                    status_text.text("Импорт успешно завершен!")
                    st.success(f"Документ '{doc_metadata['title']}' успешно проиндексирован. Текст нарезан на {total_chunks} чанков и сохранен в граф.")
                    
                except Exception as e:
                    st.error(f"Произошла ошибка в пайплайне: {e}")
                finally:
                    if os.path.exists(file_path):
                        os.remove(file_path)

    else:
        st.info("💡 Этот режим предназначен для быстрой индексации больших локальных архивов напрямую с вашего SSD-диска.")
        
        render_folder_navigator()
        st.markdown("---")
        
        folder_path = st.text_input(
            "Вы можете скорректировать абсолютный путь вручную здесь:",
            value=st.session_state.bulk_folder_path
        )
        
        if st.button("Запустить пакетную индексацию архива", type="primary"):
            if not folder_path.strip() or not os.path.exists(folder_path):
                st.error("Указанный путь к папке не найден. Проверьте правильность пути.")
                return
                
            files_to_process = []
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(".pdf"):
                        files_to_process.append(os.path.join(root, file))
                        
            total_files = len(files_to_process)
            if total_files == 0:
                st.warning("В указанной папке не обнаружено файлов в формате PDF.")
                return
                
            st.success(f"Обнаружено {total_files} PDF-файлов. Начинаем параллельную пакетную обработку...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                neo4j_client.init_constraints()
            except Exception:
                pass

            for idx, filepath in enumerate(files_to_process):
                filename = os.path.basename(filepath)
                status_text.text(f"Индексация [{idx+1}/{total_files}]: {filename}...")
                
                try:
                    security, trust = map_folder_to_metadata(filepath)
                    
                    raw_text, doc_metadata = document_loader.load_pdf(
                        filepath, 
                        security_level=security, 
                        trust_level=trust
                    )
                    
                    chunks = text_splitter.split_text(raw_text, doc_metadata)
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = [executor.submit(process_and_save_chunk, chunk, doc_metadata, security) for chunk in chunks]
                        for _ in as_completed(futures):
                            pass
                        
                except Exception as e:
                    st.error(f"Ошибка при обработке файла {filename}: {e}")
                
                progress_bar.progress(int((idx + 1) / total_files * 100))
                
            st.success(f"Пакетная индексация завершена! Успешно обработано файлов: {total_files}.")