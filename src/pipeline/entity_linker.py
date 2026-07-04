from src.core.neo4j_client import neo4j_client
from src.models.ontology import ExtractedKnowledgeGraph

class EntityLinker:
    def __init__(self):
        # Базовый словарь синонимов горно-металлургических терминов
        self.hard_synonyms = {
            "ni": "MAT_NICKEL",
            "никель": "MAT_NICKEL",
            "nickel": "MAT_NICKEL",
            "au": "MAT_GOLD",
            "золото": "MAT_GOLD",
            "gold": "MAT_GOLD",
            "electrowinning": "PROC_ELECTROWINNING",
            "электроэкстракция": "PROC_ELECTROWINNING",
            "электролиз": "PROC_ELECTROWINNING",
            "пвп": "PROC_FLASH_SMELTING",
            "печь взвешенной плавки": "PROC_FLASH_SMELTING"
        }

    def resolve_entity_id(self, raw_id: str, raw_name: str, entity_type: str) -> str:
        """
        Проверяет существование синонимов в графе и возвращает нормализованный ID.
        """
        # КРИТИЧЕСКИЙ ФИКС: Разрешаем слияние только для Материалов и Процессов.
        # Свойства (Property) НЕЛЬЗЯ сливать по имени, так как у них разные числовые значения!
        if entity_type not in ["Material", "Process"]:
            return raw_id

        # 1. Проверяем жесткий словарь синонимов
        clean_name = raw_name.lower().strip()
        if clean_name in self.hard_synonyms:
            return self.hard_synonyms[clean_name]
            
        # 2. Проверяем существование точного имени или ID в базе данных через Neo4j
        query = f"""
        MATCH (n:{entity_type})
        WHERE toLower(n.name) = toLower($name) OR n.id = $id
        RETURN n.id AS id
        LIMIT 1
        """
        result = neo4j_client.query(query, {"name": raw_name, "id": raw_id})
        if result:
            return result[0]["id"]
            
        return raw_id

    def normalize_graph(self, graph: ExtractedKnowledgeGraph) -> ExtractedKnowledgeGraph:
        """
        Пробегается по всему извлеченному графу чанка, заменяет все ID сущностей на нормализованные
        и корректирует связи (relationships), чтобы они указывали на правильные слитые узлы.
        """
        id_mapping = {}
        
        # Нормализуем материалы
        for mat in graph.materials:
            normalized_id = self.resolve_entity_id(mat.id, mat.name, "Material")
            id_mapping[mat.id] = normalized_id
            mat.id = normalized_id
            
        # Нормализуем процессы
        for proc in graph.processes:
            normalized_id = self.resolve_entity_id(proc.id, proc.name, "Process")
            id_mapping[proc.id] = normalized_id
            proc.id = normalized_id

        # Нормализуем свойства
        for prop in graph.properties:
            normalized_id = self.resolve_entity_id(prop.id, prop.name, "Property")
            id_mapping[prop.id] = normalized_id
            prop.id = normalized_id

        # Корректируем ID в связях
        valid_relations = []
        for rel in graph.relationships:
            # Заменяем старые ID на новые нормализованные
            source_mapped = id_mapping.get(rel.source_id, rel.source_id)
            target_mapped = id_mapping.get(rel.target_id, rel.target_id)
            
            # Исключаем связь сущности самой с собой (петлю), которая могла возникнуть при слиянии
            if source_mapped != target_mapped:
                rel.source_id = source_mapped
                rel.target_id = target_mapped
                valid_relations.append(rel)
                
        graph.relationships = valid_relations
        return graph

entity_linker = EntityLinker()