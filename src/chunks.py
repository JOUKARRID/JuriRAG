import bisect
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROC = Path("data/processed")
OUT = Path("data/chunks.jsonl")
PAGE = re.compile(r"\[\[PAGE (\d+)\]\]")
SUFFIX = r"(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)"
# Titres de chapitre/section/articles annexes, souvent en majuscules.
HEADING_START = re.compile(
    r"(?i)^(?:CHAPITRE|SECTION|SOUS-SECTION|TITRE|LIVRE|PARTIE|ANNEXE)\b"
)

# Code du travail : "Article 41" en debut de ligne
ART_TRAVAIL = re.compile(
    rf"(?mi)^[ \t]*Article[ \t]+(premier|\d+(?:[ \t]*{SUFFIX})?)\b")

# CGI : "Article 26.- ", "Article 26. - ", "Article 169 – ",
#       "Article 45 bis.285- ", "Article 42 bis265.- "
ART_CGI = re.compile(
    rf"(?m)^[ \t]*Article[ \t]+(premier|\d+(?:[ \t]*{SUFFIX})?)"
    rf"[ \t]*\.?[ \t]*\d{{0,4}}[ \t]*\.?[ \t]*[-–—]")

DOCS = {
    "travail_code_du_travail_2011": dict(
        mode="article", pattern=ART_TRAVAIL, repair=True, end_marker=None,
        title="Code du travail (loi 65-99)", date="2011"),
    "impots_cgi_2026": dict(
        mode="article", pattern=ART_CGI, repair=True, end_marker="[[PAGE 530]]",
        title="Code general des impots 2026", date="2026"),
    "impots_guide_tva_2026": dict(
        mode="size", title="Guide TVA Maroc 2026", date="2026"),
    "travail_procedure_salaries_etrangers": dict(
        mode="size",
        title="Procedure d'emploi des salaries etrangers (Ministere du Travail)",
        date="2018-12"),
}

# Lignes de notes de bas de page :
#   "555 Article 6 de la loi de finance n° 76-21", "... pour les années budgétaires 2012 et 2024"
FOOTNOTE_LINE = re.compile(
    r"^\d{1,4}\s+(?:Articles?|Art\.)\s+\d|ann[ée]es?\s+budg[ée]taires?", re.I)
# numero de note colle apres "bis/ter..." : "Article 42 bis265.-" -> "Article 42 bis.-"
NOTE_NUM = re.compile(
    r"(Article\s+\d+\s*(?:bis|ter|quater|quinquies|sexies|septies|octies))"
    r"\.?\s*\d{1,4}(?=\s*[.\-–—])")
# "(abrogé) 549" -> "(abrogé)"
ABROGE_NUM = re.compile(r"\((abrogée?s?)\)\s*\d{1,4}\b", re.I)
# numero de note colle a la fin d'un mot : "farcies540 et" -> "farcies et"
GLUED = re.compile(
    r"(?<=[A-Za-zÀ-ÿ»”;%])(?<!rticle)(?<!RTICLE)\d{2,4}(?=\s|$|[;,.:)])")


def clean_block(txt):
    keep = []
    for line in txt.splitlines():
        s = re.sub(r"[\uf000-\uf8ff]", "-", line).strip()  # puces parasites
        if (not s or re.fullmatch(r"\d{1,3}", s) or s.startswith("[[PAGE")
                or s.upper() == "CODE GÉNÉRAL DES IMPÔTS"):
            continue
        if FOOTNOTE_LINE.search(s):  # ligne de note de bas de page
            continue
        s = ABROGE_NUM.sub(r"(\1)", s)
        s = NOTE_NUM.sub(r"\1", s)
        s = GLUED.sub("", s)
        keep.append(s)
    return "\n".join(keep)


def is_heading(line):
    s = line.strip()
    if HEADING_START.match(s):
        return True
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and len(s) < 120 and all(c.isupper() for c in letters)


def strip_trailing_headings(body):
    """Retire les titres de chapitre/section qui terminent un article (ils appartiennent au suivant)."""
    lines = body.split("\n")
    while len(lines) > 1 and is_heading(lines[-1]):
        lines.pop()
    return "\n".join(lines)


