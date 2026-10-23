"""Run the full KB-CIDS study and regenerate every table, figure and summary.

    python run_experiment.py            # full run (about 5-10 minutes on a laptop)
    python run_experiment.py --quick    # fewer bootstrap draws, for smoke tests

Outputs are written to results/ (tables/*.csv, figures/*.png|pdf, summary.json).
"""
from __future__ import annotations

import argparse
import itertools
import json
import platform
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn

from src.data_loader import VCDB_COMMIT, load_vcdb
from src.decision_intelligence import (FAMILIES, FAMILY_IDS, RULES, birr, gl_allocate,
                                       profile_weights)
from src.evaluation import (bootstrap_birr, decision_scores, paired_test, predictive_table,
                            profiles, realized_shares, strategy_shares)
from src.explainability import (allocation_rationale, figure_1, figure_2,
                                graphical_abstract, grouped_importance)
from src.models import kb_risk_model, model_zoo
from src.preprocessing import build_cohort, feature_matrix, fit_vocabulary

warnings.filterwarnings("ignore", category=UserWarning)
OUT = Path("results")
BUDGET, ALPHA, BETA = 9.0, 1.0, 1.0          # one investment unit per family = B_ref
GRID = {"lam_size": [0.25, 0.5, 1.0], "lam_global": [0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0],
        "half_life": [np.inf, 0.5, 1, 2, 4, 8]}
PROPOSED = "KB-CIDS (full)"
STRATEGIES = {  # impact source, context weighting, recency weighting
    "Threat frequency (pooled)": ("all", False, False),
    "Threat frequency (context)": ("all", True, True),
    "Impact-aligned (pooled)": ("obs", False, False),
    "KB-CIDS w/o context": ("ai", False, True),
    "KB-CIDS w/o recency": ("ai", True, False),
    "KB-CIDS w/o AI imputation": ("obs", True, True),
    PROPOSED: ("ai", True, True),
}


def impact_sources(D: pd.DataFrame) -> dict:
    """Per-incident impact weights: all incidents, observed MBI, or AI-imputed MBI."""
    det = D["determined"].to_numpy()
    X = feature_matrix(D, fit_vocabulary(D), knowledge=True)
    model = kb_risk_model().fit(X[det], D["mbi"].to_numpy()[det])
    p = model.predict_proba(X)[:, 1]
    obs = np.where(det, D["mbi"], 0.0)
    return {"all": np.ones(len(D)), "obs": obs, "ai": np.where(det, D["mbi"], p)}


def candidate_params(context: bool, recency: bool) -> list[dict]:
    ls = GRID["lam_size"] if context else [1.0]
    lg = GRID["lam_global"] if context else [np.inf]
    hl = GRID["half_life"] if recency else [np.inf]
    return [dict(lam_size=a, lam_global=b, half_life=c) for a, b, c in itertools.product(ls, lg, hl)]


def tune(D1: pd.DataFrame, D2: pd.DataFrame, min_mbi: int = 5) -> tuple[dict, pd.DataFrame]:
    """Select each strategy's weighting parameters on the inner validation split."""
    imp, ref = impact_sources(D1), int(D1["year"].max())
    profs = profiles(D2, min_mbi)
    real = {p: realized_shares(D2, *p)[0] for p in profs}
    best, log = {}, []
    for name, (src, ctx, rec) in STRATEGIES.items():
        scored = []
        for prm in candidate_params(ctx, rec):
            val = np.mean([birr(real[p], gl_allocate(strategy_shares(D1, imp[src], *p, prm, ref),
                                                     BUDGET, ALPHA, BETA), ALPHA, BETA) for p in profs])
            scored.append((val, prm))
            log.append({"strategy": name, **prm, "validation_BIRR": val})
        best[name] = max(scored, key=lambda t: t[0])[1]
    return best, pd.DataFrame(log)


