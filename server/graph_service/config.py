from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore


class Settings(BaseSettings):
    openai_api_key: str = Field('not-used')
    openai_base_url: str | None = Field(None)
    model_name: str | None = Field(None)
    embedding_model_name: str | None = Field(None)
    neo4j_uri: str = Field('bolt://localhost:7687')
    neo4j_user: str = Field('neo4j')
    neo4j_password: str = Field('neo4j')
    # FalkorDB settings (used when graph_db_provider=falkordb)
    graph_db_provider: str = Field('neo4j')
    falkordb_host: str = Field('localhost')
    falkordb_port: int = Field(6379)

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


@lru_cache
def get_settings():
    return Settings()  # type: ignore[call-arg]


ZepEnvDep = Annotated[Settings, Depends(get_settings)]
