# Modèle d'embeddings utilisé partout (indexation ET recherche).
# Si tu changes cette ligne, relance obligatoirement : python src/index.py
MODEL = "intfloat/multilingual-e5-small"
# MODEL = "intfloat/multilingual-e5-base"   # plus précis mais plus lent

VECTORSTORE = "vectorstore"

# --- Modèle qui rédige les réponses ---
LLM_BACKEND = "groq"              # "groq", "gemini", "claude" ou "ollama"
# Modèle de secours si le premier est saturé (ignoré si sa clé n'existe pas).
LLM_FALLBACK = "gemini"           # "groq", "gemini" ou None

GEMINI_MODEL = "gemini-3.8-flash"
GROQ_MODEL = "openai/gpt-oss-120b"
CLAUDE_MODEL = "claude-sonnet-5-5"
OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_URL = "http://localhost:11434/api/chat"

# Effort de réflexion des modèles qui "réfléchissent" : "low" = plus rapide.
# Mets None pour ne pas envoyer ce paramètre.
REASONING_EFFORT = "low"