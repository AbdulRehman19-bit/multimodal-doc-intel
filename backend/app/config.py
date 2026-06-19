from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # Gemini
    gemini_api_key: str

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str
    langchain_project: str = "multimodal-doc-intel"

    # App
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    secret_key: str
    environment: str = "development"

    # ColPali model — using free open-source checkpoint
    colpali_model_name: str = "vidore/colpali-v1.2"

    # Storage
    document_bucket: str = "documents"
    index_storage_path: str = "/tmp/indexes"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()