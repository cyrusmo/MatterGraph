import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_prefix="MATTERGRAPH_", extra="ignore")

  demo_data: Path = Path(
    os.environ.get("MATTERGRAPH_DEMO_DATA", "data/demo/materials_sample.jsonl")
  )


settings = Settings()
