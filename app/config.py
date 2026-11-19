import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")).resolve()
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
SECRET = os.environ.get("SECRET", "")
MAX_DURATION_S = int(os.environ.get("MAX_DURATION_S", "300"))      # 5 min max par défaut
MAX_BYTES = int(os.environ.get("MAX_BYTES", str(300 * 1024 * 1024)))
YTDLP_TIMEOUT_S = int(os.environ.get("YTDLP_TIMEOUT_S", "300"))
YTDLP_EXTRA_ARGS = os.environ.get("YTDLP_EXTRA_ARGS", "").split()
# Apify : désactivé tant que tu n'as pas mis ALLOW_APIFY=1 (accord explicite = coût)
ALLOW_APIFY = os.environ.get("ALLOW_APIFY", "0") == "1"
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_ACTOR = os.environ.get("APIFY_ACTOR", "")                    # ex. utilisateur~acteur
APIFY_INPUT_JSON = os.environ.get("APIFY_INPUT_JSON", "")          # contient {url}
APIFY_MAX_USD = os.environ.get("APIFY_MAX_USD", "1.0")
APIFY_TIMEOUT_S = int(os.environ.get("APIFY_TIMEOUT_S", "600"))
