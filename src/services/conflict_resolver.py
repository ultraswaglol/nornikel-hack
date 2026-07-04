from typing import List, Dict, Any
from src.core.neo4j_client import neo4j_client

class ConflictResolverService:
    def find_technological_conflicts(self) -> List[Dict[str, Any]]:
        """
        Ищет технологические конфликты и дедуплицирует их, оставляя только уникальные пары.
        """
        cypher_query = """
        MATCH (pub1:Publication)-[:described_in]->(p:Process)-[:operates_at_condition]->(pr1:Property)
        MATCH (pub2:Publication)-[:described_in]->(p)-[:operates_at_condition]->(pr2:Property)
        WHERE pr1.name = pr2.name 
          AND pub1.id < pub2.id 
          AND pr1.value <> pr2.value
          AND ((pub1.id CONTAINS "RU" AND pr1.id CONTAINS "RU") OR (pub1.id CONTAINS "GLOBAL" AND pr1.id CONTAINS "GLOBAL"))
          AND ((pub2.id CONTAINS "RU" AND pr2.id CONTAINS "RU") OR (pub2.id CONTAINS "GLOBAL" AND pr2.id CONTAINS "GLOBAL"))
        RETURN p.name AS ProcessName, 
               pr1.name AS PropertyName,
               pub1.title AS SourceA, pr1.value AS ValueA, pr1.unit AS UnitA,
               pub2.title AS SourceB, pr2.value AS ValueB, pr2.unit AS UnitB
        LIMIT 10
        """
        try:
            return neo4j_client.query(cypher_query)
        except Exception as e:
            print(f"Ошибка при поиске технологических конфликтов: {e}")
            return []

    def find_knowledge_gaps(self) -> List[Dict[str, Any]]:
        """
        Анализ 'белых пятен': ищет материалы (Material), для которых 
        в базе данных нет ни одного связанного процесса (Process).
        """
        cypher_query = """
        MATCH (m:Material)
        WHERE NOT (m)<-[:uses_material]-(:Process)
        RETURN m.name AS MaterialName, m.formula AS Formula
        LIMIT 10
        """
        try:
            return neo4j_client.query(cypher_query)
        except Exception as e:
            print(f"Ошибка при поиске белых пятен: {e}")
            return []

conflict_resolver = ConflictResolverService()