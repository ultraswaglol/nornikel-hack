# ui/components/graph_renderer.py
import streamlit as st
from pyvis.network import Network
from src.core.neo4j_client import neo4j_client
from typing import List, Optional

def render_graph_component(seed_node_ids: Optional[List[str]] = None, limit: int = 50):
    """
    Генерирует интеллектуальную Ego-сеть вокруг активных узлов или 
    отображает подсеть последних исследований во избежание перегрузки браузера (Hairball Problem).
    Использует современный st.iframe для повышения производительности отрисовки.
    """
    net = Network(height="450px", width="100%", bgcolor="#1a1a1a", font_color="white")
    
    color_map = {
        "Material": "#2b5c8f",      # Синий
        "Process": "#2b8f5c",       # Зеленый
        "Property": "#ebd234",      # Желтый
        "Publication": "#eb4034",    # Красный
        "Equipment": "#8a34eb",      # Фиолетовый
        "Expert": "#eb7a34"          # Оранжевый
    }
    
    # 1. Формируем Cypher-запрос с учетом Ego-сети
    if seed_node_ids:
        query = """
        MATCH (n)-[r]-(m)
        WHERE n.id IN $seeds OR m.id IN $seeds
        RETURN n, r, m LIMIT $limit
        """
        parameters = {"seeds": seed_node_ids, "limit": limit}
    else:
        # Если поискового контекста нет (дашборд), выводим только подсеть 3-х последних публикаций
        query = """
        MATCH (pub:Publication)
        WITH pub ORDER BY pub.year DESC LIMIT 3
        MATCH (pub)-[r]-(m)
        RETURN pub AS n, r, m LIMIT $limit
        """
        parameters = {"limit": limit}
        
    try:
        records = neo4j_client.query(query, parameters)
        if not records:
            if seed_node_ids:
                st.info("По запросу нет связанных графических путей.")
            else:
                st.info("Граф пока пуст. Загрузите документы во вкладке 'Импорт'.")
            return

        for rec in records:
            node_a = rec["n"]
            node_b = rec["m"]
            rel = rec["r"]
            
            label_a = list(node_a.labels)[0]
            label_b = list(node_b.labels)[0]
            
            # Добавляем узлы в сеть
            net.add_node(
                node_a["id"], 
                label=node_a["name"] if "name" in node_a else node_a["title"], 
                color=color_map.get(label_a, "#999999"),
                title=f"Тип: {label_a}"
            )
            net.add_node(
                node_b["id"], 
                label=node_b["name"] if "name" in node_b else node_b["title"], 
                color=color_map.get(label_b, "#999999"),
                title=f"Тип: {label_b}"
            )
            
            # Добавляем связь
            net.add_edge(node_a["id"], node_b["id"], title=rel.type)
            
        net.save_graph("temp_graph.html")
        
        # ФИКС: Используем современный st.iframe вместо устаревшего st.components.v1.html.
        # Мы рендерим сохраненный HTML-файл графа напрямую, убирая предупреждения в консоли.
        st.iframe("temp_graph.html", height=460)
        
    except Exception as e:
        st.error(f"Не удалось отрисовать граф: {e}")