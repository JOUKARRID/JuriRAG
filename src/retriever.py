
import json
import re
import unicodedata
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from config import MODEL, VECTORSTORE


# Documents officiels
CODES = [
    "travail_code_du_travail_2011",
    "impots_cgi_2026",
]

SYNONYMS = [
    (r"\btva\b", "taxe sur la valeur ajoutée"),
    (r"\bir\b", "impôt sur le revenu"),
    (r"\bis\b", "impôt sur les sociétés"),
    (r"\bcgi\b", "code général des impôts"),
    (r"\bsmig\b", "salaire minimum interprofessionnel garanti"),
]

STOP = set("""le la les de des du un une et en a au aux ce ces cet cette que qui quoi quel quelle
quels quelles est sont etre pour par sur dans d l s n y ou se sa son ses leur leurs il elle ils
elles on ne pas plus comme avec sans sous entre vers tout tous toute toutes comment combien quand
peut peuvent doit doivent faut ai as avons ont fait si mais donc car or ni""".split())


# Poids de la recherche BM25
DEFAULT_BM25_WEIGHT = 0.25

_state = {}


def tokenize(text):
    """Nettoie et découpe le texte en mots."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(
        c for c in text
        if unicodedata.category(c) != "Mn"
    )

    out = []

    for t in re.findall(r"[a-z0-9]+", text):
        if t in STOP or len(t) < 2:
            continue

        if len(t) > 3 and t.endswith(("s", "x")):
            t = t[:-1]

        out.append(t)

    return out


def _merge(pieces):
    """Recolle les morceaux d'une même page sans répéter le chevauchement."""

    if not pieces:
        return ""

    out = pieces[0]

    for p in pieces[1:]:
        body = p.split("\n", 1)[1] if "\n" in p else p

        k = min(len(out), len(body), 250)

        while k > 20 and not out.endswith(body[:k]):
            k -= 1

        out += body[k:] if k > 20 else "\n" + body

    return out


