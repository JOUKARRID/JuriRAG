import json
import re
import sys

import chromadb
from sentence_transformers import SentenceTransformer

from config import MODEL, VECTORSTORE

sys.stdout.reconfigure(encoding="utf-8")

chunks = [json.loads(l) for l in open("data/chunks.jsonl", encoding="utf-8")]
bad = [c["article"] for c in chunks if re.match(r"Article\d", c["article"])]
print("Etiquettes sans espace dans chunks.jsonl :", len(bad), bad[:8])

print("\n--- Les articles TVA attendus existent-ils dans les chunks du CGI ? ---")
for label in ("Article 91", "Article 92", "Article 98"):
    found = [c for c in chunks if c["doc"] == "impots_cgi_2026" and c["article"] == label]
    if not found:
        print(f"{label} : ABSENT des chunks")
        continue
    for c in found:
        print(f"{label} | page {c['page_pdf']} | {len(c['text'])} caracteres")
        print("    ", repr(c["text"][:350]))

model = SentenceTransformer(MODEL)
col = chromadb.PersistentClient(path=VECTORSTORE).get_collection("impots")
n = col.count()

QUERIES = [
    "Quel est le taux normal de la TVA ?",
    "Quel est le taux normal de la taxe sur la valeur ajoutée ?",
    "Quelles opérations sont exonérées de la TVA ?",
    "Quelles opérations sont exonérées de la taxe sur la valeur ajoutée ?",
]
for q in QUERIES:
    emb = model.encode("query: " + q, normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=[emb], n_results=n)
    metas, dists = res["metadatas"][0], res["distances"][0]
    print("\n" + "=" * 70)
    print(q)
    print("  top 3 :", [(m["article"], round(d, 3)) for m, d in list(zip(metas, dists))[:3]])
    for i, (m, d) in enumerate(zip(metas, dists), start=1):
        if m["doc"] == "impots_cgi_2026":
            print(f"  1er chunk du CGI : rang {i} ({m['article']}, dist {d:.3f})")
            break
    for target in ("Article 91", "Article 92", "Article 98"):
        rank = next((i for i, m in enumerate(metas, 1)
                     if m["doc"] == "impots_cgi_2026" and m["article"] == target), None)
        print(f"  {target} : rang {rank} sur {n}")