def split_long(text, size, overlap):
    if len(text) <= size:
        return [text]
    parts, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind("\n", start + size // 2, end)
            if cut != -1:
                end = cut
        piece = text[start:end].strip()
        if piece:
            parts.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
        if start > 0 and text[start - 1] not in " \n":  # pas de debut au milieu d'un mot
            nxt = text.find(" ", start)
            if nxt != -1 and nxt - start < 40:
                start = nxt + 1
    return parts


def parse_label(raw, last, repair):
    """Retourne (numero, suffixe). Corrige les notes collees : 47290 -> 47."""
    if raw.lower() == "premier":
        return 1, ""
    mm = re.fullmatch(r"(\d+)\s*([A-Za-z]*)", raw.strip())
    digits, suffix = mm.group(1), mm.group(2).lower()
    n = int(digits)
    if (repair and last is not None and len(digits) >= 4
            and not (last - 3 <= n <= last + 10)):
        for k in range(len(digits) - 1, 0, -1):
            cand = int(digits[:k])
            if last - 3 <= cand <= last + 10:
                n = cand
                break
    return n, suffix


def make(stem, cfg, label, page, text, j):
    return {
        "id": f"{stem}:{label.replace(' ', '_')}:{j}",
        "domain": "travail" if stem.startswith("travail") else "impots",
        "doc": stem,
        "doc_title": cfg["title"],
        "date_doc": cfg["date"],
        "article": label,
        "page_pdf": page,
        "text": f"[{cfg['title']} | {label}]\n{text}",
    }


def chunk_articles(stem, cfg, text):
    if cfg["end_marker"]:
        i = text.find(cfg["end_marker"])
        if i != -1:
            text = text[:i]
    pages = [(m.start(), int(m.group(1))) for m in PAGE.finditer(text)]
    starts = [p[0] for p in pages]

    def page_at(pos):
        i = bisect.bisect_right(starts, pos) - 1
        return pages[i][1] if i >= 0 else 0

    bounds, seen, dups, last = [], set(), [], None
    for m in cfg["pattern"].finditer(text):
        n, suf = parse_label(m.group(1), last, cfg["repair"])
        label = f"Article {n}" + (f" {suf}" if suf else "")
        if label in seen:
            dups.append(label)
            continue
        seen.add(label)
        last = n
        bounds.append((m.start(), label, n))

    chunks = []
    for i, (pos, label, n) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else len(text)
        body = strip_trailing_headings(clean_block(text[pos:end]))
        if len(body) < 20 or (re.search(r"abrog", body, re.I) and len(body) < 200):
            continue  # article vide ou abroge
        for j, piece in enumerate(split_long(body, 1800, 200)):
            chunks.append(make(stem, cfg, label, page_at(pos), piece, j))

    nums = {n for _, _, n in bounds}
    top = max(n for n in nums if n < 700)
    missing = [k for k in range(1, top + 1) if k not in nums]
    print(f"  articles : {len(bounds)} | doublons ignores : {len(dups)} {dups[:5]}")
    print(f"  numeros absents : {len(missing)} {missing[:40]}")
    return chunks


def chunk_pages(stem, cfg, text):
    parts = PAGE.split(text)
    chunks = []
    for num, body in zip(parts[1::2], parts[2::2]):
        body = clean_block(body)
        if len(body) < 80:
            continue
        for j, piece in enumerate(split_long(body, 1200, 150)):
            chunks.append(make(stem, cfg, f"page {num}", int(num), piece, j))
    return chunks


all_chunks = []
for stem, cfg in DOCS.items():
    path = next(PROC.rglob(f"{stem}.txt"), None)
    if path is None:
        print(f"{stem} : FICHIER INTROUVABLE (lance d'abord extract_text.py)")
        continue
    text = path.read_text(encoding="utf-8")
    print(f"\n== {stem} ==")
    if cfg["mode"] == "article":
        chunks = chunk_articles(stem, cfg, text)
    else:
        chunks = chunk_pages(stem, cfg, text)
    lens = [len(c["text"]) for c in chunks]
    print(f"  chunks : {len(chunks)} | longueur moyenne : {sum(lens) // len(lens)} | max : {max(lens)}")
    print("  exemple :", repr(chunks[len(chunks) // 2]["text"][:200]))
    all_chunks += chunks

# identifiants uniques (securite)
counts = {}
for c in all_chunks:
    k = c["id"]
    if k in counts:
        counts[k] += 1
        c["id"] = f"{k}#{counts[k]}"
    else:
        counts[k] = 0

with OUT.open("w", encoding="utf-8") as f:
    for c in all_chunks:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
print(f"\nTOTAL : {len(all_chunks)} chunks ecrits dans {OUT}")