def _load():
    """Charge le modèle, ChromaDB et les chunks une seule fois."""

    if _state:
        return

    _state["model"] = SentenceTransformer(MODEL)

    _state["client"] = chromadb.PersistentClient(
        path=VECTORSTORE
    )

    chunks_path = Path("data/chunks.jsonl")

    chunks = [
        json.loads(line)
        for line in chunks_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    by_domain = {}
    pages = {}

    for c in chunks:

        by_domain.setdefault(
            c["domain"], []
        ).append(c)

        # Les guides sont regroupés par document et page/article
        if c["doc"] not in CODES:
            pages.setdefault(
                (c["doc"], c["article"]), []
            ).append(c["text"])

    _state["bm25"] = {
        domain: (
            domain_chunks,
            BM25Okapi([
                tokenize(c["text"])
                for c in domain_chunks
            ])
        )
        for domain, domain_chunks in by_domain.items()
    }

    _state["pages"] = pages
    _state["cache"] = {}


def expand(question):
    """Ajoute des synonymes et des expressions juridiques utiles."""

    extra = []

    # Synonymes généraux
    for pattern, full in SYNONYMS:

        if re.search(pattern, question, re.I):
            if full.lower() not in question.lower():
                extra.append(full)

    # Détection de l'auto-entrepreneur
    is_auto_entrepreneur = re.search(
        r"auto[- ]?entrepreneur|auto[- ]?entreprise",
        question,
        re.I
    )

    asks_rate = re.search(
        r"taux|imp[oô]t|pourcentage|combien|bar[eè]me",
        question,
        re.I
    )

    if is_auto_entrepreneur:

        extra.extend([
            "article 42 bis",
            "chiffre affaires annuel encaissé",
            "régime auto entrepreneur"
        ])

        if asks_rate:
            extra.extend([
                "article 73 paragraphe III",
                "taux spécifique",
                "activités commerciales industrielles artisanales",
                "prestataires de services"
            ])

    # Suppression des répétitions
    extra = list(dict.fromkeys(extra))

    if extra:
        return question + " (" + " ; ".join(extra) + ")"

    return question


def _is_auto_rate_question(domain, question):
    """Détecte une question sur les taux IR de l'auto-entrepreneur."""

    if domain != "impots":
        return False

    is_auto = re.search(
        r"auto[- ]?entrepreneur|auto[- ]?entreprise",
        question,
        re.I
    )

    asks_rate = re.search(
        r"taux|imp[oô]t|pourcentage|combien|bar[eè]me",
        question,
        re.I
    )

    return bool(is_auto and asks_rate)


def search(
    domain,
    question,
    n_code=5,
    n_guide=2,
    pool=30,
    bm25_weight=DEFAULT_BM25_WEIGHT
):
    """
    Recherche hybride :
    - recherche vectorielle avec Sentence Transformers ;
    - recherche par mots-clés avec BM25 ;
    - fusion des classements ;
    - récupération ciblée des taux de l'auto-entrepreneur.

    Retourne une liste de dictionnaires :
    text, meta, kind, score, dist.
    """

    _load()

    if domain not in _state["bm25"]:
        raise ValueError(
            f"Domaine inconnu : {domain}. "
            f"Domaines disponibles : {list(_state['bm25'].keys())}"
        )

    model = _state["model"]
    client = _state["client"]

    chunks, bm25 = _state["bm25"][domain]

    col = client.get_collection(domain)

    by_id = {
        c["id"]: c
        for c in chunks
    }

    # Expansion de la question
    q = expand(question)

    # Calcul et mise en cache
    if q not in _state["cache"]:

        _state["cache"][q] = (
            model.encode(
                "query: " + q,
                normalize_embeddings=True
            ).tolist(),

            bm25.get_scores(
                tokenize(q)
            )
        )

    emb, kw_scores = _state["cache"][q]

    results = []

    # Détection de la question sur les taux
    targeted_auto_rate = _is_auto_rate_question(
        domain,
        question
    )

    for kind, n in (
        ("code", n_code),
        ("guide", n_guide)
    ):

        if n <= 0:
            continue

        is_code = kind == "code"

        # Sélection des chunks du type demandé
        idx = [
            i
            for i, c in enumerate(chunks)
            if (c["doc"] in CODES) == is_code
        ]

        if not idx:
            continue

        n_pool = min(pool, len(idx))

        # Filtrage ChromaDB
        where = (
            {"doc": {"$in": CODES}}
            if is_code
            else {"doc": {"$nin": CODES}}
        )

        res = col.query(
            query_embeddings=[emb],
            n_results=n_pool,
            where=where
        )

        # Classement vectoriel
        dense_rank = {
            cid: rank
            for rank, cid in enumerate(res["ids"][0])
        }

        dense_info = {
            cid: (doc, meta, dist)
            for cid, doc, meta, dist in zip(
                res["ids"][0],
                res["documents"][0],
                res["metadatas"][0],
                res["distances"][0]
            )
        }

        # Classement BM25
        idx.sort(
            key=lambda i: kw_scores[i],
            reverse=True
        )

        kw_rank = {
            chunks[i]["id"]: rank
            for rank, i in enumerate(idx[:pool])
            if kw_scores[i] > 0
        }

        # Fusion des résultats
        fused = {}

        for cid in set(dense_rank) | set(kw_rank):

            score = 0.0

            if cid in dense_rank:
                score += 1 / (60 + dense_rank[cid])

            if cid in kw_rank:
                score += bm25_weight / (60 + kw_rank[cid])

            fused[cid] = score

        # Correction ciblée pour les taux de l'auto-entrepreneur
        if (
            targeted_auto_rate
            and kind == "code"
        ):

            targeted_ids = [
                c["id"]
                for c in chunks
                if (
                    c["doc"] == "impots_cgi_2026"
                    and c["article"] == "Article 73"
                    and c["id"].endswith(
                        ("Article_73:4", "Article_73:5")
                    )
                )
            ]

            # Ajouter les chunks même s'ils ne sont pas
            # présents dans les résultats vectoriels ou BM25.
            max_score = max(
                fused.values(),
                default=0.0
            )

            for rank, cid in enumerate(targeted_ids):

                fused[cid] = max(
                    fused.get(cid, 0.0),
                    max_score + 0.002 - rank * 0.0001
                )

        # Parcours des résultats classés
        seen_pages = set()

        sorted_ids = sorted(
            fused,
            key=fused.get,
            reverse=True
        )

        count = 0

        for cid in sorted_ids:

            if count >= n:
                break

            # Résultat issu de ChromaDB
            if cid in dense_info:

                doc, meta, dist = dense_info[cid]

            else:
                # Résultat ajouté depuis les chunks JSONL
                c = by_id[cid]

                doc = c["text"]
                dist = None

                meta = {
                    k: c.get(k)
                    for k in (
                        "id",
                        "doc",
                        "doc_title",
                        "date_doc",
                        "article",
                        "page_pdf"
                    )
                }

            # Pour les guides : une seule occurrence par page
            # et récupération du texte complet de cette page.
            if kind == "guide":

                key = (
                    meta["doc"],
                    meta["article"]
                )

                if key in seen_pages:
                    continue

                seen_pages.add(key)

                pieces = _state["pages"].get(key)

                if pieces:
                    doc = _merge(pieces)

            results.append({
                "text": doc,
                "meta": meta,
                "kind": kind,
                "score": fused[cid],
                "dist": dist
            })

            count += 1

    return sorted(
        results,
        key=lambda r: r["score"],
        reverse=True
    )
