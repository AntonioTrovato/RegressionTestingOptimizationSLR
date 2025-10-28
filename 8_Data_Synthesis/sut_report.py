#!/usr/bin/env python3
import argparse
import glob
import math
import os
import re
import pandas as pd
from collections import defaultdict

# ---- Columns (0-based) ----
COL_Y  = 24  # paper type
COL_Z  = 25  # method string
COL_AD = 29  # SUT(s) names

# ---- Output category order ----
CATEGORY_ORDER = [
    "SIR",
    "Defects4J",
    "Apache Projects",
    "Industrial / Proprietary",
    "Other Public Repositories",
]

def first_xlsx_in_cwd():
    files = sorted(glob.glob("*.xlsx")) + sorted(glob.glob("*.xls"))
    return files[0] if files else None

def is_empty(x):
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    return str(x).strip() == ""

def split_multi(raw):
    """
    Split multi-valued SUT cells. Supports ; , | / + & · and also colons like 'SIR: grep, flex'.
    Keeps both the full token and sub-tokens so 'SIR: grep' triggers SIR and 'grep'.
    """
    if is_empty(raw):
        return []
    s = str(raw)
    # Normalize separators
    s = s.replace("＆", "&")
    # Also break on " - " and " – " and newlines
    s = s.replace("\n", " ").replace("\r", " ")
    # Split on common separators
    parts = re.split(r"[;,\|/+\u00B7&]+", s)
    tokens = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # If something like 'SIR: grep, flex', keep 'sir' and also 'grep', 'flex'
        if ":" in p:
            lhs, rhs = p.split(":", 1)
            lhs = lhs.strip()
            rhs = rhs.strip()
            if lhs:
                tokens.append(lhs)
            # split rhs again to isolate items after colon
            rhs_parts = re.split(r"[;,\|/+\u00B7&]+", rhs)
            tokens.extend([rp.strip() for rp in rhs_parts if rp.strip()])
        else:
            tokens.append(p)
    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for t in tokens:
        tl = t.strip()
        if tl and tl.lower() not in seen:
            uniq.append(tl)
            seen.add(tl.lower())
    return uniq

def paper_id_from_index(idx0):
    # Excel data row = idx0 + 2; i = row - 1 = idx0 + 1
    return f"paper_{idx0 + 1}"

# ---- Known names (all lowercase for matching) ----

# SIR programs (include common variants)
SIR_PROGRAMS = {
    "print_tokens", "print tokens", "print_tokens 2", "print tokens 2",
    "flex", "grep", "sed", "space", "gzip",
    "nano-xml", "nano xml",
    "xml-security", "xml security",
    "ant", "jtopas", "replace", "schedule", "schedule2", "tcas", "totinfo",
}
SIR_MARKERS = {"sir"}

# Defects4J projects (common subset + aliases)
DEFECTS4J_PROJECTS = {
    "chart", "jfreechart",
    "closure",
    "math", "commons-math", "commons math",
    "lang", "commons-lang", "commons lang",
    "time", "joda-time", "joda time",
    "mockito",
    "cli", "commons-cli", "commons cli",
    "codec", "commons-codec", "commons codec",
    "collections", "commons-collections", "commons collections",
    "compress", "commons-compress", "commons compress",
    "gson", "jsoup", "jxpath",
}
DEFECTS4J_MARKERS = {"defects4j", "defect4j", "defects 4j"}

# Apache umbrella (non-exhaustive; used if not already classified as SIR)
APACHE_PROJECTS = {
    "ant", "jmeter", "tomcat", "camel",
    "commons-math", "commons lang", "commons-lang", "commons-io", "commons io",
    "commons-cli", "commons cli", "commons-codec", "commons codec",
    "commons-collections", "commons collections", "commons-compress", "commons compress",
    "struts", "hadoop", "spark", "jfreechart", "xml-security", "xml security",
}
APACHE_MARKERS = {"apache", "apache software foundation", "asf"}

# Industrial / Proprietary markers
INDUSTRIAL_MARKERS = {
    "industrial", "proprietary", "company", "industry",
    "cisco", "abb", "abb robotics", "omicron", "siemens", "bosch",
    "google open source data set", "google open source dataset",
    "google open-source data set", "google dataset",
}