def evaluate(D: pd.DataFrame, E: pd.DataFrame, params: dict, min_mbi: int = 10,
             imp: dict | None = None) -> dict:
    """Out-of-time decision evaluation of all strategies at the reference budget."""
    imp = imp or impact_sources(D)
    ref = int(D["year"].max())
    profs = profiles(E, min_mbi)
    real = {p: realized_shares(E, *p)[0] for p in profs}
    shares = {"Equal allocation": {p: np.full(len(FAMILY_IDS), 1 / len(FAMILY_IDS)) for p in profs}}
    for name, (src, _, _) in STRATEGIES.items():
        shares[name] = {p: strategy_shares(D, imp[src], *p, params[name], ref) for p in profs}
    shares["Oracle (ex post)"] = real
    scores = decision_scores(shares, real, BUDGET, ALPHA, BETA)
    return {"profiles": profs, "real": real, "shares": shares, "scores": scores, "imp": imp}


def decision_table(res: dict, E: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    sc = res["scores"]
    ci = bootstrap_birr(E, res["shares"], res["profiles"], BUDGET, ALPHA, BETA, n_boot)
    eq, orc = sc["Equal allocation"].mean(), sc["Oracle (ex post)"].mean()
    rows = []
    for s in sc.columns:
        rows.append({
            "Strategy": s, "Mean BIRR": sc[s].mean(), "BIRR 95% CI": ci[s],
            "Delta vs equal (pp)": 100 * (sc[s].mean() - eq),
            "Oracle gap closed (%)": 100 * (sc[s].mean() - eq) / (orc - eq),
            "Profiles better than equal": int((sc[s] > sc["Equal allocation"] + 1e-12).sum()),
            "Wilcoxon p vs equal": paired_test(sc[s], sc["Equal allocation"])
            if s != "Equal allocation" else np.nan,
            "Wilcoxon p vs KB-CIDS": paired_test(sc[PROPOSED], sc[s]) if s != PROPOSED else np.nan,
        })
    return pd.DataFrame(rows)


def split(df: pd.DataFrame, split_year: int):
    D = df[df["year"] <= split_year].reset_index(drop=True)
    E = df[df["year"] > split_year].reset_index(drop=True)
    D1 = D[D["year"] <= split_year - 2].reset_index(drop=True)
    D2 = D[D["year"] > split_year - 2].reset_index(drop=True)
    return D, E, D1, D2


def predictive_study(D: pd.DataFrame, E: pd.DataFrame, n_boot: int) -> tuple:
    vocab = fit_vocabulary(D)
    XD, XE = feature_matrix(D, vocab, True), feature_matrix(E, vocab, True)
    raw = [c for c in XD.columns if not c.startswith(("kb_", "kr_"))]
    dD, dE = D["determined"].to_numpy(), E["determined"].to_numpy()
    yD, yE = D["mbi"].to_numpy()[dD], E["mbi"].to_numpy()[dE]
    preds, fitted = {}, {}
    for name, (est, know) in model_zoo().items():
        cols = list(XD.columns) if know else raw
        est.fit(XD.loc[dD, cols], yD)
        preds[name] = est.predict_proba(XE.loc[dE, cols])[:, 1]
        fitted[name] = (est, cols)
    ref = list(preds)[-1]
    return predictive_table(yE, preds, ref, n_boot), preds, fitted, XE.loc[dE], yE


def run_scenario(df: pd.DataFrame, split_year: int, min_mbi: int) -> dict:
    D, E, D1, D2 = split(df, split_year)
    params, _ = tune(D1, D2)
    res = evaluate(D, E, params, min_mbi)
    sc = res["scores"]
    eq, orc = sc["Equal allocation"].mean(), sc["Oracle (ex post)"].mean()
    out = {s: sc[s].mean() for s in sc.columns}
    out["KB-CIDS gap closed (%)"] = 100 * (sc[PROPOSED].mean() - eq) / (orc - eq)
    out["Profiles"] = len(res["profiles"])
    out["p (KB-CIDS vs threat frequency)"] = paired_test(sc[PROPOSED], sc["Threat frequency (context)"])
    return out


def fmt_ci(t) -> str:
    return f"[{t[0]:.3f}, {t[1]:.3f}]"


def main(quick: bool = False) -> None:
    t0 = time.time()
    n_boot = 200 if quick else 2000
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)

    raw = load_vcdb("data")
    df = build_cohort(raw)
    D, E, D1, D2 = split(df, 2016)
    print(f"cohort={len(df)}  development={len(D)}  evaluation={len(E)}")

    # ---------------- Table 1: out-of-time predictive validity of materiality models
    t1, preds, fitted, XE, yE = predictive_study(D, E, n_boot)
    t1_out = t1.copy()
    for m in ("ROC-AUC", "PR-AUC", "Brier", "ECE"):
        t1_out[f"{m} CI"] = t1_out[f"{m} CI"].apply(fmt_ci)
    t1_out.to_csv(OUT / "tables" / "Table_1_predictive_validity.csv", index=False)
    print(t1[["Model", "ROC-AUC", "PR-AUC", "Brier", "ECE"]].round(3).to_string(index=False))

    # ---------------- Decision layer: tune on 2000-2014 -> 2015-2016, test on 2017-2026
    params, tuning_log = tune(D1, D2)
    tuning_log.to_csv(OUT / "tables" / "S3_validation_tuning.csv", index=False)
    res = evaluate(D, E, params)
    t2 = decision_table(res, E, n_boot // 2)
    t2_out = t2.copy()
    t2_out["BIRR 95% CI"] = t2_out["BIRR 95% CI"].apply(fmt_ci)
    t2_out.to_csv(OUT / "tables" / "Table_2_decision_performance.csv", index=False)
    print(t2.drop(columns=["BIRR 95% CI"]).round(4).to_string(index=False))
    sc = res["scores"].copy()
    sc.index = [f"{a} | {b}" for a, b in sc.index]
    sc.to_csv(OUT / "tables" / "S2_profile_scores.csv")

    # ---------------- Budget curve (Figure 2a) and alpha/beta sensitivity
    budgets = BUDGET * np.geomspace(0.1, 10, 25)
    rows = []
    for b in budgets:
        s = decision_scores(res["shares"], res["real"], b, ALPHA, BETA).mean().to_dict()
        lo, hi = bootstrap_birr(E, {PROPOSED: res["shares"][PROPOSED]}, res["profiles"], b,
                                ALPHA, BETA, n_boot // 4)[PROPOSED]
        rows.append({"budget": b, **s, f"{PROPOSED} lo": lo, f"{PROPOSED} hi": hi})
    curve = pd.DataFrame(rows)
    curve.to_csv(OUT / "tables" / "S4_budget_curve.csv", index=False)
    sens = []
    for a, bt in itertools.product([0.5, 1.0, 2.0], [1.0, 2.0, 3.0]):
        s = decision_scores(res["shares"], res["real"], BUDGET, a, bt).mean()
        sens.append({"alpha": a, "beta": bt, **s.to_dict(), "KB-CIDS gap closed (%)": 100 * (
            s[PROPOSED] - s["Equal allocation"]) / (s["Oracle (ex post)"] - s["Equal allocation"])})
    pd.DataFrame(sens).to_csv(OUT / "tables" / "S5_sensitivity_alpha_beta.csv", index=False)

    # ---------------- Robustness scenarios (Table S6)
    robust = {"Main specification": run_scenario(df, 2016, 10)}
    robust["Record threshold 100,000"] = run_scenario(
        build_cohort(raw, record_threshold=100_000), 2016, 10)
    robust["Excluding non-random sub-sources"] = run_scenario(
        df[df["sub_source"].isna()].reset_index(drop=True), 2016, 10)
    robust["Split year 2015"] = run_scenario(df, 2015, 10)
    robust["Split year 2017"] = run_scenario(df, 2017, 10)
    robust["Profiles with >= 5 material incidents"] = run_scenario(df, 2016, 5)
    pd.DataFrame(robust).T.to_csv(OUT / "tables" / "S6_robustness.csv")

    # ---------------- Explainability
    model, cols = fitted[list(fitted)[-1]]
    imp_tab = grouped_importance(model, XE[cols], yE)
    imp_tab.to_csv(OUT / "tables" / "S7_permutation_importance.csv", index=False)
    example = ("Healthcare", "Small")
    w = profile_weights(D, *example, **params[PROPOSED], ref_year=int(D["year"].max()))
    allocation_rationale(D, res["imp"]["ai"], w).to_csv(
        OUT / "tables" / "S8_allocation_rationale_healthcare_small.csv", index=False)
    alloc = {k: {p: gl_allocate(res["shares"][s][p], BUDGET, ALPHA, BETA) / BUDGET
                 for p in res["profiles"]}
             for k, s in (("freq", "Threat frequency (context)"), ("kb", PROPOSED))}
    pd.DataFrame([{"profile": f"{p[0]} | {p[1]}", "strategy": k, **dict(zip(FAMILY_IDS, v[p]))}
                  for k, v in alloc.items() for p in res["profiles"]] +
                 [{"profile": f"{p[0]} | {p[1]}", "strategy": "realized",
                   **dict(zip(FAMILY_IDS, res["real"][p]))} for p in res["profiles"]]
                 ).to_csv(OUT / "tables" / "S9_allocations.csv", index=False)
    pd.DataFrame(RULES, columns=["rule", "scope", "condition", "family/consequence"]).to_csv(
        OUT / "tables" / "S1_knowledge_base.csv", index=False)
    pd.DataFrame(FAMILIES, columns=["family", "name", "CIS v8 / NIST CSF 2.0"]).to_csv(
        OUT / "tables" / "S1b_control_families.csv", index=False)

    # ---------------- Figures
    figure_1(alloc, res["real"], res["profiles"], str(OUT / "figures" / "Figure_1"))
    figure_2(curve, res["scores"], BUDGET, str(OUT / "figures" / "Figure_2"))
    t2i = t2.set_index("Strategy")
    stats = {"n_incidents": len(df), "n_sectors": int(df["sector"].nunique() - 1),
             "auc": float(t1["ROC-AUC"].iloc[-1]), "n_rules": 22,
             "birr_kb": float(t2i.loc[PROPOSED, "Mean BIRR"]),
             "birr_freq": float(t2i.loc["Threat frequency (context)", "Mean BIRR"]),
             "birr_eq": float(t2i.loc["Equal allocation", "Mean BIRR"])}
    graphical_abstract(stats, str(OUT / "figures" / "Graphical_abstract"))

    # ---------------- Summary for the manuscript
    summary = {
        "vcdb_commit": VCDB_COMMIT, "cohort": len(df), "development": len(D), "evaluation": len(E),
        "development_determined": int(D["determined"].sum()),
        "evaluation_determined": int(E["determined"].sum()),
        "mbi_rate_development": float(D.loc[D["determined"], "mbi"].mean()),
        "mbi_rate_evaluation": float(E.loc[E["determined"], "mbi"].mean()),
        "kb_coverage": float(df["kb_mapped"].mean()), "profiles": len(res["profiles"]),
        "selected_params": {k: {a: (None if np.isinf(b) else b) for a, b in v.items()}
                            for k, v in params.items()},
        "table1": t1_out.to_dict(orient="records"), "table2": t2_out.to_dict(orient="records"),
        "robustness": robust, "runtime_s": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    env = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
           "scikit-learn": sklearn.__version__, "scipy": scipy.__version__,
           "matplotlib": __import__("matplotlib").__version__, "platform": platform.platform()}
    (OUT / "environment.json").write_text(json.dumps(env, indent=2))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="fewer bootstrap draws")
    main(ap.parse_args().quick)
