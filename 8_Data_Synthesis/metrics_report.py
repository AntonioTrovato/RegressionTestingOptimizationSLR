#!/usr/bin/env python3
import argparse
import glob
import math
import os
import re
import pandas as pd
from collections import defaultdict

# ---- Column indices (0-based) ----
# Y=24 (paper type), Z=25 (method), AA=26 (taxonomy), AG=32 (metrics)
COL_Y  = 24
COL_Z  = 25
COL_AA = 26
COL_AG = 32

# ---- Taxonomy substrings (per method) ----
# Prioritization taxonomy substrings (lowercase)
PRIO_TAX_KEYS = ["coverage", "requirement", "probability", "distribution",
                 "human", "clustering", "history", "model", "cost", "other"]

# Selection taxonomy substrings (lowercase)
SEL_TAX_KEYS  = ["integer", "data-", "symbolic", "dynamic", "graph",
                 "textual", "sdg", "path", "modification", "firewall",
                 "cluster", "design"]

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
    """Split multi-valued cells on common separators."""
    if is_empty(raw):
        return []
    s = str(raw).replace("＆", "&")
    parts = re.split(r"[;,\|/+\u00B7/&]+", s)  # ; , | / + · & /
    return [p.strip() for p in parts if p.strip()]

def paper_id_from_index(idx0):
    # Excel data row = idx0 + 2; i = row - 1 = idx0 + 1
    return f"paper_{idx0 + 1}"

# ---- Metric normalization (PRIORITIZATION) ----
PRIO_METRIC_CANON = [
    "APFD/NAPFD",
    "Code-Coverage",
    "Number of Faults Detected / FDR",
    "Time-Based / Cost-Aware",
    "Precision/Recall/F-Measure",
    "Execution Time",
    "Other",
]

PRIO_METRIC_PATTERNS = {
    "APFD/NAPFD": [
        r"\bapfd\b", r"\bnapfd\b", r"normalized-?apfd\b", r"\bapfdc\b",
        r"\bapva\b", r"\bafdp\b", r"\bafpd\b",
        r"average percentage (of )?faults detected"
    ],
    "Code-Coverage": [
        r"\bapbc\b", r"\bapsc\b", r"\bapfc\b"
    ],
    "Number of Faults Detected / FDR": [
        r"faults? detected\b", r"\bfdr\b", r"fault detection rate",
        r"high-?severity faults detected early"
    ],
    "Time-Based / Cost-Aware": [
        r"time to first failure|\bttff\b", r"mean fault detection time|\bmtfd\b",
        r"time to risk detection", r"execution cost",
        r"cost-?aware apfdc", r"average percentage of fault detected per cost"
    ],
    "Precision/Recall/F-Measure": [
        r"\bprecision\b", r"\brecall\b", r"f-?measure\b", r"\bf1-?score\b"
    ],
    "Execution Time": [
        r"prioritization execution time", r"time for prioritization",
        r"execution time( per algorithm)?\b"
    ],
    # "Other" will be assigned later when none of the above match OR for listed unique metrics:
}

# Other-list (prioritization) — if these appear, force "Other"
PRIO_OTHER_HINTS = [
    r"kendall tau", r"redundancy rate", r"\bhypervolume\b", r"\bnrpa\b",
    r"\bndcg\b", r"mutation score", r"effectiveness on flaky tests",
    r"\bcode coverage\b", r"first-?fault position", r"target test path finding rate",
    r"hamming distance", r"# ?of test cases executed", r"percentage of suite runned"
]

# ---- Metric normalization (SELECTION) ----
SEL_METRIC_CANON = [
    "Number of Test Cases / Ratio",
    "Time-Based",
    "Precision/Recall/F-Measure",
    "Safety / Fault-Detection Capability",
    "Other",
]

