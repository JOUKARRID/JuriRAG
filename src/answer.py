import re
import sys
import time
import unicodedata

from llm import ask
from retriever import search

sys.stdout.reconfigure(encoding="utf-8")

SYSTEM = """Tu es un assistant d'information sur le droit du travail et la fiscalité au Maroc.

RÈGLES STRICTES :
1. Réponds UNIQUEMENT à partir des extraits fournis dans <contexte>. N'utilise jamais tes connaissances personnelles pour compléter.
2. Après chaque information, cite l'extrait entre crochets, par exemple [1] ou [2][3].
3. Si les extraits ne contiennent pas la réponse, écris exactement : "Je n'ai pas trouvé cette information dans les documents dont je dispose." puis indique en une phrase quel organisme officiel consulter. N'invente rien.
4. Les extraits viennent de textes officiels (codes) et de guides pratiques. En cas de contradiction, le texte du code l'emporte. Signale la contradiction.
5. Chaque extrait indique la date de son document. Si le document date de 2018 ou avant, précise que l'information est à vérifier car elle peut avoir changé.
6. Réponds en français, de façon claire et simple. Pour une liste de documents, de conditions ou de taux, utilise une liste à puces COMPLÈTE : recopie TOUS les éléments de la liste présents dans l'extrait, sans en omettre. Donne les chiffres importants (taux, seuils, délais, montants) quand ils figurent dans les extraits.
7. N'écris aucun calcul (pas de ×, de + ni de =) et ne convertis aucune unité. Recopie la règle exactement comme elle est écrite dans l'extrait (par exemple "un jour et demi de travail effectif par mois de service"). "Jours de travail effectif" n'est pas la même chose que "jours ouvrables".
8. Mentionne aussi les cas particuliers qui figurent dans l'extrait cité (par exemple une règle différente pour les salariés de moins de dix-huit ans).
9. Si l'extrait renvoie à un autre article pour une information demandée (par exemple un taux) et que cet article n'est pas dans le contexte, dis-le clairement : "Le taux est fixé à l'article X, qui ne figure pas dans mes extraits."
10. Termine par une seule ligne : "Information générale, ne remplace pas un conseil juridique." """

CLASSIFY_SYSTEM = (
    "Tu classes des questions. Réponds par UN SEUL mot, sans ponctuation : "
    "'travail' (droit du travail : contrat, congés, licenciement, salaire, durée du travail, "
    "emploi de salariés étrangers), 'impots' (fiscalité : IR, IS, TVA, auto-entrepreneur, "
    "déclarations, exonérations) ou 'autre' (tout le reste)."
)

# Mots-clés (sans accents) : classification instantanée, sans appeler le modèle
TRAVAIL_KW = ["travail", "salari", "employeur", "licenci", "conge", "contrat", "preavis",
              "smig", "maternit", "embauche", "demission", "indemnite", "visa", "etranger",
              "apprenti", "syndic", "greve", "convention collective", "cdi", "cdd",
              "periode d'essai", "harcelement", "retraite", "heures sup"]
IMPOTS_KW = ["impot", "tva", "taxe", "fiscal", "imposab", "exoner", "auto-entrepreneur",
             "auto entrepreneur", "autoentrepreneur", "bareme", "cgi", "retenue a la source",
             "chiffre d'affaires", "declaration de revenu", "revenu global", "deductib",
             "plus-value", "plus value"]
# Sujets connus mais non couverts par les documents (CNSS retirée du périmètre)
CNSS_KW = ["cnss", "securite sociale", "allocation familiale", "allocations familiales"]

NUM_WORDS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
             "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
             "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20,
             "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60,
             "cent": 100, "mille": 1000}


def _norm(text):
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def classify(question, use_llm=True):
    q = _norm(question)
    t = sum(k in q for k in TRAVAIL_KW)
    i = sum(k in q for k in IMPOTS_KW)
    if t > 0 and i == 0:
        return "travail"
    if i > 0 and t == 0:
        return "impots"
    if not use_llm:
        return "autre"
    # ambigu ou sans mot-clé : on demande au modèle
    out = ask(CLASSIFY_SYSTEM, question, max_tokens=10).strip().lower()
    if "imp" in out:
        return "impots"
    if "travail" in out:
        return "travail"
    return "autre"


