import sys

from retriever import search

sys.stdout.reconfigure(encoding="utf-8")

# Étiquettes attendues : vérifiées dans les fichiers quand c'est possible.
# (L'article 98 du CGI est ABROGÉ : le taux normal de TVA est à l'article 99.)
TESTS = [
    ("travail", "Combien de jours de congé annuel payé après six mois de service ?", ["Article 231", "Article 232"]),
    ("travail", "Quelles sont les conditions du licenciement d'un salarié ?", ["Article 35", "Article 39", "Article 52", "Article 61", "Article 62"]),
    ("travail", "Quelle est la durée normale du travail par semaine ?", ["Article 184"]),
    ("travail", "Quelle est la durée du congé de maternité ?", ["Article 152", "Article 154"]),
    ("travail", "Quel est le délai de traitement du visa du contrat de travail d'un salarié étranger ?", ["Article 516", "page 5", "page 3"]),
    ("travail", "Quelles pièces fournir pour une première demande de visa de contrat de travail d'étranger ?", ["page 5"]),
    ("impots", "Quel est le taux normal de la TVA ?", ["Article 99"]),
    ("impots", "Quelles sont les tranches du barème de l'impôt sur le revenu ?", ["Article 73"]),
    ("impots", "Comment est imposé l'auto-entrepreneur ?", ["Article 42 bis", "Article 42 ter"]),
    ("impots", "Quelles opérations sont exonérées de la TVA ?", ["Article 91", "Article 92"]),
]

WEIGHTS = [0, 0.25, 0.5, 1.0]  # 0 = vecteurs seuls, 1 = poids égal
n = len(TESTS)
summary = []

for w in WEIGHTS:
    given = strict = 0
    fails, ranks = [], []
    for domain, question, expected in TESTS:
        res = search(domain, question, bm25_weight=w)
        labels = [r["meta"]["article"] for r in res]
        rank = next((i + 1 for i, l in enumerate(labels) if l in expected), None)
        if rank:
            given += 1
            ranks.append(rank)
            if rank <= 4:
                strict += 1
        else:
            fails.append(question[:55])
    avg = sum(ranks) / len(ranks) if ranks else 0
    summary.append((w, given, strict, avg))
    print(f"\n--- poids BM25 = {w} ---")
    print(f"  bon passage parmi les 8 donnés : {given}/{n} | dans le top 4 : {strict}/{n} | rang moyen : {avg:.1f}")
    for f in fails:
        print("  RATÉ :", f)

print("\n" + "=" * 60)
print("Poids BM25 | parmi les 8 donnés | top 4 | rang moyen")
for w, g, s, a in summary:
    print(f"{w:10} | {g:>10}/{n}       | {s}/{n}   | {a:.1f}")