# Other public repositories (examples + markers)
OTHER_PUBLIC_SET = {
    "nopcommerce", "umbraco", "jedit", "freemind", "k9-mail", "k9 mail",
    "open sudoku", "open-sudoku", "tcp-ci-dataset", "tcp ci dataset",
}
OTHER_PUBLIC_MARKERS = {
    "open source dataset", "public dataset", "dataset pubblico", "open dataset"
}

def to_lc(x: str) -> str:
    return x.strip().lower()

def categorize_sut_tokens(tokens):
    """
    Map SUT tokens to origin categories.
    Priority:
      1) SIR
      2) Defects4J
      3) Apache Projects
      4) Industrial / Proprietary
      5) Other Public Repositories
    A paper can belong to multiple categories.
    """
    cats = set()
    lc_tokens = [to_lc(t) for t in tokens]

    # Helper functions
    def any_token_contains(patterns):
        """True if any token contains any of the given substrings."""
        return any(any(p in tok for p in patterns) for tok in lc_tokens)

    def any_token_equals_or_contains(names):
        """True if any token exactly matches or contains one of the names."""
        return any(any(p == tok or p in tok for p in names) for tok in lc_tokens)

    # --- SIR ---
    if any_token_contains(SIR_MARKERS) or any_token_equals_or_contains(SIR_PROGRAMS):
        cats.add("SIR")

    # --- Defects4J ---
    if any_token_contains(DEFECTS4J_MARKERS) or any_token_equals_or_contains(DEFECTS4J_PROJECTS):
        cats.add("Defects4J")

    # --- Apache Projects ---
    if any_token_contains(APACHE_MARKERS) or any_token_equals_or_contains(APACHE_PROJECTS):
        cats.add("Apache Projects")

    # --- Industrial / Proprietary ---
    if any_token_contains(INDUSTRIAL_MARKERS):
        cats.add("Industrial / Proprietary")

    # --- Other Public Repositories ---
    if any_token_equals_or_contains(OTHER_PUBLIC_SET) or any_token_contains(OTHER_PUBLIC_MARKERS):
        cats.add("Other Public Repositories")

    # Fallback: if tokens exist but none matched
    if not cats and lc_tokens:
        cats.add("Other Public Repositories")

    return cats


def load_df(path):
    df = pd.read_excel(path, header=0)
    if df.shape[1] <= COL_AD:
        df = pd.read_excel(path, header=None)
    return df

def main():
    ap = argparse.ArgumentParser(description="Aggregate SUT origins per method (prioritization/selection) for PS papers.")
    ap.add_argument("-i", "--input", help="Excel file (default: first .xlsx/.xls in folder)")
    args = ap.parse_args()

    in_path = args.input or first_xlsx_in_cwd()
    if not in_path or not os.path.exists(in_path):
        raise FileNotFoundError("No Excel file found. Put it here or pass with -i <file.xlsx>.")

    df = load_df(in_path)

    # Per-method: category -> set(paper_ids)
    per_method = {
        "prioritization": {cat: set() for cat in CATEGORY_ORDER},
        "selection":      {cat: set() for cat in CATEGORY_ORDER},
    }

    for idx, row in df.iterrows():
        try:
            y = row.iloc[COL_Y]
            z = row.iloc[COL_Z]
            ad = row.iloc[COL_AD]  # SUT(s)
        except Exception:
            continue

        if str(y).strip() != "PS":
            continue

        z_str = "" if is_empty(z) else str(z).lower()
        if is_empty(ad):
            continue

        tokens = split_multi(ad)
        cats = categorize_sut_tokens(tokens)
        if not cats:
            continue

        pid = paper_id_from_index(idx)

        if "prioritization" in z_str:
            for c in cats:
                per_method["prioritization"][c].add(pid)
        if "selection" in z_str:
            for c in cats:
                per_method["selection"][c].add(pid)

    # ---- Print output ----
    def print_block(method_name):
        print(method_name)
        cat_map = per_method[method_name]
        for cat in CATEGORY_ORDER:
            papers = sorted(cat_map[cat], key=lambda s: int(s.split("_")[1]))
            if not papers:
                continue
            print(f"{cat} [{len(papers)}] : " + ", ".join(papers))
        print()

    print_block("prioritization")
    print_block("selection")

if __name__ == "__main__":
    main()
