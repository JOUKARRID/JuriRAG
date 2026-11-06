import sys

from retriever import search

sys.stdout.reconfigure(encoding="utf-8")

domain = sys.argv[1]
question = " ".join(sys.argv[2:])
for i, r in enumerate(search(domain, question), start=1):
    m = r["meta"]
    print(f"\n[{i}] {m['article']} | p.{m['page_pdf']} | {r['kind']}")
    print(r["text"][:900])