# app.py
import streamlit as st
from config.settings import settings
from src.core.neo4j_client import neo4j_client
from src.core.qdrant_client import vector_client
from src.core.yandex_ai import yandex_ai  # Импортируем синглтон ИИ
from ui.views.search_view import render_search_view
from ui.views.import_view import render_import_view
from ui.views.dashboard_view import render_dashboard_view

st.set_page_config(
    page_title="R&D Knowledge Graph - Норникель",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Кэшируем инициализацию базы, чтобы она выполнялась строго 1 раз при старте сервера
@st.cache_resource
def initialize_database():
    try:
        neo4j_client.init_constraints()
        return True
    except Exception as e:
        print(f"Ошибка подключения к Neo4j при старте: {e}")
        return False

# Отображаем визуальный лоадер только при первом запуске
if "db_initialized" not in st.session_state:
    with st.spinner("⏳ Подключение к графовой базе знаний Neo4j..."):
        success = initialize_database()
        if success:
            st.session_state.db_initialized = True
            try:
                st.toast("✅ Успешно подключено к Neo4j!")
            except Exception:
                pass

# Боковое брендированное меню
st.sidebar.markdown(
    """
    <div style="background-color:#0f172a; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #1e293b;">
        <h2 style="color:#38bdf8; font-family:sans-serif; margin:0; font-size:22px; letter-spacing: 1px;">НОРНИКЕЛЬ</h2>
        <p style="color:#94a3b8; font-family:sans-serif; margin:0; font-size:14px; font-weight:bold;">R&D КАРТА ЗНАНИЙ</p>
    </div>
    """, 
    unsafe_allow_html=True
)

# 1. Авторизация (Роль) в соответствии с ИБ
st.sidebar.subheader("🔒 Авторизация (Роль)")
user_role = st.sidebar.selectbox(
    "Выберите вашу учетную запись:",
    ["Исследователь R&D (Public)", "Аналитик (Internal)", "Главный инженер (Confidential)"]
)

st.sidebar.markdown("---")

# 2. Навигация
st.sidebar.subheader("🧭 Навигация")
menu_selection = st.sidebar.radio(
    "Перейти на страницу:",
    ["Поиск и GraphRAG", "Импорт Документов", "Аналитика и Дашборды"]
)

st.sidebar.markdown("---")

# 3. БЕЗОПАСНАЯ И ДИНАМИЧЕСКАЯ ПАНЕЛЬ НАСТРОЕК ИИ В СУББАРЕ
with st.sidebar.expander("⚙️ Настройки ИИ (AI Settings)", expanded=False):
    if "api_key_session" not in st.session_state:
        st.session_state.api_key_session = settings.yandex_ai_studio_api_key
    if "folder_id_session" not in st.session_state:
        st.session_state.folder_id_session = settings.yandex_folder_id

    mock_ui = st.checkbox("Имитационный режим (Mock)", value=yandex_ai.mock_mode)
    
    ai_mode_ui = st.selectbox(
        "Режим работы ИИ:",
        ["LOCAL", "CLOUD"],
        index=0 if yandex_ai.ai_mode == "LOCAL" else 1,
        disabled=mock_ui
    )
    
    api_key_ui = st.text_input(
        "Yandex API Key:",
        value=st.session_state.api_key_session,
        type="password",
        disabled=mock_ui
    )
    folder_id_ui = st.text_input(
        "Yandex Folder ID:",
        value=st.session_state.folder_id_session,
        type="password",
        disabled=mock_ui
    )
    
    if st.button("Применить настройки ИИ", use_container_width=True, type="primary"):
        st.session_state.api_key_session = api_key_ui
        st.session_state.folder_id_session = folder_id_ui
        
        yandex_ai.reinit_client(api_key_ui, folder_id_ui, ai_mode_ui, mock_ui)
        vector_client._init_collection()
        
        st.success("Настройки успешно применены!")
        st.rerun()

# Маршрутизация
if menu_selection == "Поиск и GraphRAG":
    render_search_view(user_role)
elif menu_selection == "Импорт Документов":
    render_import_view()
elif menu_selection == "Аналитика и Дашборды":
    render_dashboard_view()