def build_context(results):
    blocks = []
    for i, r in enumerate(results, start=1):
        m = r["meta"]
        head = (f"[{i}] {m['doc_title']} | {m['article']} | page PDF {m['page_pdf']} "
                f"| document de {m['date_doc']}")
        blocks.append(f"{head}\n{r['text']}")
    return "\n\n".join(blocks)


def _numbers(text, words=False):
    text = re.sub(r"\[\d+\]", " ", text)                       # renvois [1]
    text = text.replace("\u202f", " ").replace("\xa0", " ")
    text = re.sub(r"(?<=\d)[ .](?=\d{3}(?!\d))", "", text)     # 80 000 ou 80.000 -> 80000
    text = text.replace(",", ".")                              # 1,5 -> 1.5
    nums = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)}
    if words:
        low = _norm(text)
        for w, v in NUM_WORDS.items():
            if re.search(rf"\b{w}\b", low):
                nums.add(float(v))
        if "et demi" in low:
            nums.update({0.5, 1.5})
    return nums


def check_numbers(text, results):
    """Retourne les chiffres de la réponse qui ne figurent pas dans les extraits."""
    body = text.split("Information générale")[0]
    ctx_nums = _numbers(build_context(results), words=True)
    return sorted(n for n in _numbers(body) - ctx_nums if n not in (0.0, 1.0))


def answer(question, domain=None):
    """Retourne (texte_de_la_réponse, liste_des_sources_citées, domaine)."""
    if domain is None:
        q = _norm(question)
        if any(k in q for k in CNSS_KW) and not any(k in q for k in ("visa", "etranger")):
            return ("Cette question relève de la sécurité sociale (CNSS), qui n'est pas encore "
                    "couverte par les documents de l'assistant. Consultez le site officiel de "
                    "la CNSS (cnss.ma).", [], "cnss")
        domain = classify(question)
    if domain == "autre":
        return ("Cette question sort du périmètre de l'assistant (droit du travail et "
                "fiscalité au Maroc).", [], domain)

    results = search(domain, question)
    user = f"<contexte>\n{build_context(results)}\n</contexte>\n\nQuestion : {question}"
    text = ask(SYSTEM, user, max_tokens=2000)

    bad = check_numbers(text, results)
    if bad:
        shown = ", ".join(f"{n:g}" for n in bad)
        text += (f"\n\nATTENTION (vérification automatique) : le ou les chiffres {shown} ne "
                 f"figurent pas tels quels dans les extraits (calcul ou conversion du "
                 f"modèle). Vérifie dans la source citée.")

    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)})
    sources = [results[n - 1] for n in cited if 1 <= n <= len(results)]
    return text, sources, domain


def show(question, domain=None):
    t0 = time.time()
    text, sources, dom = answer(question, domain)
    print("=" * 70)
    print(f"QUESTION : {question}   (domaine : {dom}, {time.time() - t0:.0f}s)")
    print("-" * 70)
    print(text)
    if sources:
        print("\nSources citées :")
        for r in sources:
            m = r["meta"]
            print(f"  - {m['doc_title']} | {m['article']} | page PDF {m['page_pdf']} "
                  f"| document de {m['date_doc']}")


DEMO = [
    "Combien de jours de congé annuel payé après six mois de service ?",
    "Quel est le taux normal de la TVA ?",
    "Quelles pièces fournir pour une première demande de visa de contrat de travail d'étranger ?",
    "Comment est imposé l'auto-entrepreneur ?",
    "Quel est le taux de l'impôt sur le revenu de l'auto-entrepreneur ?",
    "Quel est le montant de la pension de retraite d'un salarié du secteur privé ?",  # piège : dans le domaine, absent des documents
    "Quel est le montant des allocations familiales de la CNSS ?",                    # CNSS : non couverte
    "Quelle est la capitale du Maroc ?",                                              # hors périmètre
]

if __name__ == "__main__":
    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else DEMO
    t_all = time.time()
    for q in questions:
        try:
            show(q)
        except Exception as e:  # une erreur n'arrête pas les questions suivantes
            print("=" * 70)
            print(f"QUESTION : {q}\n  ÉCHEC : {e}")
    print(f"\nTemps total : {time.time() - t_all:.0f}s")