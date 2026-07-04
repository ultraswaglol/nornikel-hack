# src/core/qdrant_client.py
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from config.settings import settings
from src.core.yandex_ai import yandex_ai
import uuid

class VectorStoreClient:
    def __init__(self):
        self.client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        self.collection_name = "nornickel_rd_chunks"
        self._init_collection()

    def _init_collection(self):
        """Автоматически настраивает размерность Qdrant под активный режим ИИ (1536 для Cloud, 768 для Local/Mock)"""
        # ФИКС: Устанавливаем 1536 для облачной модели text-embeddings
        self.vector_size = 1536 if yandex_ai.ai_mode == "CLOUD" and not yandex_ai.mock_mode else 768
        
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if exists:
            # Проверяем размерность существующей коллекции в базе
            info = self.client.get_collection(self.collection_name)
            current_size = info.config.params.vectors.size
            if current_size != self.vector_size:
                # Если размерность изменилась, авто-пересоздаем коллекцию!
                print(f"🔄 [Qdrant]: Смена режима ИИ. Пересоздание коллекции: ожидалось {self.vector_size}, было {current_size}.")
                self.client.delete_collection(self.collection_name)
                exists = False
                
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )

    def save_chunk(self, text_chunk: str, vector: list, metadata: dict):
        """Запись чанка и его вектора в базу"""
        point_id = str(uuid.uuid4())
        payload = {
            "text": text_chunk,
            **metadata
        }
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(id=point_id, vector=vector, payload=payload)
            ]
        )

    def search_similar_chunks(self, query_vector: list, security_level: str, limit: int = 5) -> list:
        """Поиск семантически похожих фрагментов с учетом ролевой модели ИБ"""
        from qdrant_client.models import Filter, FieldCondition, MatchAny
        
        allowed_levels = ["PUBLIC"]
        if security_level in ["INTERNAL", "CONFIDENTIAL"]:
            allowed_levels.append("INTERNAL")
        if security_level == "CONFIDENTIAL":
            allowed_levels.append("CONFIDENTIAL")

        query_filter = Filter(
            must=[
                FieldCondition(
                    key="security_level",
                    match=MatchAny(any=allowed_levels)
                )
            ]
        )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit
        )
        return [hit.payload for hit in results.points]

vector_client = VectorStoreClient()