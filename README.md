# JuriRAG 🇲🇦

**An AI-powered legal assistant for Moroccan employment law and taxation.**

JuriRAG is a web-based Retrieval-Augmented Generation (RAG) application designed to help users explore Moroccan legal and tax information through natural-language questions.

It combines semantic search, keyword-based retrieval, and Large Language Models (LLMs) to retrieve relevant legal documents and generate contextual answers.

##  Features

- **Hybrid Retrieval:** Combines multilingual E5 embeddings with BM25 keyword search.
- **Vector Database:** Uses ChromaDB to store and retrieve legal document embeddings.
- **AI-Generated Answers:** Uses a configurable LLM provider to generate answers based on retrieved legal excerpts.
- **Legal Domains:**
  - Moroccan employment law (*Code du travail*).
  - Moroccan taxation (*Code général des impôts* and VAT documentation).
- **Retrieval-Only Mode:** Tests document retrieval without sending a request to an LLM.
- **Web Interface:** Simple interface for asking questions and exploring retrieved legal information.

##  Technologies

- Python
- ChromaDB
- Multilingual E5 Embeddings
- BM25
- Retrieval-Augmented Generation (RAG)
- HTML, CSS, JavaScript
- Groq / Gemini / Anthropic (configurable LLM providers)

##  Run Locally (Windows)

### 1. Clone the repository

```bash
git clone https://github.com/JOUKARRID/JuriRAG.git
cd JuriRAG
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your LLM provider

Set the API key corresponding to your configured provider:

- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`

Keep your API keys private. Never commit them to GitHub.

### 5. Start the application

```bash
python app.py
```

Open your browser at:

[http://127.0.0.1:8000](http://127.0.0.1:8000)

Stop the server using `Ctrl + C`.

The application uses the `PORT` environment variable when available (default: `8000`). The server binds to `0.0.0.0` to support cloud deployment.

## 🔌 API Endpoints

### Health Check

```http
GET /api/health
```

Returns the application status, local index availability, and LLM provider configuration status. API-key values are never returned.

### Ask a Question

```http
POST /api/query
Content-Type: application/json
```

Example request:

```json
{
  "question": "Combien de jours de congé annuel payé après six mois de service ?",
  "domain": "travail",
  "mode": "answer"
}
```

Available parameters:

| Parameter | Values | Description |
|---|---|---|
| `question` | Text | User's legal or tax question |
| `domain` | `auto`, `travail`, `impots` | Selects the legal domain |
| `mode` | `answer`, `retrieve` | Generates an answer or retrieves relevant excerpts only |

**Recherche seule** (`retrieve`) performs retrieval without making an LLM request.

## 📚 Legal Data Sources

The project uses Moroccan legal and tax documentation, including:

- Moroccan Labour Code (Law No. 65-99).
- General Tax Code (CGI).
- VAT documentation.
- Documentation concerning foreign employees in Morocco.

The first search may take some time because the embedding model needs to load. If its weights are not cached, they may be downloaded automatically.

##  Disclaimer

JuriRAG is an experimental AI-powered legal information assistant. Its responses are intended for informational and educational purposes only and do not replace professional legal or tax advice.

Always verify important information against official and up-to-date legal sources.

## 👨‍💻 Author

**Mohammed Joukarrid**  
Master's Student in Artificial Intelligence and Digital Computing  
Faculty of Sciences and Techniques of Béni Mellal (FST Béni Mellal), Morocco.

##  Project Status

JuriRAG is an ongoing project. Improvements to retrieval quality, legal-document coverage, and deployment are planned.
