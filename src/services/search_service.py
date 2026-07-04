# src/services/search_service.py
from typing import List, Dict, Any
from src.core.yandex_ai import yandex_ai
from src.core.qdrant_client import vector_client
from src.core.neo4j_client import neo4j_client

class HybridSearchService:
    def search(self, query: str, security_level: str = "PUBLIC", limit: int = 5) -> Dict[str, Any]:
        """
        Выполняет параллельный поиск в двух базах данных:
        1. Векторный поиск по смыслу в Qdrant.
        2. Поиск связанных сущностей по ключевым словам в Neo4j.
        """
        # 1. Векторный поиск по текстовым чанкам
        query_vector = yandex_ai.get_embedding(query, is_query=True)
        text_chunks = vector_client.search_similar_chunks(
            query_vector=query_vector, 
            security_level=security_level, 
            limit=limit
        )

        # 2. Извлечение контекста из графа знаний
        # Ищем в графе процессы и материалы, которые упоминаются в запросе
        graph_facts = []
        words = [w.strip(",.?!\"'").lower() for w in query.split() if len(w) > 3]
        
        if words:
            # Cypher-запрос на поиск совпадений по ключевым словам в именах сущностей
            cypher_query = """
            MATCH (n)-[r]->(m)
            WHERE any(word IN $words WHERE toLower(n.name) CONTAINS word OR toLower(m.name) CONTAINS word)
            RETURN labels(n)[0] AS source_type, n.name AS source_name, 
                   type(r) AS rel_type, 
                   labels(m)[0] AS target_type, m.name AS target_name
            LIMIT 15
            """
            try:
                records = neo4j_client.query(cypher_query, {"words": words})
                for rec in records:
                    fact = f"[{rec['source_type']}] {rec['source_name']} -> {rec['rel_type']} -> [{rec['target_type']}] {rec['target_name']}"
                    graph_facts.append(fact)
            except Exception as e:
                print(f"Ошибка при извлечении фактов из графа: {e}")

        return {
            "text_chunks": [chunk["text"] for chunk in text_chunks],
            "graph_facts": graph_facts
        }

search_service = HybridSearchService()