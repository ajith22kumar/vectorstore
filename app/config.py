from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    redis_url: str = ""            # empty = use in-memory cache
    answer_cache_ttl: int = 3600
    graph_cache_ttl: int = 2592000
    rate_limit_per_minute: int = 30
    openai_api_key: str
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "gpt-4"
    chunk_size: int = 500
    chunk_overlap: int = 100
    top_k: int = 5
    max_distance: float = 0.8
    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = " "
    chroma_dir: str = "./chroma_data"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    model_config = {"env_file": ".env"}
    graph_hops: int = 2
    graph_chunk_limit: int = 4
    final_chunks: int = 6
    rrf_k: int = 60
settings = Settings()