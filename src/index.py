import json
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from config import MODEL, VECTORSTORE

sys.stdout.reconfigure(encoding="utf-8")

print("Modele :", MODEL)
model = SentenceTransformer(MODEL)
client = chromadb.PersistentClient(path=VECTORSTORE)

chunks = [json.loads(l) for l in
          Path("data/chunks.jsonl").read_text(encoding="utf-8").splitlines()]

for domain in ("travail", "impots"):
    try:
        client.delete_collection(domain)
    except Exception:
        pass
    col = client.create_collection(domain, metadata={"hnsw:space": "cosine"})
    sub = [c for c in chunks if c["domain"] == domain]
    for i in range(0, len(sub), 64):
        batch = sub[i:i + 64]
        emb = model.encode(
            ["passage: " + c["text"] for c in batch],
            normalize_embeddings=True, show_progress_bar=False).tolist()
        col.add(
            ids=[c["id"] for c in batch],
            embeddings=emb,
            documents=[c["text"] for c in batch],
            metadatas=[{k: c[k] for k in
                        ("doc", "doc_title", "date_doc", "article", "page_pdf")}
                       for c in batch],
        )
        print(domain, i + len(batch), "/", len(sub), flush=True)

print("Indexation terminee.")