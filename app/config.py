import os
from dotenv import load_dotenv

# Locate .env relative to this file regardless of working directory
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(_env_path)

UKHO_API_KEY = os.getenv("UKHO_API_KEY", "")
UKHO_BASE_URL = "https://admiraltyapi.azure-api.net/uktidalapi/api/V1"

SIGNALK_HOST = os.getenv("SIGNALK_HOST", "localhost")
SIGNALK_PORT = int(os.getenv("SIGNALK_PORT", "3000"))

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8080"))
