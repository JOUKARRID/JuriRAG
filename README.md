# JuriRAG

JuriRAG is a local web interface for testing the Moroccan employment-law and tax RAG pipeline. It uses the existing ChromaDB index, multilingual E5 embeddings, BM25 keyword retrieval, and the configured LLM provider.

## Run locally (Windows)

From the project directory, start the existing virtual environment's Python server:

```powershell
.\venv\Scripts\python.exe app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop the server with `Ctrl+C`. Set `PORT` before startup to use a different local port.

The server binds only to `127.0.0.1`. Your configured provider key must be available as an environment variable (`GROQ_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY`, depending on `src/config.py`). The page shows whether the configured provider is ready. Generation sends the question and retrieved legal excerpts to that provider; **Recherche seule** tests retrieval locally without an LLM request. For automatic domain detection in this mode, the query needs to contain a known work- or tax-related keyword; otherwise, choose a domain manually.

## API

- `GET /api/health` — local index and LLM configuration status; never returns API-key values.
- `POST /api/query` — JSON body: `{"question":"...","domain":"auto","mode":"answer"}`. Use `mode: "retrieve"` to return hybrid-search excerpts without generating an answer. `domain` may be `auto`, `travail`, or `impots`.

The first search loads the embedding model and may take a little while (and may download its weights if they are not cached yet).