SEL_METRIC_PATTERNS = {
    "Number of Test Cases / Ratio": [
        r"numero test selezionati", r"% ?di test selezionati", r"# ?tests? selected",
        r"selected test ratio", r"test suite reduction"
    ],
    "Time-Based": [
        r"user\+system execution time", r"test suite execution time", r"\btime\b",
        r"\bae time\b", r"\baec time\b", r"execution time"
    ],
    "Precision/Recall/F-Measure": [
        r"\bprecision\b", r"\brecall\b", r"f-?measure\b", r"\bprecision ?%\b"
    ],
    "Safety / Fault-Detection Capability": [
        r"\bsafety\b", r"safety %", r"fault-?detection capability",
        r"fault detection ability", r"number of detected faults",
        r"detection effectiveness"
    ],
    # "Other" handled later
}

SEL_OTHER_HINTS = [
    r"\bhypervolume\b", r"qualitative/?effectiveness", r"time saving percentage",
    r"size of (the )?pareto frontier", r"number of non-?dominated solutions",
    r"memory consumption"
]

def compile_patterns(patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]

PRIO_COMPILED = {
    k: compile_patterns(v) for k, v in PRIO_METRIC_PATTERNS.items()
}
PRIO_OTHER_COMPILED = compile_patterns(PRIO_OTHER_HINTS)

SEL_COMPILED = {
    k: compile_patterns(v) for k, v in SEL_METRIC_PATTERNS.items()
}
SEL_OTHER_COMPILED = compile_patterns(SEL_OTHER_HINTS)

def normalize_metrics_for_prioritization(cell_value):
    """
    Return a set of canonical metric buckets for prioritization, given AG cell text.
    """
    found = set()
    if is_empty(cell_value):
        return found
    text = str(cell_value)
    tokens = split_multi(text) or [text]
    for tok in tokens:
        lt = tok.lower()
        matched_any = False
        # try canonical buckets (except Other)
        for canon, regex_list in PRIO_COMPILED.items():
            for rgx in regex_list:
                if rgx.search(lt):
                    found.add(canon)
                    matched_any = True
                    break
        # if no match, see if it falls into "Other" by hints
        if not matched_any:
            for rgx in PRIO_OTHER_COMPILED:
                if rgx.search(lt):
                    found.add("Other")
                    matched_any = True
                    break
        # still nothing, but token non-empty -> leave unmatched (ignore)
    return found

def normalize_metrics_for_selection(cell_value):
    """
    Return a set of canonical metric buckets for selection, given AG cell text.
    """
    found = set()
    if is_empty(cell_value):
        return found
    text = str(cell_value)
    tokens = split_multi(text) or [text]
    for tok in tokens:
        lt = tok.lower()
        matched_any = False
        for canon, regex_list in SEL_COMPILED.items():
            for rgx in regex_list:
                if rgx.search(lt):
                    found.add(canon)
                    matched_any = True
                    break
        if not matched_any:
            for rgx in SEL_OTHER_COMPILED:
                if rgx.search(lt):
                    found.add("Other")
                    matched_any = True
                    break
        # else ignore unmatched noise
    return found

def match_taxonomy_labels(cell_value, tax_keys):
    s = "" if is_empty(cell_value) else str(cell_value).lower()
    tokens = split_multi(s) or [s]
    found = set()
    for tok in tokens:
        lt = tok.lower()
        for key in tax_keys:
            if key in lt:
                found.add(key)
    return found

def load_df(path):
    df = pd.read_excel(path, header=0)
    # Ensure enough columns; fallback if needed
    if df.shape[1] <= COL_AG:
        df = pd.read_excel(path, header=None)
    return df

