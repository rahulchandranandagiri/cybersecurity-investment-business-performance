"""Predictive and decision-level evaluation utilities."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from .decision_intelligence import FAMILY_IDS, birr, gl_allocate, profile_weights, risk_shares

FW_COLS = [f"kb_{f}" for f in FAMILY_IDS]


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error with equal-width probability bins."""
    y, p = np.asarray(y), np.asarray(p)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(y[idx == b].mean() - p[idx == b].mean()) * (idx == b).mean()
                     for b in range(bins) if (idx == b).any()))


METRICS = {"ROC-AUC": roc_auc_score, "PR-AUC": average_precision_score,
           "Brier": brier_score_loss, "ECE": ece}


def predictive_table(y: np.ndarray, preds: dict, ref: str, n_boot: int = 2000,
                     seed: int = 42) -> pd.DataFrame:
    """Point estimates, bootstrap 95% CIs and paired AUC tests against `ref`."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    boots = [rng.integers(0, len(y), len(y)) for _ in range(n_boot)]
    boots = [b for b in boots if 0 < y[b].sum() < len(b)]
    rows = []
    for name, p in preds.items():
        row = {"Model": name}
        for m, fn in METRICS.items():
            vals = np.array([fn(y[b], p[b]) for b in boots])
            row[m] = fn(y, p)
            row[f"{m} CI"] = (np.percentile(vals, 2.5), np.percentile(vals, 97.5))
        if name != ref:
            d = np.array([roc_auc_score(y[b], preds[ref][b]) - roc_auc_score(y[b], p[b])
                          for b in boots])
            row["dAUC vs proposed"] = -d.mean()
            row["p (paired bootstrap)"] = max(2 * min((d <= 0).mean(), (d >= 0).mean()),
                                              1 / len(boots))
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------- decision layer
def mbi_pool(E: pd.DataFrame, sector: str, size: str) -> pd.DataFrame:
    """Observed material-impact incidents of a profile that the knowledge base maps."""
    return E[(E["sector"] == sector) & (E["size"] == size) & E["determined"] &
             (E["mbi"] == 1) & E["kb_mapped"]]


def realized_shares(E: pd.DataFrame, sector: str, size: str) -> tuple[np.ndarray, int]:
    """Observed business-impact risk shares of a profile in the evaluation period."""
    m = mbi_pool(E, sector, size)
    mass = m[FW_COLS].to_numpy().sum(axis=0)
    return (mass / mass.sum() if mass.sum() > 0 else mass), len(m)


def strategy_shares(D: pd.DataFrame, impact: np.ndarray, sector: str, size: str,
                    params: dict, ref_year: int) -> np.ndarray:
    w = profile_weights(D, sector, size, params["lam_size"], params["lam_global"],
                        params["half_life"], ref_year)
    return risk_shares(D[FW_COLS].to_numpy(), impact, w)


def profiles(E: pd.DataFrame, min_mbi: int = 10) -> list[tuple[str, str]]:
    ok = E[E["determined"] & (E["mbi"] == 1) & E["kb_mapped"] &
           (E["size"] != "Unknown") & (E["sector"] != "Other/unknown")]
    cnt = ok.groupby(["sector", "size"]).size()
    return [k for k, n in cnt.items() if n >= min_mbi]


def decision_scores(shares: dict, real: dict, budget: float, alpha: float,
                    beta: float) -> pd.DataFrame:
    """BIRR of every strategy (columns) for every profile (rows)."""
    out = {}
    for strat, sh in shares.items():
        out[strat] = {p: birr(real[p], gl_allocate(sh[p], budget, alpha, beta)
                              if strat != "Equal allocation" else
                              np.full(len(FAMILY_IDS), budget / len(FAMILY_IDS)),
                              alpha, beta) for p in real}
    return pd.DataFrame(out)


def bootstrap_birr(E: pd.DataFrame, shares: dict, profs: list, budget: float,
                   alpha: float, beta: float, n_boot: int = 1000, seed: int = 42) -> dict:
    """95% CIs of mean BIRR, resampling evaluation incidents within each profile."""
    rng = np.random.default_rng(seed)
    pools = {p: mbi_pool(E, *p)[FW_COLS].to_numpy() for p in profs}
    alloc = {s: {p: (gl_allocate(sh[p], budget, alpha, beta) if s != "Equal allocation"
                     else np.full(len(FAMILY_IDS), budget / len(FAMILY_IDS)))
                 for p in profs} for s, sh in shares.items()}
    draws = {s: [] for s in shares}
    for _ in range(n_boot):
        real = {}
        for p, X in pools.items():
            mass = X[rng.integers(0, len(X), len(X))].sum(axis=0)
            real[p] = mass / mass.sum()
        for s in shares:
            draws[s].append(np.mean([birr(real[p], alloc[s][p], alpha, beta) for p in profs]))
    return {s: (np.percentile(v, 2.5), np.percentile(v, 97.5)) for s, v in draws.items()}


def paired_test(a: pd.Series, b: pd.Series) -> float:
    diff = (a - b).to_numpy()
    return float(wilcoxon(diff).pvalue) if np.any(diff != 0) else 1.0
