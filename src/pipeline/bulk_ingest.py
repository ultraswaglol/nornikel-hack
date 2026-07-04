# src/pipeline/bulk_ingest.py
import os
import sys
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в пути Python, чтобы импорты работали из терминала
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.pipeline.document_loader import document_loader
from src.pipeline.text_splitter import text_splitter
from src.pipeline.entity_extractor import entity_extractor
from src.pipeline.entity_linker import entity_linker
from src.core.yandex_ai import yandex_ai
from src.core.qdrant_client import vector_client
from src.core.neo4j_client import neo4j_client
from src.models.ontology import SecurityLevel, TrustLevel

load_dotenv()

# Файл-реестр для кэширования обработанных документов
REGISTRY_FILE = "processed_files_registry.json"

def load_registry() -> set:
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_to_registry(filepath: str):
    registry = load_registry()
    registry.add(filepath)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(registry), f, ensure_ascii=False, indent=2)

def map_folder_to_metadata(filepath: str) -> tuple:
    """
    Автоматически сопоставляет путь к файлу с уровнем достоверности и безопасности 
    в соответствии с онтологией R&D (на основе папок)
    """
    path_lower = filepath.lower()
    
    # По умолчанию
    security = SecurityLevel.PUBLIC
    trust = TrustLevel.LEVEL_B
    
    if "журналы" in path_lower or "статьи" in path_lower:
        trust = TrustLevel.LEVEL_A  # Рецензируемые научные публикации
    elif "доклады" in path_lower or "конференций" in path_lower:
        trust = TrustLevel.LEVEL_B  # Материалы конференций
    elif "обзоры" in path_lower:
        trust = TrustLevel.LEVEL_B
        
    return security, trust

def process_single_file(filepath: str) -> str:
    """Пайплайн обработки одного файла"""
    try:
        security, trust = map_folder_to_metadata(filepath)
        
        # 1. Извлечение текста
        raw_text, doc_metadata = document_loader.load_pdf(
            filepath, 
            security_level=security, 
            trust_level=trust
        )
        
        # 2. Нарезка на чанки
        chunks = text_splitter.split_text(raw_text, doc_metadata)
        
        # 3. Индексация чанков и графа
        for chunk in chunks:
            # Получаем вектор и сохраняем в Qdrant
            vector = yandex_ai.get_embedding(chunk["text"], is_query=False)
            vector_client.save_chunk(
                text_chunk=chunk["text"],
                vector=vector,
                metadata={
                    "title": doc_metadata["title"],
                    "security_level": security.value,
                    "year": doc_metadata["year"]
                }
            )
            
            # Извлекаем граф через ИИ
            extracted_graph = entity_extractor.extract_from_chunk(chunk["text"], doc_metadata)
            
            # Сливаем синонимы и записываем в Neo4j
            normalized_graph = entity_linker.normalize_graph(extracted_graph)
            neo4j_client.save_graph(normalized_graph)
            
        save_to_registry(filepath)
        return f"Успешно обработан: {os.path.basename(filepath)}"
    except Exception as e:
        return f"Ошибка при обработке {os.path.basename(filepath)}: {e}"

def bulk_ingest(root_folder: str, max_workers: int = 5):
    """Сканирует папки и запускает многопоточную обработку"""
    print("Инициализация ограничений в Neo4j...")
    neo4j_client.init_constraints()
    
    processed_files = load_registry()
    files_to_process = []
    
    # Сканируем папки на наличие PDF-файлов
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file.lower().endswith(".pdf"):
                full_path = os.path.join(root, file)
                if full_path not in processed_files:
                    files_to_process.append(full_path)
                    
    total_files = len(files_to_process)
    print(f"Найдено файлов для обработки: {total_files} (Пропущено уже обработанных: {len(processed_files)})")
    
    if total_files == 0:
        print("Все файлы уже обработаны!")
        return

    # Запускаем многопоточный пул для отправки запросов к API в параллели
    print(f"Запуск пула потоков с {max_workers} воркерами...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_file, fp): fp for fp in files_to_process}
        
        completed_count = 0
        for future in as_completed(futures):
            completed_count += 1
            result = future.result()
            print(f"[{completed_count}/{total_files}] {result}")

if __name__ == "__main__":
    # Укажите путь к корневой папке 'Источники информации' на вашем диске
    # Например: "/Users/ultraswag/Downloads/Источники информации"
    ROOT_DATA_FOLDER = "/Users/ultraswag/Downloads/Источники информации" 
    
    if os.path.exists(ROOT_DATA_FOLDER):
        bulk_ingest(ROOT_DATA_FOLDER, max_workers=5)  # 5 потоков — оптимально для старта
    else:
        print(f"Папка {ROOT_DATA_FOLDER} не найдена. Пожалуйста, укажите верный абсолютный путь к папке в скрипте.")