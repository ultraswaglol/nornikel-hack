# src/services/graph_rag_service.py
import os
from src.core.yandex_ai import yandex_ai
from src.core.neo4j_client import neo4j_client
from src.services.search_service import search_service

class GraphRAGService:
    def __init__(self):
        # Используем старшую Alice AI для качественного синтеза рассуждений и написания Cypher
        self.model_name = "alice-ai"

    def _get_schema_prompt(self) -> str:
        return """
        Ты — транслятор естественного языка в запросы Cypher для графовой базы данных Neo4j.
        
        Схема графа:
        - Узлы Material: свойства {id, name, name_en, formula, state_of_matter}
        - Узлы Process: свойства {id, name, type}
        - Узлы Property: свойства {id, name, value, min_value, max_value, unit}
        - Узлы Publication: свойства {id, title, authors, year, geography, security_level, trust_level}
        
        Связи:
        - (:Process)-[:USES_MATERIAL]->(:Material)
        - (:Process)-[:OPERATES_AT]->(:Property)
        - (:Publication)-[:DESCRIBES]->(:Process)
        
        Правила генерации Cypher:
        1. Отвечай ТОЛЬКО чистым кодом Cypher. Не используй markdown-разметку (```cypher) или пояснения.
        2. Используй toLower() для поиска по тексту, чтобы избежать ошибок регистра.
        3. Примеры фильтрации числовых диапазонов: 
           MATCH (p:Process)-[:OPERATES_AT]->(pr:Property) WHERE pr.name = 'Сухой остаток' AND pr.value <= 1000
        """

    def answer_question(self, user_query: str, security_level: str = "PUBLIC") -> str:
        """
        Основной метод генерации ответа. 
        Попытка 1: Сгенерировать Cypher и достать данные из графа.
        Попытка 2 (Резервная): В случае ошибки выполнения Cypher — автоматический откат на векторный гибридный поиск.
        """
        system_prompt = self._get_schema_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Сгенерируй Cypher-запрос для ответа на вопрос: '{user_query}'"}
        ]
        
        graph_records = []
        cypher_query = ""
        
        try:
            # 1. Генерируем Cypher код
            cypher_query = yandex_ai.get_text_completion(self.model_name, messages, temperature=0.1)
            # Очищаем от возможных markdown тегов
            cypher_query = cypher_query.strip().replace("```cypher", "").replace("```", "").strip()
            
            # 2. Выполняем в Neo4j
            graph_records = neo4j_client.query(cypher_query)
        except Exception as e:
            print(f"Ошибка выполнения сгенерированного Cypher-запроса ({cypher_query}): {e}")
            # Если Cypher сломался, мы не падаем, а идем в резервный гибридный поиск

        # 3. Собираем контекст (смешиваем граф-результаты и векторные данные)
        hybrid_results = search_service.search(user_query, security_level=security_level)
        
        # Объединяем источники знаний
        context_parts = []
        if graph_records:
            context_parts.append(f"Структурированные факты из Графа Знаний:\n{graph_records}")
        if hybrid_results["graph_facts"]:
            context_parts.append(f"Связанные термины из Базы Знаний:\n" + "\n".join(hybrid_results["graph_facts"]))
        if hybrid_results["text_chunks"]:
            context_parts.append(f"Выдержки из R&D документов:\n" + "\n\n".join(hybrid_results["text_chunks"]))
            
        context = "\n\n===\n\n".join(context_parts)

        # 4. Формируем финальный инженерный ответ через Alice AI
        synthesis_prompt = f"""
        Ты — главный научный консультант горно-металлургической компании.
        Ответь на вопрос пользователя, используя предоставленный контекст (данные из графа и выдержки из документов).
        Если в контексте есть противоречия или разные мнения ученых по оптимальным параметрам — обязательно укажи это.
        
        Вопрос: {user_query}
        
        Контекст для анализа:
        {context}
        """
        
        final_messages = [
            {"role": "system", "content": "Ты эксперт-аналитик, дающий точные инженерные ответы на основе верифицированных документов."},
            {"role": "user", "content": synthesis_prompt}
        ]
        
        return yandex_ai.get_text_completion(self.model_name, final_messages, temperature=0.3)

graph_rag_service = GraphRAGService()