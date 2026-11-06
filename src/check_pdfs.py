from pathlib import Path
from pypdf import PdfReader

for pdf in sorted(Path("data/raw").rglob("*.pdf")):
    reader = PdfReader(pdf)
    nb_pages = len(reader.pages)
    # on teste le texte des 10 premieres pages
    texte = "".join((p.extract_text() or "") for p in reader.pages[:10])
    statut = "OK" if len(texte) > 1000 else "PROBLEME (scan ou vide ?)"
    print(f"{pdf.parent.name}/{pdf.name} | {nb_pages} pages | {len(texte)} caracteres | {statut}")