import json
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import answer as rag_answer
import chromadb
from config import GEMINI_MODEL, GROQ_MODEL, LLM_BACKEND, LLM_FALLBACK, OLLAMA_MODEL, VECTORSTORE
from llm import OPENAI_STYLE
from retriever import search

WEB_ROOT = PROJECT_ROOT / "web"
RAG_LOCK = threading.Lock()
MAX_REQUEST_BYTES = 16_384
VALID_DOMAINS = {"auto", "travail", "impots"}


def _llm_status():
    if LLM_BACKEND == "ollama":
        configured = True
    elif LLM_BACKEND in OPENAI_STYLE:
        configured = bool(os.environ.get(OPENAI_STYLE[LLM_BACKEND][1]))
    elif LLM_BACKEND == "claude":
        configured = bool(os.environ.get("ANTHROPIC_API_KEY"))
    else:
        configured = False

    return {
        "backend": LLM_BACKEND,
        "model": {
            "groq": GROQ_MODEL,
            "gemini": GEMINI_MODEL,
            "ollama": OLLAMA_MODEL,
        }.get(LLM_BACKEND, LLM_BACKEND),
        "configured": configured,
        "fallback": LLM_FALLBACK or None,
    }


def _health():
    result = {
        "status": "degraded",
        "llm": _llm_status(),
        "collections": {},
        "chunks_file": (PROJECT_ROOT / "data" / "chunks.jsonl").is_file(),
    }
    try:
        client = chromadb.PersistentClient(path=str(PROJECT_ROOT / VECTORSTORE))
        for domain in ("travail", "impots"):
            result["collections"][domain] = client.get_collection(domain).count()
        result["status"] = (
            "ready" if all(result["collections"].values())
            and result["chunks_file"] else "degraded"
        )
    except Exception as exc:
        result["index_error"] = str(exc)
    return result


def _serialize_source(source):
    meta = source.get("meta") or {}
    return {
        "title": meta.get("doc_title") or meta.get("doc") or "Document juridique",
        "article": meta.get("article"),
        "page": meta.get("page_pdf"),
        "date": meta.get("date_doc"),
        "kind": source.get("kind"),
        "score": source.get("score"),
        "text": source.get("text", ""),
    }


class JuriRAGHandler(BaseHTTPRequestHandler):
    server_version = "JuriRAG/1.0"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(200, _health())
            return
        if path == "/":
            self._send_file(WEB_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if path == "/styles.css":
            self._send_file(WEB_ROOT / "styles.css", "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._send_file(WEB_ROOT / "app.js", "text/javascript; charset=utf-8")
            return
        self._send_json(404, {"error": "Route introuvable."})

    def do_POST(self):
        if urlparse(self.path).path != "/api/query":
            self._send_json(404, {"error": "Route introuvable."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "En-tête Content-Length invalide."})
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "La requête est vide ou trop volumineuse."})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Le corps doit être un objet JSON valide."})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Le corps doit être un objet JSON."})
            return

        question = payload.get("question")
        domain = payload.get("domain", "auto")
        mode = payload.get("mode", "answer")
        if not isinstance(question, str) or not question.strip():
            self._send_json(400, {"error": "Saisissez une question."})
            return
        question = question.strip()
        if len(question) > 2_000:
            self._send_json(400, {"error": "La question ne peut pas dépasser 2 000 caractères."})
            return
        if not isinstance(domain, str) or domain not in VALID_DOMAINS:
            self._send_json(400, {"error": "Domaine invalide."})
            return
        if not isinstance(mode, str) or mode not in {"answer", "retrieve"}:
            self._send_json(400, {"error": "Mode invalide."})
            return

        try:
            with RAG_LOCK:
                if mode == "retrieve":
                    selected_domain = (
                        rag_answer.classify(question, use_llm=False)
                        if domain == "auto" else domain
                    )
                    if selected_domain == "autre":
                        self._send_json(
                            422,
                            {"error": "Choisissez explicitement le domaine pour cette recherche sans LLM."},
                        )
                        return
                    results = search(selected_domain, question)
                    response = {
                        "mode": mode,
                        "domain": selected_domain,
                        "answer": None,
                        "sources": [_serialize_source(item) for item in results],
                    }
                else:
                    text, sources, resolved_domain = rag_answer.answer(
                        question,
                        None if domain == "auto" else domain,
                    )
                    response = {
                        "mode": mode,
                        "domain": resolved_domain,
                        "answer": text,
                        "sources": [_serialize_source(item) for item in sources],
                    }
            self._send_json(200, response)
        except Exception as exc:
            traceback.print_exc()
            self._send_json(500, {"error": str(exc) or "Erreur pendant le traitement."})

    def _send_file(self, path, content_type):
        try:
            content = path.read_bytes()
        except OSError:
            self._send_json(404, {"error": "Fichier de l’interface introuvable."})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status, value):
        content = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} - {fmt % args}", flush=True)


def main():
    try:
        port = int(os.environ.get("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("PORT doit être un nombre compris entre 1 et 65535.")

    server = ThreadingHTTPServer(("0.0.0.0", port), JuriRAGHandler)
    print(f"JuriRAG prêt : http://127.0.0.1:{port}", flush=True)
    print("Arrêtez le serveur avec Ctrl+C.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt de JuriRAG.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
