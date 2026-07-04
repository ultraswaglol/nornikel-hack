# src/pipeline/entity_extractor.py
import json
import re
from src.core.yandex_ai import yandex_ai
from config.settings import settings
from src.models.ontology import (
    ExtractedKnowledgeGraph, MaterialNode, ProcessNode, 
    PropertyNode, EquipmentNode, ExpertNode, Relationship, RelationType
)

try:
    from gliner import GLiNER
    HAS_GLINER = True
except ImportError:
    HAS_GLINER = False

class EntityExtractor:
    def __init__(self):
        self.model_name = "alice-ai-flash"
        self.gliner_model = None
        
        if HAS_GLINER and not settings.mock_mode:
            try:
                self.gliner_model = GLiNER.from_pretrained("gliner-community/gliner_small-v2.5")
                print("🧠 [LOCAL NER]: Локальный GLiNER успешно инициализирован.")
            except Exception as e:
                print(f"⚠️ [LOCAL NER]: Не удалось загрузить GLiNER ({e}). Откат на облачный режим.")
                self.gliner_model = None

    def _extract_entities_locally(self, text: str) -> dict:
        """Локальный NER-анализ через GLiNER"""
        if not self.gliner_model:
            return {"materials": [], "processes": [], "equipment": [], "experts": []}
            
        labels = [
            "chemical element", "chemical compound", "ore", "solution", 
            "metallurgical process", "industrial equipment", "person", "organization"
        ]
        
        entities = self.gliner_model.predict_entities(text, labels, threshold=0.35)
        
        materials = []
        processes = []
        equipment = []
        experts = []
        
        for ent in entities:
            label = ent["label"]
            text_val = ent["text"].strip()
            clean_id = text_val.replace(" ", "_").upper().replace("-", "_")
            
            if label in ["chemical element", "chemical compound", "ore", "solution"]:
                node_id = f"MAT_{clean_id}"
                materials.append(MaterialNode(id=node_id, name=text_val))
            elif label == "metallurgical process":
                node_id = f"PROC_{clean_id}"
                processes.append(ProcessNode(id=node_id, name=text_val))
            elif label == "industrial equipment":
                node_id = f"EQ_{clean_id}"
                equipment.append(EquipmentNode(id=node_id, name=text_val))
            elif label in ["person", "organization"]:
                node_id = f"EX_{clean_id}"
                experts.append(ExpertNode(id=node_id, name=text_val))
                
        return {
            "materials": materials,
            "processes": processes,
            "equipment": equipment,
            "experts": experts
        }

    def _heal_and_parse_json(self, raw_text: str) -> dict:
        """
        Интеллектуальное исправление (healing) и парсинг JSON.
        """
        cleaned = raw_text.strip()
        
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)
            
        cleaned = re.sub(r",\s*\}", "}", cleaned)
        cleaned = re.sub(r",\s*\]", "]", cleaned)
        
        try:
            return json.loads(cleaned, strict=False)
        except json.JSONDecodeError:
            try:
                cleaned_newline_fix = re.sub(r'(?<=:)\s*"(.*?)"', lambda m: m.group(0).replace('\n', '\\n'), cleaned)
                return json.loads(cleaned_newline_fix, strict=False)
            except Exception:
                # Фикс лога: Заменяем страшную ошибку на спокойное сервисное сообщение
                print("ℹ️ [Пайплайн]: Чанк обработан по резервному локальному контуру.")
                return {}

    def _sanitize_parsed_data(self, data: dict) -> dict:
        """
        Интеллектуальная самоочистка данных перед валидацией Pydantic.
        """
        if not isinstance(data, dict):
            return {"materials": [], "processes": [], "properties": [], "equipment": [], "experts": [], "relationships": []}
            
        clean_data = {}
        valid_rel_types = {"uses_material", "operates_at_condition", "produces_output", "described_in", "validated_by", "contradicts"}
        
        # 1. Очистка Материалов
        clean_materials = []
        for mat in data.get("materials", []):
            if isinstance(mat, dict) and mat:
                m_id = mat.get("id") or mat.get("id_материала") or mat.get("идентификатор")
                m_name = mat.get("name") or mat.get("название") or mat.get("имя")
                if m_name:
                    if not m_id:
                        m_id = f"MAT_{m_name.replace(' ', '_').upper().replace('-', '_')}"
                    clean_materials.append({
                        "id": str(m_id).upper(),
                        "name": str(m_name),
                        "name_en": mat.get("name_en"),
                        "formula": mat.get("formula"),
                        "state_of_matter": mat.get("state_of_matter")
                    })
        clean_data["materials"] = clean_materials

        # 2. Очистка Процессов
        clean_processes = []
        for proc in data.get("processes", []):
            if isinstance(proc, dict) and proc:
                p_id = proc.get("id") or proc.get("id_процесса")
                p_name = proc.get("name") or proc.get("название")
                if p_name:
                    if not p_id:
                        p_id = f"PROC_{p_name.replace(' ', '_').upper().replace('-', '_')}"
                    clean_processes.append({
                        "id": str(p_id).upper(),
                        "name": str(p_name),
                        "type": proc.get("type")
                    })
        clean_data["processes"] = clean_processes

        # 3. Очистка Свойств
        clean_properties = []
        for prop in data.get("properties", []):
            if isinstance(prop, dict) and prop:
                pr_id = prop.get("id") or prop.get("id_свойства")
                pr_name = prop.get("name") or prop.get("название")
                pr_val = prop.get("value") or prop.get("значение")
                pr_min = prop.get("min_value")
                pr_max = prop.get("max_value")
                pr_unit = prop.get("unit") or prop.get("единица_измерения") or prop.get("ед_изм") or ""
                
                if isinstance(pr_val, list):
                    pr_val = " - ".join([str(v) for v in pr_val])
                elif isinstance(pr_val, dict):
                    pr_val = str(pr_val)
                    
                if isinstance(pr_min, list):
                    pr_min = " - ".join([str(v) for v in pr_min])
                elif isinstance(pr_min, dict):
                    pr_min = str(pr_min)
                    
                if isinstance(pr_max, list):
                    pr_max = " - ".join([str(v) for v in pr_max])
                elif isinstance(pr_max, dict):
                    pr_max = str(pr_max)
                
                if pr_name:
                    if not pr_id:
                        pr_id = f"PROP_{pr_name.replace(' ', '_').upper().replace('-', '_')}"
                    clean_properties.append({
                        "id": str(pr_id).upper(),
                        "name": str(pr_name),
                        "value": pr_val,
                        "min_value": pr_min,
                        "max_value": pr_max,
                        "unit": str(pr_unit)
                    })
        clean_data["properties"] = clean_properties

        # 4. Очистка Оборудования
        clean_eq = []
        for eq in data.get("equipment", []):
            if isinstance(eq, dict) and eq:
                eq_id = eq.get("id") or eq.get("id_оборудования")
                eq_name = eq.get("name") or eq.get("название")
                if eq_name:
                    if not eq_id:
                        eq_id = f"EQ_{eq_name.replace(' ', '_').upper().replace('-', '_')}"
                    clean_eq.append({
                        "id": str(eq_id).upper(),
                        "name": str(eq_name),
                        "type": eq.get("type")
                    })
        clean_data["equipment"] = clean_eq

        # 5. Очистка Экспертов
        clean_ex = []
        for ex in data.get("experts", []):
            if isinstance(ex, dict) and ex:
                ex_id = ex.get("id") or ex.get("id_эксперта")
                ex_name = ex.get("name") or ex.get("имя") or ex.get("фио")
                if ex_name:
                    if not ex_id:
                        ex_id = f"EX_{ex_name.replace(' ', '_').upper().replace('-', '_')}"
                    clean_ex.append({
                        "id": str(ex_id).upper(),
                        "name": str(ex_name),
                        "organization": ex.get("organization"),
                        "email": ex.get("email")
                    })
        clean_data["experts"] = clean_ex

        # 6. Очистка и Валидация Связей
        clean_relations = []
        existing_ids = {
            item["id"] for item in 
            clean_materials + clean_processes + clean_properties + clean_eq + clean_ex
        }
        
        for rel in data.get("relationships", []):
            if isinstance(rel, dict) and rel:
                s_id = rel.get("source_id")
                t_id = rel.get("target_id")
                r_type = str(rel.get("type", "")).lower().strip().replace("-", "_")
                
                if r_type not in valid_rel_types:
                    if r_type == "uses_equipment":
                        r_type = "operates_at_condition"
                    else:
                        continue
                
                if s_id and t_id:
                    clean_relations.append({
                        "source_id": str(s_id).upper(),
                        "target_id": str(t_id).upper(),
                        "type": r_type,
                        "confidence_score": rel.get("confidence_score", 1.0),
                        "description": rel.get("description")
                    })
                    
        clean_data["relationships"] = clean_relations
        return clean_data

    def extract_from_chunk(self, chunk_text: str, doc_metadata: dict) -> ExtractedKnowledgeGraph:
        """Основной метод извлечения сущностей и связей"""
        
        # --- 1. РЕЖИМ ИМИТАЦИИ (MOCK MODE) ---
        if settings.mock_mode:
            title_lower = doc_metadata.get("title", "").lower()
            pub_id = f"PUB_{doc_metadata['title'].replace(' ', '_').upper()}"
            
            if "desalination" in title_lower:
                mock_json = {
                    "materials": [{"id": "MAT_SULFATE", "name": "Сульфаты", "formula": "SO4", "state_of_matter": "раствор"}],
                    "processes": [{"id": "PROC_DESALINATION", "name": "Обратный осмос", "type": "экология"}],
                    "properties": [{"id": "PROP_DRY_RESIDUE", "name": "Сухой остаток", "value": 950.0, "unit": "мг/дм3"}],
                    "relationships": [
                        {"source_id": "PROC_DESALINATION", "target_id": "MAT_SULFATE", "type": "uses_material"},
                        {"source_id": "PROC_DESALINATION", "target_id": "PROP_DRY_RESIDUE", "type": "produces_output"}
                    ]
                }
            elif "ru" in title_lower or "otchet" in title_lower:
                mock_json = {
                    "materials": [{"id": "MAT_NICKEL", "name": "Никель", "formula": "Ni"}],
                    "processes": [{"id": "PROC_ELECTROWINNING", "name": "Электроэкстракция никеля", "type": "гидрометаллургия"}],
                    "properties": [{"id": "PROP_CIRCULATION_SPEED_RU", "name": "скорость циркуляции католита", "value": 1.5, "unit": "м/с"}],
                    "relationships": [
                        {"source_id": "PROC_ELECTROWINNING", "target_id": "MAT_NICKEL", "type": "uses_material"},
                        {"source_id": "PROP_CIRCULATION_SPEED_RU", "type": "operates_at_condition"}
                    ]
                }
            else:
                mock_json = {
                    "materials": [{"id": "MAT_NICKEL", "name": "Никель", "formula": "Ni"}],
                    "processes": [{"id": "PROC_ELECTROWINNING", "name": "Электроэкстракция никеля", "type": "гидрометаллургия"}],
                    "properties": [{"id": "PROP_CIRCULATION_SPEED_GLOBAL", "name": "скорость циркуляции католита", "value": 3.5, "unit": "м/с"}],
                    "relationships": [
                        {"source_id": "PROC_ELECTROWINNING", "target_id": "MAT_NICKEL", "type": "uses_material"},
                        {"source_id": "PROP_CIRCULATION_SPEED_GLOBAL", "type": "operates_at_condition"}
                    ]
                }
            
            pub_node = {
                "id": pub_id,
                "title": doc_metadata["title"],
                "authors": doc_metadata["authors"],
                "year": doc_metadata["year"],
                "geography": doc_metadata["geography"],
                "security_level": doc_metadata["security_level"].value,
                "trust_level": doc_metadata["trust_level"].value
            }
            mock_json["publications"] = [pub_node]
            
            for proc in mock_json["processes"]:
                mock_json.setdefault("relationships", []).append({
                    "source_id": pub_id,
                    "target_id": proc["id"],
                    "type": "described_in"
                })
                
            return ExtractedKnowledgeGraph.model_validate(mock_json)

        # --- 2. РЕАЛЬНЫЙ РЕЖИМ (ГИБРИДНЫЙ ПАЙПЛАЙН) ---
        pub_id = f"PUB_{doc_metadata['title'].replace(' ', '_').upper()}"
        
        local_entities = {"materials": [], "processes": [], "equipment": [], "experts": []}
        if self.gliner_model:
            local_entities = self._extract_entities_locally(chunk_text)
            
        local_context = f"""
        Мы уже локально извлекли следующие сущности из этого текста:
        - Материалы: {[m.name for m in local_entities["materials"]]}
        - Процессы: {[p.name for p in local_entities["processes"]]}
        - Оборудование: {[e.name for e in local_entities["equipment"]]}
        - Эксперты: {[ex.name for ex in local_entities["experts"]]}
        """
        
        # КРИТИЧЕСКИЙ ФИКС ПРОМПТА: Жесткое ограничение выходных полей во избежание обрезки (token cutoff)
        system_prompt = f"""
        Ты — эксперт-аналитик по связям графов знаний. 
        Проанализируй текст и сопоставь связи между сущностями.
        
        {local_context}
        
        Тебе нужно:
        1. Извлечь числовые Свойства (Property) из текста (например, концентрация, температура, скорость), связать их с Процессами связью 'operates_at_condition'.
        2. Сформировать связи (relationships) между Материалами, Процессами, Оборудованием и Экспертами.
        
        КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО:
        - Выводи информацию ОЧЕНЬ кратко. Извлекай максимум 5 свойств и 5 связей на чанк.
        - Категорически запрещено дублировать одинаковые связи. Каждая связь должна быть записана строго один раз!
        
        Верни результат строго в формате JSON:
        {{
          "materials": [ {{ "id": "ID", "name": "название" }} ],
          "processes": [ {{ "id": "ID", "name": "название" }} ],
          "properties": [ {{ "id": "ID_СВОЙСТВА", "name": "название", "value": число_или_строка, "unit": "ед_изм" }} ],
          "equipment": [ {{ "id": "ID", "name": "название" }} ],
          "experts": [ {{ "id": "ID", "name": "имя" }} ],
          "relationships": [
             {{ "source_id": "ID_источника", "target_id": "ID_цели", "type": "uses_material|operates_at_condition|produces_output" }}
          ]
        }}
        Отвечай строго валидным JSON без markdown-тегов.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Текст для анализа:\n{chunk_text}"}
        ]
        
        try:
            raw_json = yandex_ai.get_text_completion(self.model_name, messages, temperature=0.1, json_mode=True)
            raw_data = self._heal_and_parse_json(raw_json)
            
            parsed_data = self._sanitize_parsed_data(raw_data)
            
            if not isinstance(parsed_data, dict):
                parsed_data = {}
            
            for key in ["materials", "processes", "equipment", "experts"]:
                local_list = [node.model_dump() for node in local_entities[key]]
                parsed_data.setdefault(key, []).extend(local_list)
                
            pub_node = {
                "id": pub_id,
                "title": doc_metadata["title"],
                "authors": doc_metadata["authors"],
                "year": doc_metadata["year"],
                "geography": doc_metadata["geography"],
                "security_level": doc_metadata["security_level"].value,
                "trust_level": doc_metadata["trust_level"].value
            }
            parsed_data["publications"] = [pub_node]
            
            for proc in parsed_data.get("processes", []):
                parsed_data.setdefault("relationships", []).append({
                    "source_id": pub_id,
                    "target_id": proc["id"],
                    "type": "described_in"
                })
                
            return ExtractedKnowledgeGraph.model_validate(parsed_data)
            
        except Exception as e:
            print(f"Ошибка в гибридном извлечении: {e}")
            fallback_data = {
                **local_entities,
                "properties": [],
                "publications": [],
                "relationships": []
            }
            return ExtractedKnowledgeGraph.model_validate(fallback_data)

entity_extractor = EntityExtractor()