# src/core/yandex_ai.py
import os
import time
import random
from typing import List
from openai import OpenAI
from config.settings import settings

class YandexAIClient:
    def __init__(self):
        # Инициализируем настройки из .env
        self.reinit_client(
            api_key=settings.yandex_ai_studio_api_key,
            folder_id=settings.yandex_folder_id,
            ai_mode=settings.ai_mode,
            mock_mode=settings.mock_mode
        )

    def reinit_client(self, api_key: str, folder_id: str, ai_mode: str, mock_mode: bool):
        """
        Безопасно пересоздает клиент ИИ в реальном времени при изменении настроек в UI.
        """
        self.mock_mode = mock_mode
        self.ai_mode = ai_mode.upper()  # LOCAL или CLOUD
        self.folder_id = folder_id
        
        if not self.mock_mode:
            if self.ai_mode == "CLOUD":
                # Боевой облачный клиент Яндекса
                self.client = OpenAI(
                    api_key=api_key,
                    base_url="https://ai.api.cloud.yandex.net/v1",
                    project=self.folder_id  # Передаем FOLDER_ID как project
                )
            else:
                # Локальный клиент Ollama
                self.client = OpenAI(
                    api_key="ollama",
                    base_url="http://localhost:11434/v1"
                )

    def get_text_completion(self, model_name: str, messages: List[dict], temperature: float = 0.1, json_mode: bool = False) -> str:
        """Генерация текста с автоматической маршрутизацией запросов и поддержкой URI AI Studio"""
        if self.mock_mode:
            user_text = messages[-1]["content"].lower()
            if "cypher" in messages[0]["content"].lower():
                if "обессоливани" in user_text:
                    return "MATCH (p:Process {id: 'PROC_DESALINATION'})-[:operates_at_condition]->(pr:Property) RETURN p.name, pr.name, pr.value, pr.unit"
                elif "электроэкстракц" in user_text or "flow rate" in user_text:
                    return "MATCH (p:Process {id: 'PROC_ELECTROWINNING'})-[:operates_at_condition]->(pr:Property) RETURN p.name, pr.name, pr.value, pr.unit"
                return "MATCH (n)-[r]->(m) RETURN n.name, type(r), m.name LIMIT 10"
                
            if "эксперт-технолог" in messages[0]["content"].lower():
                if "обессоливани" in user_text:
                    return """На основе анализа R&D-отчетов компании, для исходной воды с содержанием сульфатов (250 мг/л) рекомендуется метод **обратного осмоса (reverse osmosis)**. 
                    Согласно экспериментальным данным из отчета *'Water Desalination Methods for Enrichment Plant'*, этот метод позволяет снизить сухой остаток до **950 мг/дм³**, что полностью удовлетворяет убедительному показателю в 1000 мг/дм³. Процесс протекает при рабочем давлении до 1.5 МПа."""
                elif "электроэкстракц" in user_text:
                    return """В базе знаний зафиксировано противоречие относительно оптимальной скорости циркуляции католита при электроэкстракции никеля:
                    1. Отечественная практика (*Отчет лаборатории гидрометаллургии Норникеля*): рекомендуется скорость **1.5 м/с** для предотвращения загрязнения катодов.
                    2. Зарубежная практика (*Исследование Outokumpu Technology*): рекомендуется поддерживать скорость на уровне **3.5 м/с** во во избежание истощения прикатолидного слоя.
                    Скорости ниже 2.0 м/с по зарубежным источникам ведут к росту дендритов, что расходится с отечественными рекомендациями."""
            return "Имитационный режим: Ответ сгенерирован локально. Система готова к подключению к Yandex AI Studio."

        # Выбираем модель в зависимости от режима и формируем полный URI для Yandex AI Studio
        if self.ai_mode == "CLOUD":
            mapped_model = "yandexgpt-lite" if model_name in ["alice-ai-flash", "alice-ai-llm-flash"] else "yandexgpt"
            model_uri = f"gpt://{self.folder_id}/{mapped_model}/latest"
        else:
            model_uri = "qwen3.5"

        kwargs = {
            "model": model_uri,
            "messages": messages,
            "temperature": temperature
        }
        
        # Включаем json_mode (response_format) СТРОГО только если мы НЕ в облачном режиме!
        # Облако Яндекса не поддерживает этот параметр в API, а локальная Qwen через Ollama поддерживает идеально.
        if json_mode and self.ai_mode != "CLOUD":
            kwargs["response_format"] = {"type": "json_object"}
            
        max_retries = 5
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content.strip()
            except Exception as e:
                if "429" in str(e) or "limit" in str(e).lower() or "quota" in str(e).lower():
                    delay = base_delay * (2 ** attempt) + random.uniform(0.1, 0.5)
                    print(f"⚠️ [API 429]: Превышен лимит одновременных запросов. Повторная попытка {attempt+1}/{max_retries} через {delay:.2f} сек...")
                    time.sleep(delay)
                else:
                    raise e
                    
        raise Exception("Превышены все попытки обращения к ИИ из-за лимитов одновременных сессий.")

    def get_embedding(self, text: str, is_query: bool = False) -> List[float]:
        """Генерация эмбеддинга (1536 для Яндекса, 768 для локального Nomic)"""
        if self.mock_mode:
            # В Mock-режиме возвращаем 1536 для Cloud, 768 для Local под размерность Qdrant
            return [0.0] * (1536 if self.ai_mode == "CLOUD" else 768)
            
        # В новом Yandex AI Studio используется единая модель text-embeddings, выдающая 1536 измерений
        if self.ai_mode == "CLOUD":
            model_uri = f"emb://{self.folder_id}/text-embeddings/latest"
        else:
            model_uri = "nomic-embed-text"
        
        max_retries = 5
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                params = {
                    "input": [text],
                    "model": model_uri
                }
                if self.ai_mode == "CLOUD":
                    params["encoding_format"] = "float"
                    
                response = self.client.embeddings.create(**params)
                return response.data[0].embedding
            except Exception as e:
                if "429" in str(e) or "limit" in str(e).lower() or "quota" in str(e).lower():
                    delay = base_delay * (2 ** attempt) + random.uniform(0.1, 0.5)
                    print(f"⚠️ [API 429]: Превышен лимит эмбеддингов. Повторная попытка {attempt+1}/{max_retries} через {delay:.2f} сек...")
                    time.sleep(delay)
                else:
                    raise e
                    
        raise Exception("Превышены все попытки получения эмбеддингов.")

yandex_ai = YandexAIClient()