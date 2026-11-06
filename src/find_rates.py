import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Charger les chunks
chunks_path = Path("data/chunks.jsonl")

if not chunks_path.exists():
    print("ERREUR : data/chunks.jsonl introuvable.")
    print("Lance ce script depuis la racine du projet JuriRAG.")
    sys.exit(1)

with open(chunks_path, "r", encoding="utf-8") as f:
    chunks = [json.loads(line) for line in f if line.strip()]

# Garder uniquement le CGI 2026
cgi = [c for c in chunks if c.get("doc") == "impots_cgi_2026"]

print("=" * 65)
print("DIAGNOSTIC DES TAUX AUTO-ENTREPRENEUR")
print("=" * 65)

# Expressions de recherche
article_73 = [
    c for c in cgi
    if "73" in str(c.get("article", ""))
]

auto_pattern = re.compile(
    r"auto[- ]?entrepreneur|auto[- ]?entreprise",
    re.IGNORECASE
)

rate_pattern = re.compile(
    r"(?<!\d)(?:0[,.]5|0[,.]50|1)(?!\d)\s*%",
    re.IGNORECASE
)

# 1. Vérifier les morceaux de l'article 73
print("\n1. MORCEAUX DE L'ARTICLE 73")
print("-" * 65)

print("Nombre de morceaux trouvés :", len(article_73))

for c in article_73:
    print(
        f"\nArticle : {c.get('article')} | "
        f"Page : {c.get('page_pdf')} | "
        f"ID : {c.get('id')}"
    )
    print(c.get("text", "")[:1500])

# 2. Chercher les taux dans les morceaux parlant d'auto-entrepreneur
print("\n\n2. AUTO-ENTREPRENEUR + TAUX")
print("-" * 65)

found = 0

for c in cgi:
    t = c.get("text", "")

    if auto_pattern.search(t) and rate_pattern.search(t):
        found += 1

        print(
            f"\nArticle : {c.get('article')} | "
            f"Page : {c.get('page_pdf')} | "
            f"ID : {c.get('id')}"
        )

        for m in rate_pattern.finditer(t):
            start = max(0, m.start() - 250)
            end = min(len(t), m.end() + 250)

            print("Extrait :", t[start:end].replace("\n", " "))

print("\nTotal :", found, "morceau(x)")

# 3. Chercher tous les taux dans l'article 73
print("\n\n3. TAUX TROUVÉS DANS L'ARTICLE 73")
print("-" * 65)

found_73 = 0

for c in article_73:
    t = c.get("text", "")

    for m in rate_pattern.finditer(t):
        found_73 += 1
        start = max(0, m.start() - 250)
        end = min(len(t), m.end() + 250)

        print(
            f"\nPage : {c.get('page_pdf')} | "
            f"ID : {c.get('id')}"
        )
        print("Extrait :", t[start:end].replace("\n", " "))

print("\nTotal des taux trouvés dans l'article 73 :", found_73)

print("\n" + "=" * 65)
print("FIN DU DIAGNOSTIC")
print("=" * 65)