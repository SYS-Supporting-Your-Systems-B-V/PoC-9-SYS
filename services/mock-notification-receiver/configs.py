import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("mock_notification_receiver.app")


class Settings(BaseSettings):
    host: str = Field("0.0.0.0", validation_alias="MOCK_RECEIVER_HOST")
    port: int = Field(8002, validation_alias="MOCK_RECEIVER_PORT")
    public_base: str = Field(
        "https://mach2.disyepd.com/receiver-mock/fhir",
        validation_alias="MOCK_RECEIVER_PUBLIC_BASE",
    )
    default_task_status: str = Field("requested", validation_alias="MOCK_RECEIVER_DEFAULT_TASK_STATUS")
    require_bearer_token: bool = Field(True, validation_alias="MOCK_RECEIVER_REQUIRE_BEARER_TOKEN")
    nuts_internal_base: str = Field("http://nuts-node:8083", validation_alias="MOCK_RECEIVER_NUTS_INTERNAL_BASE")
    introspection_timeout: float = Field(10.0, validation_alias="MOCK_RECEIVER_INTROSPECTION_TIMEOUT")
    required_scope: str = Field("eOverdracht-receiver", validation_alias="MOCK_RECEIVER_REQUIRED_SCOPE")
    log_level: str = Field("INFO", validation_alias="MOCK_RECEIVER_LOG_LEVEL")
    model_config = SettingsConfigDict(case_sensitive=False)


def _load_dotenv_once() -> None:
    try:
        from dotenv import dotenv_values

        dotenv_path = (Path(__file__).parent / ".env").resolve()
        if not dotenv_path.exists():
            logger.info("[mock-notification-receiver] .env not found file=%s", str(dotenv_path))
            return

        for key, value in dotenv_values(str(dotenv_path)).items():
            if value is not None and key not in os.environ:
                os.environ[key] = value
        logger.info("[mock-notification-receiver] .env loaded file=%s", str(dotenv_path))
    except Exception:
        logger.exception("[mock-notification-receiver] .env load failed")


_load_dotenv_once()
settings = Settings()


__all__ = ["settings"]
