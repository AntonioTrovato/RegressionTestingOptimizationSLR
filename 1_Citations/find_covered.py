#!/usr/bin/env python3
"""
Script per trovare l'intersezione tra i paper della lista attuale e quelli
della tornata precedente (old), per ciascun database (ACM, IEEE, ScienceDirect).

Uso:
    python find_covered.py [percorso_cartella_1_Citations]

Se non viene passato un argomento, usa la cartella corrente.

Per ogni database DB (ACM, IEEE, ScienceDirect) lo script si aspetta:
    1_Citations/DB/DB.bib
    1_Citations/DB/old/DB.bib

e produce:
    1_Citations/DB/Covered{DB}.bib

contenente le entry BibTeX presenti sia nel file attuale che in quello old
(match basato sul DOI quando disponibile, altrimenti sul titolo normalizzato).
"""

import os
import re
import sys

DATABASES = ["ACM", "IEEE", "ScienceDirect"]


def split_entries(text):
    """Divide il contenuto di un file .bib in una lista di entry (stringhe),
    ognuna a partire da '@' fino alla entry successiva."""
    # Trova tutte le posizioni che iniziano una entry (@qualcosa{...)
    starts = [m.start() for m in re.finditer(r'@\w+\s*\{', text)]
    entries = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        entry = text[start:end].strip()
        if entry:
            entries.append(entry)
    return entries


def extract_field(entry, field):
    """Estrae il valore di un campo (es. doi, title) da una entry BibTeX.
    Gestisce valori delimitati da {} o da "" ."""
    pattern = re.compile(
        r'\b' + re.escape(field) + r'\s*=\s*(\{|")',
        re.IGNORECASE,
    )
    m = pattern.search(entry)
    if not m:
        return None

    open_char = m.group(1)
    start = m.end()

    if open_char == '"':
        end = entry.find('"', start)
        if end == -1:
            return None
        return entry[start:end].strip()

    # open_char == '{': bisogna gestire graffe annidate
    depth = 1
    i = start
    while i < len(entry) and depth > 0:
        if entry[i] == '{':
            depth += 1
        elif entry[i] == '}':
            depth -= 1
        i += 1
    return entry[start:i - 1].strip()


def normalize_title(title):
    if not title:
        return None
    t = title.lower()
    t = re.sub(r'[{}\\]', '', t)          # rimuove graffe e backslash (accenti bibtex, ecc.)
    t = re.sub(r'[^a-z0-9]+', ' ', t)      # tiene solo lettere/numeri
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def normalize_doi(doi):
    if not doi:
        return None
    d = doi.lower().strip()
    d = re.sub(r'^https?://(dx\.)?doi\.org/', '', d)
    d = re.sub(r'^doi:\s*', '', d)
    return d.strip()


def entry_key(entry):
    """Restituisce una chiave univoca per il confronto: preferisce il DOI,
    altrimenti usa il titolo normalizzato."""
    doi = normalize_doi(extract_field(entry, "doi"))
    if doi:
        return ("doi", doi)
    title = normalize_title(extract_field(entry, "title"))
    if title:
        return ("title", title)
    return None


def load_entries(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return split_entries(text)


def process_database(citations_dir, db):
    current_path = os.path.join(citations_dir, db, f"{db}.bib")
    old_path = os.path.join(citations_dir, db, "old", f"{db}.bib")
    output_path = os.path.join(citations_dir, db, f"Covered{db}.bib")

    if not os.path.isfile(current_path):
        print(f"[{db}] SKIP: file attuale non trovato -> {current_path}")
        return
    if not os.path.isfile(old_path):
        print(f"[{db}] SKIP: file old non trovato -> {old_path}")
        return

    current_entries = load_entries(current_path)
    old_entries = load_entries(old_path)

    # Costruisce l'insieme delle chiavi presenti nel file old
    old_keys = set()
    for e in old_entries:
        k = entry_key(e)
        if k:
            old_keys.add(k)

    covered = []
    seen = set()
    for e in current_entries:
        k = entry_key(e)
        if k and k in old_keys and k not in seen:
            covered.append(e)
            seen.add(k)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(covered))
        if covered:
            f.write("\n")

    print(
        f"[{db}] attuale={len(current_entries)} old={len(old_entries)} "
        f"intersezione={len(covered)} -> {output_path}"
    )


def main():
    citations_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    citations_dir = os.path.abspath(citations_dir)

    if not os.path.isdir(citations_dir):
        print(f"Cartella non trovata: {citations_dir}")
        sys.exit(1)

    print(f"Cartella 1_Citations: {citations_dir}\n")

    for db in DATABASES:
        process_database(citations_dir, db)


if __name__ == "__main__":
    main()