"""
MMarra Data Hub - Configuracao centralizada.
Todas as variaveis de ambiente e constantes em um unico lugar.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ============================================================
# SANKHYA API
# ============================================================

SANKHYA_BASE_URL = "https://api.sankhya.com.br"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_X_TOKEN", "")

# ============================================================
# LLM - Ollama (fallback local)
# ============================================================

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_CLASSIFIER_MODEL = os.getenv("LLM_CLASSIFIER_MODEL", os.getenv("LLM_MODEL", "qwen3:4b"))
USE_LLM_CLASSIFIER = os.getenv("USE_LLM_CLASSIFIER", "true").lower() in ("true", "1", "yes")
LLM_CLASSIFIER_TIMEOUT = int(os.getenv("LLM_CLASSIFIER_TIMEOUT", "60"))
USE_LLM_NARRATOR = os.getenv("USE_LLM_NARRATOR", "true").lower() in ("true", "1", "yes")

# ============================================================
# LLM - Groq API
# ============================================================

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_MODEL_CLASSIFY = os.getenv("GROQ_MODEL_CLASSIFY", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "10"))
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ============================================================
# LLM - Anthropic Haiku (classificador inteligente)
# ============================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
USE_HAIKU_CLASSIFIER = os.getenv("USE_HAIKU_CLASSIFIER", "false").lower() in ("true", "1", "yes")
HAIKU_MODEL = os.getenv("HAIKU_MODEL", "claude-haiku-4-5-20251001")
HAIKU_TIMEOUT = int(os.getenv("HAIKU_TIMEOUT", "8"))

# ============================================================
# AZURE DATA LAKE
# ============================================================

AZURE_STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT", "mmarradatalake")
AZURE_STORAGE_KEY = os.getenv("AZURE_STORAGE_KEY", "")
AZURE_CONTAINER = os.getenv("AZURE_CONTAINER", "datahub")

# ============================================================
# SMART AGENT
# ============================================================

SMART_ONLY = os.getenv("SMART_ONLY", "true").lower() in ("true", "1", "yes")
ADMIN_USERS = [u.strip().upper() for u in os.getenv("ADMIN_USERS", "").split(",") if u.strip()]

# ============================================================
# QUERY EXECUTOR
# ============================================================

MAX_ROWS = 500
QUERY_TIMEOUT = 30

# ============================================================
# TRAINING
# ============================================================

TRAINING_HOUR = int(os.getenv("TRAINING_HOUR", "3"))
