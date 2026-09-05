import secrets
from pathlib import Path
from typing import ClassVar
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    # Application Configuration
    APP_NAME: str = "Drishtik Backend"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./data/drishtik.db"
    STORAGE_ROOT: str = "data"
    
    # Security: Loaded from .env or environment variable.
    # If not provided in environment, generates a secure random key at runtime (never hard-coded).
    JWT_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Logging
    LOG_LEVEL: str = "INFO"

    # Hyperledger Fabric Blockchain Configuration
    FABRIC_ENABLED: bool = False
    FABRIC_PEER_ENDPOINT: str = "localhost:7051"
    FABRIC_CHANNEL_NAME: str = "cctvchannel"
    FABRIC_CHAINCODE_NAME: str = "evidence_anchor"
    FABRIC_MSP_ID: str = "Org1MSP"
    FABRIC_CRYPTO_PATH: str = "blockchain/crypto"
    FABRIC_TLS_CERT_PATH: str = ""
    FABRIC_CLIENT_CERT_PATH: str = ""
    FABRIC_CLIENT_KEY_PATH: str = ""
    FABRIC_GATEWAY_TIMEOUT_SECONDS: int = 5

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=(str(ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
