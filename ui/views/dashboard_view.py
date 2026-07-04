import streamlit as st
import pandas as pd
from src.services.conflict_resolver import conflict_resolver
from src.core.neo4j_client import neo4j_client

def render_dashboard_view():
    st.subheader("📊 Аналитика R&D знаний и Качество данных")
    
    # 1. Системные метрики
    try:
        nodes_count = neo4j_client.query("MATCH (n) RETURN count(n) as count")[0]["count"]
        rels_count = neo4j_client.query("MATCH ()-[r]->() RETURN count(r) as count")[0]["count"]
        pubs_count = neo4j_client.query("MATCH (p:Publication) RETURN count(p) as count")[0]["count"]
    except Exception:
        nodes_count, rels_count, pubs_count = 0, 0, 0
        
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Всего сущностей в графе", nodes_count)
    with col2:
        st.metric("Зафиксировано связей", rels_count)
    with col3:
        st.metric("Обработано публикаций", pubs_count)
        
    st.markdown("---")
    
    # 2. Сравнительный анализ (с точным маппингом свойств по ID публикаций)
    st.markdown("### ⚖️ Сравнительный анализ технологий")
    st.write("Сравнение технологий на основе параметров и публикаций из базы знаний:")
    
    compare_query = """
    MATCH (pub:Publication)-[:described_in]->(p:Process)-[:operates_at_condition]->(pr:Property)
    WHERE (pub.id = "PUB_REPORT_NICKEL_ELECTROWINNING_RU" AND pr.id = "PROP_CIRCULATION_SPEED_RU")
       OR (pub.id = "PUB_REPORT_NICKEL_ELECTROWINNING_GLOBAL" AND pr.id = "PROP_CIRCULATION_SPEED_GLOBAL")
       OR (pub.id = "PUB_REPORT_WATER_DESALINATION" AND pr.id = "PROP_DRY_RESIDUE")
    RETURN p.name AS Process, pub.title AS Source, pr.name AS Parameter, pr.value AS Value
    """
    try:
        records = neo4j_client.query(compare_query)
        if records:
            df = pd.DataFrame(records)
            pivot_df = df.pivot_table(
                index=["Process", "Source"], 
                columns="Parameter", 
                values="Value"
            ).fillna("Нет данных")
            st.dataframe(pivot_df, use_container_width=True)
        else:
            st.info("Пока недостаточно числовых параметров в базе данных для построения сравнительной таблицы.")
    except Exception as e:
        st.error(f"Не удалось построить таблицу сравнения: {e}")
        
    st.markdown("---")
    
    # 3. Выявление противоречий
    st.markdown("### ⚠️ Технологические противоречия в исследованиях")
    conflicts = conflict_resolver.find_technological_conflicts()
    if conflicts:
        for conf in conflicts:
            with st.expander(f"⚠️ Конфликт по параметру: '{conf['PropertyName']}' (Процесс: {conf['ProcessName']})"):
                st.write(f"**Источник А**: *\"{conf['SourceA']}\"* ➔ Значение: **{conf['ValueA']} {conf['UnitA']}**")
                st.write(f"**Источник Б**: *\"{conf['SourceB']}\"* ➔ Значение: **{conf['ValueB']} {conf['UnitB']}**")
    else:
        st.success("В базе знаний не обнаружено явных противоречий по технологическим параметрам.")
        
    st.markdown("---")
    
    # 4. Анализ «Белых пятен»
    st.markdown("### 🔍 Белые пятна в R&D-карте знаний")
    gaps = conflict_resolver.find_knowledge_gaps()
    if gaps:
        for gap in gaps:
            formula_str = f" ({gap['Formula']})" if gap['Formula'] else ""
            st.warning(f"Компонент: **{gap['MaterialName']}**{formula_str} — технологические цепочки отсутствуют.")
    else:
        st.success("Все материалы в базе покрыты хотя бы одним технологическим процессом.")