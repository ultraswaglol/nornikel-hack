# ui/views/search_view.py
import streamlit as st
from src.services.graph_rag_service import graph_rag_service
from ui.components.graph_renderer import render_graph_component
from config.logger import log_action

def render_search_view(user_role: str):
    st.subheader("🔍 Интеллектуальная поисковая система (GraphRAG)")
    
    role_security_map = {
        "Исследователь R&D (Public)": "PUBLIC",
        "Аналитик (Internal)": "INTERNAL",
        "Главный инженер (Confidential)": "CONFIDENTIAL"
    }
    security_level = role_security_map.get(user_role, "PUBLIC")
    
    query = st.text_input(
        "Введите ваш технологический запрос:", 
        placeholder="Например: Какие методы обессоливания воды подходят при сульфатах < 300 мг/л?",
        key="global_search_input"
    )
    
    if st.button("Выполнить поиск", type="primary"):
        if query.strip():
            # Логируем действие пользователя (ИБ Аудит)
            log_action(user_role, "SEARCH", f"Запрос: {query}")
            
            with st.spinner("Alice AI анализирует базы данных..."):
                answer = graph_rag_service.answer_question(query, security_level=security_level)
                
                st.markdown("### 💡 Аналитический ответ системы:")
                st.write(answer)
                
                # Кнопка экспорта в Markdown
                st.download_button(
                    label="📥 Скачать аналитический отчет (Markdown)",
                    data=answer,
                    file_name="nornickel_rd_report.md",
                    mime="text/markdown"
                )
                
                # Логируем экспорт отчета
                log_action(user_role, "EXPORT_REPORT", f"Экспортирован отчет по запросу: {query}")
                
                st.markdown("### 🔗 Локальный граф связей по теме запроса:")
                render_graph_component(limit=40)
        else:
            st.warning("Пожалуйста, сформулируйте поисковый запрос.")