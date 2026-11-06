import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def page_of(text, pos):
    i = text.rfind("[[PAGE ", 0, pos)
    return text[i + 7:text.find("]]", i)] if i != -1 else "?"


cgi = Path("data/processed/impots/impots_cgi_2026.txt").read_text(encoding="utf-8")
body = cgi[:cgi.find("[[PAGE 530]]")]

print("=== 'Article 98' dans le CGI (avant les annexes) ===")
hits = list(re.finditer(r"Article\s*98\b", body))
print(len(hits), "occurrence(s)")
for h in hits[:4]:
    print(f"\n  page {page_of(body, h.start())} :")
    print("  ", repr(body[max(0, h.start() - 150):h.start() + 350]))

print("\n=== 'taux normal' pres de 'valeur ajoutee' dans le CGI ===")
shown = 0
for h in re.finditer(r"taux\s+normal", body, re.I):
    ctx = body[max(0, h.start() - 300):h.start() + 300]
    if re.search(r"valeur\s+ajout", ctx, re.I):
        print(f"\n  page {page_of(body, h.start())} :")
        print("  ", repr(body[max(0, h.start() - 150):h.start() + 250]))
        shown += 1
        if shown == 4:
            break

chunks = [json.loads(l) for l in open("data/chunks.jsonl", encoding="utf-8")]
cgi_chunks = [c for c in chunks if c["doc"] == "impots_cgi_2026"]
labels = [c["article"] for c in cgi_chunks]
print("\n=== chunks voisins dans chunks.jsonl ===")
for t in ("Article 96", "Article 97", "Article 98", "Article 99"):
    print(f"  {t} : {labels.count(t)} chunk(s)")

print("\n=== chunks qui citent 'Article 98' sans etre l'article 98 ===")
n = 0
for c in cgi_chunks:
    i = c["text"].find("Article 98")
    if i != -1 and c["article"] != "Article 98":
        print(f"  dans {c['article']} (p.{c['page_pdf']}) :", repr(c["text"][max(0, i - 100):i + 250]))
        n += 1
        if n == 3:
            break

guide = Path("data/processed/impots/impots_guide_tva_2026.txt").read_text(encoding="utf-8")
print("\n=== Guide TVA : passages avec 'taux normal' ===")
for h in list(re.finditer(r"taux\s+normal", guide, re.I))[:5]:
    print(f"\n  page {page_of(guide, h.start())} :")
    print("  ", repr(guide[max(0, h.start() - 100):h.start() + 250]))