"""Cohort construction, business-impact labelling and feature engineering."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .decision_intelligence import FAMILY_IDS, consequence_rules, family_weights

DISRUPTION = {"Interruption", "Obscuration", "Destruction", "Degradation"}
SECTORS = {
    "62": "Healthcare", "92": "Public administration", "61": "Education",
    "52": "Finance & insurance", "51": "Information", "54": "Professional services",
    "42": "Retail & wholesale", "44": "Retail & wholesale", "45": "Retail & wholesale",
    "72": "Accommodation & food", "31": "Manufacturing", "32": "Manufacturing",
    "33": "Manufacturing", "48": "Transport & logistics", "49": "Transport & logistics",
    "21": "Energy & utilities", "22": "Energy & utilities", "81": "Other services",
    "56": "Administrative services",
}
SMALL = {"1 to 10", "11 to 100", "101 to 1000", "Small"}
LARGE = {"1001 to 10000", "10001 to 25000", "25001 to 50000", "50001 to 100000",
         "Over 100000", "Large"}
BULK_CAMPAIGN = "MOVEit vulnerability exploited."  # 747 scripted records (2023)


def build_cohort(raw: pd.DataFrame, record_threshold: int = 10_000) -> pd.DataFrame:
    """Apply inclusion rules and attach context, knowledge and outcome fields."""
    df = raw.copy()
    df = df[df["security_incident"].isin(["Confirmed", "Suspected"])]
    df = df[df["year"].between(2000, 2026)]
    df = df[~df["summary"].str.startswith(BULK_CAMPAIGN)]
    df["year"] = df["year"].astype(int)
    df["sector"] = df["industry"].str[:2].map(SECTORS).fillna("Other/unknown")
    df["size"] = np.select([df["employee_count"].isin(SMALL),
                            df["employee_count"].isin(LARGE)], ["Small", "Large"],
                           "Unknown")
    df["region"] = np.where(df["country"].str.contains("US"), "US",
                            np.where(df["country"] == "Unknown", "Unknown", "Non-US"))
    # ---- business-impact outcome (material business impact, MBI)
    avail = df["availability"].fillna("").str.split("|")
    disrupt = avail.apply(lambda v: bool(DISRUPTION & set(v)))
    total = pd.to_numeric(df["data_total"], errors="coerce")
    mass = total >= record_threshold
    known_small = total.notna() & ~mass
    no_conf = ~df["has_confidentiality"].astype(bool) | (df["data_disclosure"] == "No")
    df["disruption"] = disrupt.astype(int)
    df["mass_exposure"] = mass.astype(int)
    df["mbi"] = (disrupt | mass).astype(int)
    df["determined"] = disrupt | mass | known_small | no_conf
    # ---- knowledge base
    kb = np.vstack([family_weights(r) for _, r in df.iterrows()])
    for j, f in enumerate(FAMILY_IDS):
        df[f"kb_{f}"] = kb[:, j]
    df["kb_mapped"] = kb.sum(axis=1) > 0
    cr = pd.DataFrame([consequence_rules(r) for _, r in df.iterrows()], index=df.index)
    return pd.concat([df, cr], axis=1).reset_index(drop=True)


def _multi_hot(series: pd.Series, prefix: str, vocab: list[str]) -> pd.DataFrame:
    sets = series.fillna("").str.split("|").apply(set)
    return pd.DataFrame({f"{prefix}={v}": sets.apply(lambda s: v in s).astype(np.int8)
                         for v in vocab}, index=series.index)


def fit_vocabulary(train: pd.DataFrame, min_count: int = 15) -> dict:
    """Learn the categorical vocabulary from the development period only."""
    cols = ["sector", "size", "region", "actor", "motive", "asset"] + [
        f"{a}_{k}" for a in ("hacking", "malware", "social", "misuse", "error", "physical")
        for k in ("variety", "vector")]
    vocab = {}
    for c in cols:
        counts = train[c].fillna("").str.split("|").explode().value_counts()
        vocab[c] = sorted(v for v, n in counts.items() if v and n >= min_count)
    return vocab


def feature_matrix(df: pd.DataFrame, vocab: dict, knowledge: bool = True) -> pd.DataFrame:
    """Pre-incident context + threat-pattern features (no outcome fields)."""
    parts = [df[[f"act_{a}" for a in ("hacking", "malware", "social", "misuse", "error",
                                      "physical", "environmental", "unknown")]].astype(np.int8)]
    parts += [_multi_hot(df[c], c, v) for c, v in vocab.items()]
    if knowledge:
        parts.append(df[[f"kb_{f}" for f in FAMILY_IDS] +
                        ["kr_disrupt", "kr_mass", "kr_contained"]].astype(float))
    return pd.concat(parts, axis=1)