def main():
    ap = argparse.ArgumentParser(
        description="Metrics report for PS papers (prioritization/selection): per metric and per (taxonomy × metric)."
    )
    ap.add_argument("-i", "--input", help="Excel file (default: first .xlsx/.xls in folder)")
    args = ap.parse_args()

    in_path = args.input or first_xlsx_in_cwd()
    if not in_path or not os.path.exists(in_path):
        raise FileNotFoundError("No Excel file found. Put it here or pass with -i <file.xlsx>.")

    df = load_df(in_path)

    # Collect containers per method
    methods = {
        "prioritization": {
            "metric_to_papers": defaultdict(list),
            "tax_metric_to_papers": defaultdict(list),
            "tax_keys": PRIO_TAX_KEYS,
            "metric_order": PRIO_METRIC_CANON,
            "norm_metrics_fn": normalize_metrics_for_prioritization
        },
        "selection": {
            "metric_to_papers": defaultdict(list),
            "tax_metric_to_papers": defaultdict(list),
            "tax_keys": SEL_TAX_KEYS,
            "metric_order": SEL_METRIC_CANON,
            "norm_metrics_fn": normalize_metrics_for_selection
        }
    }

    for idx, row in df.iterrows():
        try:
            y = row.iloc[COL_Y]
            z = row.iloc[COL_Z]
            aa = row.iloc[COL_AA]  # taxonomy
            ag = row.iloc[COL_AG]  # metrics
        except Exception:
            continue

        if str(y).strip() != "PS":
            continue

        z_str = "" if is_empty(z) else str(z).lower()
        pid = paper_id_from_index(idx)

        for method_name, cfg in methods.items():
            if method_name not in z_str:
                continue

            # normalize metrics for this method
            metrics = cfg["norm_metrics_fn"](ag)
            if not metrics:
                continue

            # match taxonomies for this method
            taxos = match_taxonomy_labels(aa, cfg["tax_keys"])
            # If no taxonomy matched, we still count the metric in (1), but we skip (taxonomy × metric)
            # as there is no taxonomy label to pair.

            # (1) per-metric listing
            for m in metrics:
                cfg["metric_to_papers"][m].append(pid)

            # (2) taxonomy × metric listing
            for t in sorted(taxos):
                for m in metrics:
                    cfg["tax_metric_to_papers"][(t, m)].append(pid)

    # Deduplicate and sort paper lists
    for mname, cfg in methods.items():
        for k, v in cfg["metric_to_papers"].items():
            cfg["metric_to_papers"][k] = sorted(set(v), key=lambda s: int(s.split("_")[1]))
        for k, v in cfg["tax_metric_to_papers"].items():
            cfg["tax_metric_to_papers"][k] = sorted(set(v), key=lambda s: int(s.split("_")[1]))

    # ---- Print reports ----
    for method_name, cfg in methods.items():
        print(f"\n=== {method_name.upper()} — METRICS ===")
        # Respect requested order, then any extra metrics (unlikely)
        printed_keys = set()
        for canon in cfg["metric_order"]:
            papers = cfg["metric_to_papers"].get(canon, [])
            if papers:
                printed_keys.add(canon)
                print(f"{canon} [{len(papers)}]: " + ", ".join(papers))
        # Print any unexpected bucket names if present
        for canon, papers in sorted(cfg["metric_to_papers"].items()):
            if canon not in printed_keys and papers:
                print(f"{canon} [{len(papers)}]: " + ", ".join(papers))

        print(f"\n=== {method_name.upper()} — TAXONOMY × METRIC ===")
        # Sort by taxonomy then metric (alphabetical), but keep metric order preference
        pairs = list(cfg["tax_metric_to_papers"].keys())
        # Custom sort: taxonomy alpha, then metric by PRIO/SEL order list (fallback alpha)
        order_index = {name: i for i, name in enumerate(cfg["metric_order"])}
        pairs.sort(key=lambda x: (x[0], order_index.get(x[1], 10**6), x[1]))
        # Print
        for (t, m) in pairs:
            papers = cfg["tax_metric_to_papers"][(t, m)]
            if papers:
                print(f"({t}, {m}) [{len(papers)}]: " + ", ".join(papers))

if __name__ == "__main__":
    main()
