import re
import sys
from pathlib import Path

from pypdf import PdfReader

sys.stdout.reconfigure(encoding="utf-8")

RAW, OCR, OUT = Path("data/raw"), Path("data/ocr"), Path("data/processed")

# Pages (numerotation d'origine) a ignorer : captures, formulaires, annexes a remplir
SKIP_PAGES = {"travail_procedure_salaries_etrangers": {12, 13, 14, 16, 22, 23, 24}}

ARTICLE = re.compile(r"(?m)^\s*Article\s+(\d+(?:\s*(?:bis|ter|quater))?)", re.I)
HEADER = re.compile(r"PROC[EÉ]DURE D.EMPLOI DES SALARI[EÉ]S [EÉ]TRANGERS AU MAROC", re.I)
ORIG_MARK = re.compile(r"\[{0,2}PAGE ORIGINALE\s+(\d+)\]{0,2}", re.I)
APOS = re.compile(
    r"\b([dl])(un|une|autorisation|attestation|activit[eé]|octroi|employeur|"
    r"article|autorit[eé]|administration|emploi|[eé]tranger|entreprise)\b", re.I)


def clean(text):
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if len(s) >= 5:  # supprime les lignes de charabia (symboles en exces)
            ok = sum(ch.isalnum() or ch in " '’.,;:-()%/" for ch in s)
            if ok / len(s) < 0.8:
                continue
        lines.append(APOS.sub(r"\1'\2", s))
    return "\n".join(lines)


def process_marked_text(raw, stem):
    """Texte OCR contenant deja des marqueurs [[PAGE n]] : nettoyage page par page."""
    raw = HEADER.sub("\n", raw)
    parts = re.split(r"\[\[PAGE (\d+)\]\]", raw)  # ['', '1', texte1, '2', texte2, ...]
    out = []
    for num, body in zip(parts[1::2], parts[2::2]):
        if int(num) in SKIP_PAGES.get(stem, set()):
            continue
        out.append(f"\n[[PAGE {num}]]\n{clean(body)}")
    return "".join(out)


for pdf in sorted(RAW.rglob("*.pdf")):
    stem = pdf.stem
    print("Traitement :", stem, flush=True)
    ocr_file = OCR / f"{stem}.txt"

    if ocr_file.exists():
        raw_text = ORIG_MARK.sub(r"\n[[PAGE \1]]\n", ocr_file.read_text(encoding="utf-8"))
        full, source = process_marked_text(raw_text, stem), "fichier OCR .txt"
    else:
        reader = PdfReader(pdf)
        pages = [p.extract_text() or "" for p in reader.pages]
        joined = ORIG_MARK.sub(r"\n[[PAGE \1]]\n", "\n".join(pages))
        if "[[PAGE" in joined:  # couche texte issue d'un OCR avec marqueurs de page
            full, source = process_marked_text(joined, stem), "PDF + marqueurs OCR"
        else:
            full = "".join(f"\n[[PAGE {i}]]\n{t}" for i, t in enumerate(pages, start=1))
            source = "PDF"

    if len(full.strip()) < 1000:
        print(f"  SAUTE (vide ou scan) : {pdf.name}")
        continue

    dest = OUT / pdf.parent.name / (stem + ".txt")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(full, encoding="utf-8")
    nb = len(ARTICLE.findall(full))
    print(f"  [{source}] {len(full)} caracteres, {nb} 'Article N' detectes")