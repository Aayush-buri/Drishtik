import logging
import sys
from app.core.config import settings

def setup_logging() -> None:
    """
    Configures application logging.
    Application logging must remain separate from future forensic audit logging.
    Do not log passwords, authentication tokens, secrets, private keys, or sensitive evidence contents.
    """
    log_level_name = settings.LOG_LEVEL.upper()
    log_level = logging.getLevelName(log_level_name)
    
    if not isinstance(log_level, int):
        log_level = logging.INFO
        
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Optional: reduce noise from third-party libraries if needed later
    # logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(settings.APP_NAME)
