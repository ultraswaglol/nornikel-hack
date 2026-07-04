# src/core/neo4j_client.py
from neo4j import GraphDatabase
from config.settings import settings
from src.models.ontology import ExtractedKnowledgeGraph

class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri, 
            auth=(settings.neo4j_user, settings.neo4j_password)
        )

    def close(self):
        self.driver.close()

    def query(self, query_string, parameters=None):
        with self.driver.session() as session:
            result = session.run(query_string, parameters)
            return [dict(record) for record in result]

    def init_constraints(self):
        constraints = [
            "CREATE CONSTRAINT material_id_unique IF NOT EXISTS FOR (m:Material) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT process_id_unique IF NOT EXISTS FOR (p:Process) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT property_id_unique IF NOT EXISTS FOR (pr:Property) REQUIRE pr.id IS UNIQUE",
            "CREATE CONSTRAINT publication_id_unique IF NOT EXISTS FOR (pub:Publication) REQUIRE pub.id IS UNIQUE",
            "CREATE CONSTRAINT equipment_id_unique IF NOT EXISTS FOR (eq:Equipment) REQUIRE eq.id IS UNIQUE",
            "CREATE CONSTRAINT expert_id_unique IF NOT EXISTS FOR (ex:Expert) REQUIRE ex.id IS UNIQUE"
        ]
        with self.driver.session() as session:
            # 1. Применяем ограничения уникальности
            for constraint in constraints:
                session.run(constraint)
                
            # 2. ИСПРАВЛЕННЫЙ ХАК ИБ-ШУМА: Создаем временные сущности независимыми MERGE-запросами
            session.run('MERGE (m:Material {id: "TEMP_INIT_MATERIAL"}) SET m.name="INIT", m.formula="H2O"')
            session.run('MERGE (p:Process {id: "TEMP_INIT_PROCESS"}) SET p.name="INIT"')
            session.run('MERGE (pr:Property {id: "TEMP_INIT_PROPERTY"}) SET pr.name="INIT", pr.value=1.0, pr.unit="м"')
            session.run('MERGE (pub:Publication {id: "TEMP_INIT_PUB"}) SET pub.title="INIT", pub.authors=["INIT"], pub.year=2024, pub.geography="RU"')
            
            # Связываем созданные узлы (теперь MATCH на узлы гарантированно сработает!)
            session.run("""
            MATCH (p:Process {id: "TEMP_INIT_PROCESS"}), (m:Material {id: "TEMP_INIT_MATERIAL"})
            MERGE (p)-[:uses_material]->(m)
            """)
            session.run("""
            MATCH (p:Process {id: "TEMP_INIT_PROCESS"}), (pr:Property {id: "TEMP_INIT_PROPERTY"})
            MERGE (p)-[:operates_at_condition]->(pr)
            """)
            session.run("""
            MATCH (pub:Publication {id: "TEMP_INIT_PUB"}), (p:Process {id: "TEMP_INIT_PROCESS"})
            MERGE (pub)-[:described_in]->(p)
            """)
            
            # Мгновенно зачищаем временный мусор, оставляя типы связей зарегистрированными в схеме СУБД
            session.run('MATCH (n) WHERE n.id STARTS WITH "TEMP_INIT_" DETACH DELETE n')

    def save_graph(self, graph: ExtractedKnowledgeGraph):
        """Высокопроизводительное транзакционное сохранение графа через UNWIND"""
        with self.driver.session() as session:
            session.execute_write(self._write_batch_transaction, graph)

    @staticmethod
    def _write_batch_transaction(tx, graph: ExtractedKnowledgeGraph):
        # 1. Пакетная вставка Материалов
        if graph.materials:
            materials_batch = [m.model_dump() for m in graph.materials]
            tx.run(
                """
                UNWIND $batch AS param
                MERGE (m:Material {id: param.id})
                SET m.name = param.name, m.name_en = param.name_en, 
                    m.formula = param.formula, m.state_of_matter = param.state_of_matter
                """,
                batch=materials_batch
            )

        # 2. Пакетная вставка Процессов
        if graph.processes:
            tx.run(
                """
                UNWIND $batch AS proc
                MERGE (p:Process {id: proc.id})
                SET p.name = proc.name, p.type = proc.type
                """,
                batch=[p.model_dump() for p in graph.processes]
            )

        # 3. Пакетная запись Свойств
        if graph.properties:
            tx.run(
                """
                UNWIND $batch AS prop
                MERGE (pr:Property {id: prop.id})
                SET pr.name = prop.name, pr.value = prop.value, 
                    pr.min_value = prop.min_value, pr.max_value = prop.max_value, pr.unit = prop.unit
                """,
                batch=[pr.model_dump() for pr in graph.properties]
            )

        # 4. Пакетная запись Оборудования
        if graph.equipment:
            tx.run(
                """
                UNWIND $batch AS eq
                MERGE (e:Equipment {id: eq.id})
                SET e.name = eq.name, e.type = eq.type
                """,
                batch=[e.model_dump() for e in graph.equipment]
            )

        # 5. Пакетная запись Экспертов
        if graph.experts:
            tx.run(
                """
                UNWIND $batch AS ex
                MERGE (e:Expert {id: ex.id})
                SET e.name = ex.name, e.organization = ex.organization, e.email = ex.email
                """,
                batch=[ex.model_dump() for ex in graph.experts]
            )

        # 6. Пакетная запись Публикаций
        if graph.publications:
            tx.run(
                """
                UNWIND $batch AS pub
                MERGE (p:Publication {id: pub.id})
                SET p.title = pub.title, p.authors = pub.authors, p.year = pub.year, p.geography = pub.geography, 
                    p.security_level = pub.security_level, p.trust_level = pub.trust_level
                """,
                batch=[p.model_dump() for p in graph.publications]
            )

        # 7. Высокопроизводительное создание связей через UNWIND
        if graph.relationships:
            rel_batches = {}
            for rel in graph.relationships:
                rel_batches.setdefault(rel.type.value, []).append(rel.model_dump())
            
            for rel_type, batch in rel_batches.items():
                query = f"""
                UNWIND $batch AS rel
                MATCH (a {{id: rel.source_id}}), (b {{id: rel.target_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r.confidence_score = rel.confidence_score, r.description = rel.description
                """
                tx.run(query, batch=batch)

# Инициализируем синглтон подключения (КРИТИЧЕСКИ ВАЖНАЯ СТРОЧКА!)
neo4j_client = Neo4jClient()