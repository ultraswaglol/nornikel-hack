# config/settings.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class AppSettings(BaseSettings):
    yandex_ai_studio_api_key: str = Field(default="mock_key", alias="YANDEX_AI_STUDIO_API_KEY")
    yandex_folder_id: str = Field(default="mock_folder", alias="YANDEX_FOLDER_ID")
    
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(alias="NEO4J_PASSWORD")
    
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")

    # Переключатель ИИ: LOCAL или CLOUD
    ai_mode: str = Field(default="LOCAL", alias="AI_MODE")
    mock_mode: bool = Field(default=True, alias="MOCK_MODE")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = AppSettings()