"""Check the submitted manuscript against the experiment outputs.

Reads paper/Manuscript.docx, Highlights.docx and Supplementary_Material.docx and verifies
(1) journal format limits, (2) citation numbering and cross-references, and (3) that every
number quoted in the text equals the value computed in results/ by run_experiment.py.

Usage (from the repository root, after `python run_experiment.py`):
    python paper/verify_manuscript.py
Exits with status 1 if any check fails. Needs only the packages in requirements.txt.
"""
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

PAPER = Path(__file__).resolve().parent
R = PAPER.parent / "results"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def docx_text(path: Path) -> str:
    """Plain text of a .docx: one line per paragraph (tables cell by cell), equations included."""
    body = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml")).find(W + "body")
    lines = []
    for p in body.iter(W + "p"):
        parts = []
        for el in p.iter():
            if el.tag in (W + "t", M + "t") and el.text:
                parts.append(el.text)
            elif el.tag == W + "tab":
                parts.append("\t")
            elif el.tag in (W + "br", W + "cr"):
                parts.append("\n")
            elif el.tag == W + "noBreakHyphen":
                parts.append("-")
        lines.append("".join(parts))
    return "\n".join(lines).replace("\xa0", " ").replace(" ", " ")


txt = docx_text(PAPER / "Manuscript.docx")
hl = docx_text(PAPER / "Highlights.docx")
sup = docx_text(PAPER / "Supplementary_Material.docx")
res = []


def check(name, ok, detail=""):
    res.append((name, bool(ok), detail))


# ---------------- journal format limits
abs_m = re.search(r"Abstract\s+(.*?)\s+Keywords:", txt, re.S)
n_words = len(re.findall(r"\S+", abs_m.group(1))) if abs_m else 0
check("Abstract <= 250 words", 0 < n_words <= 250, f"{n_words} words")
kw = re.search(r"Keywords:\s*(.*?)\n", txt).group(1)
n_kw = len([k for k in kw.split(";") if k.strip()])
check("Keywords 1-5 (Elsevier submission form limit)", 1 <= n_kw <= 5, f"{n_kw} keywords")
bullets = [l.strip(" -•\t") for l in hl.splitlines() if l.strip() and l.strip() != "Highlights"]
check("Highlights 3-5 bullets", 3 <= len(bullets) <= 5, f"{len(bullets)} bullets")
for b in bullets:
    check(f'Highlight <= 85 chars: "{b[:40]}..."', len(b) <= 85, f"{len(b)} chars")

# ---------------- citations and cross-references
body, refs = txt.split("\nReferences\n")[0], txt.split("\nReferences\n")[1]
n_refs = len(re.findall(r"^\[(\d+)\]", refs, re.M))
cited = []
for grp in re.findall(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]", body):
    for part in grp.split(","):
        part = part.strip()
        if re.match(r"^\d+\s*[–-]\s*\d+$", part):
            a, b = map(int, re.split(r"[–-]", part))
            cited += list(range(a, b + 1))
        else:
            cited.append(int(part))
first = list(dict.fromkeys(cited))
check("Reference list length", n_refs == 36, f"{n_refs} references")
check("Every reference cited in text", set(range(1, n_refs + 1)) <= set(cited),
      f"uncited: {sorted(set(range(1, n_refs + 1)) - set(cited))}")
check("No citation outside reference list", max(cited) <= n_refs and min(cited) >= 1,
      f"range {min(cited)}-{max(cited)}")
check("References numbered in order of first citation", first == sorted(first) and first[0] == 1)
for item in ["Table 1", "Table 2", "Fig. 1", "Fig. 2", "Eq. (1)", "Eq. (7)", "Algorithm 1"]:
    check(f"{item} cited in text", item in body)
for s in ["S1", "S5", "S6", "S7", "S8", "S10"]:
    check(f"Table {s} exists in supplementary", f"Table {s}." in sup)

# ---------------- numbers quoted in the manuscript vs results/
S = json.load(open(R / "summary.json"))
tab = lambda name: pd.read_csv(R / "tables" / name)
t1 = tab("Table_1_predictive_validity.csv").set_index("Model")
t2 = tab("Table_2_decision_performance.csv").set_index("Strategy")
sc = pd.read_csv(R / "tables" / "S2_profile_scores.csv", index_col=0)
rob = pd.read_csv(R / "tables" / "S6_robustness.csv", index_col=0)
sens, cur, imp = tab("S5_sensitivity_alpha_beta.csv"), tab("S4_budget_curve.csv"), tab("S7_permutation_importance.csv")
al, tun = tab("S9_allocations.csv"), tab("S3_validation_tuning.csv")
ra = tab("S8_allocation_rationale_healthcare_small.csv")
KB = "KB-CIDS risk model (GB + knowledge, calibrated)"
fam = [f"F{i}" for i in range(1, 10)]
m = al.groupby("strategy")[fam].mean()
d_fr = sc["KB-CIDS (full)"] - sc["Threat frequency (context)"]
f3 = lambda x: f"{x:.3f}"
pct = lambda x: f"{100 * x:.1f}%"
ci = lambda s: s.strip("[]").replace(", ", "–")
claims = {
    "9,284": f"{S['cohort']:,}", "7,438": f"{S['development']:,}", "1,846": f"{S['evaluation']:,}",
    "4,941": f"{S['development_determined']:,}", "1,133": f"{S['evaluation_determined']:,}",
    "6,074": f"{S['development_determined'] + S['evaluation_determined']:,}",
    "26.7%": pct(S["mbi_rate_development"]), "62.9%": pct(S["mbi_rate_evaluation"]), "97.4%": pct(S["kb_coverage"]),
    "0.891": f3(t1.loc[KB, "ROC-AUC"]), "0.932": f3(t1.loc[KB, "PR-AUC"]),
    "0.883": f3(t1.loc["Gradient boosting", "ROC-AUC"]), "0.865": f3(t1.loc["Random forest", "ROC-AUC"]),
    "0.849": f3(t1.loc["Logistic regression", "ROC-AUC"]),
    "0.833": f3(t1.loc["Knowledge rules (expert, calibrated)", "ROC-AUC"]),
    "0.679": f3(t1.loc["Historical lookup (action category)", "ROC-AUC"]),
    "0.873–0.911": ci(t1.loc[KB, "ROC-AUC CI"]),
    "ΔAUC = 0.009": f"ΔAUC = {-t1.loc['Gradient boosting', 'dAUC vs proposed']:.3f}",
    "p = 0.001": f"p = {t1.loc['Gradient boosting', 'p (paired bootstrap)']:.3f}",
    "ΔAUC = 0.074": f"ΔAUC = {imp.iloc[0]['mean_drop_auc']:.3f}",
    "ECE 0.118–0.270": f"ECE {t1['ECE'].min():.3f}–{t1['ECE'].max():.3f}",
    "0.483": f3(t2.loc["Threat frequency (context)", "Mean BIRR"]),
    "0.443": f3(t2.loc["Threat frequency (pooled)", "Mean BIRR"]),
    "0.553": f3(t2.loc["Impact-aligned (pooled)", "Mean BIRR"]), "0.588": f3(t2.loc["KB-CIDS (full)", "Mean BIRR"]),
    "0.577–0.599": ci(t2.loc["KB-CIDS (full)", "BIRR 95% CI"]),
    "0.656": f3(t2.loc["Oracle (ex post)", "Mean BIRR"]),
    "56.5%": f"{t2.loc['KB-CIDS (full)', 'Oracle gap closed (%)']:.1f}%",
    "0.567": f3(t2.loc["KB-CIDS w/o recency", "Mean BIRR"]), "0.585": f3(t2.loc["KB-CIDS w/o context", "Mean BIRR"]),
    "0.599": f3(t2.loc["KB-CIDS w/o AI imputation", "Mean BIRR"]),
    "= 0.074)": f"= {t2.loc['KB-CIDS w/o context', 'Wilcoxon p vs KB-CIDS']:.3f})",
    "better in 15 of 18": f"better in {int(t2.loc['Impact-aligned (pooled)', 'Profiles better than equal'])} of 18",
    "higher in 15 of 18": f"higher in {int((sc['KB-CIDS w/o AI imputation'] > sc['KB-CIDS (full)']).sum())} of 18",
    "0.022–0.175": f"{d_fr.min():.3f}–{d_fr.max():.3f}",
    "59.0%": pct(m.loc["freq", ["F6", "F7", "F8"]].sum()), "10.3%": pct(m.loc["realized", ["F6", "F7", "F8"]].sum()),
    "52.2%": pct(m.loc["kb", ["F2", "F4", "F5"]].sum()), "28.6%": pct(m.loc["freq", ["F2", "F4", "F5"]].sum()),
    "71.6%": pct(m.loc["realized", ["F2", "F4", "F5"]].sum()),
    "0.560 vs 0.541": f"{tun[tun.strategy == 'KB-CIDS (full)'].validation_BIRR.max():.3f} vs "
                      f"{tun[tun.strategy == 'KB-CIDS w/o AI imputation'].validation_BIRR.max():.3f}",
    "0.190 vs 0.091": f"{cur.iloc[0]['KB-CIDS (full)']:.3f} vs {cur.iloc[0]['Equal allocation']:.3f}",
    "≤ 0.008": f"≤ {rob['p (KB-CIDS vs threat frequency)'].max():.3f}",
    "34–67%": f"{rob['KB-CIDS gap closed (%)'].min():.0f}–{rob['KB-CIDS gap closed (%)'].max():.0f}%",
    "43–62%": f"{sens['KB-CIDS gap closed (%)'].min():.0f}–{sens['KB-CIDS gap closed (%)'].max():.0f}%",
    "40.5%": pct(ra[ra.family == "F5"].iloc[0].share_of_family_risk),
    "34.5%": pct(ra[ra.family == "F5"].iloc[1].share_of_family_risk),
    "26.3%": pct(ra[ra.family == "F6"].iloc[0].share_of_family_risk),
    "24.7%": pct(ra[ra.family == "F6"].iloc[1].share_of_family_risk),
    "20.8%": pct(ra[ra.family == "F6"].iloc[2].share_of_family_risk),
    "closed 56% of the gap": f"closed {t2.loc['KB-CIDS (full)', 'Oracle gap closed (%)']:.0f}% of the gap",
}
for quoted, computed in claims.items():
    check(f'number "{quoted}" matches results', quoted == computed and quoted in txt,
          f"computed {computed}; in text: {quoted in txt}")
check("Robustness: KB-CIDS > equal and > threat frequency in every specification",
      ((rob["KB-CIDS (full)"] > rob["Equal allocation"])
       & (rob["KB-CIDS (full)"] > rob["Threat frequency (context)"])).all())
check("Sensitivity: threat frequency below equal for every (alpha, beta)",
      (sens["Threat frequency (context)"] < sens["Equal allocation"]).all())
check("KB-CIDS > equal and > threat frequency in 18/18 profiles",
      (sc["KB-CIDS (full)"] > sc["Equal allocation"]).all() and (d_fr > 0).all())
check("Contained-impact rule ranked fifth in permutation importance", imp.iloc[4]["feature"] == "kr_contained")
check("Resilience family weight ranked first", imp.iloc[0]["feature"] == "kb_F5")

ok = sum(r[1] for r in res)
print(f"{ok}/{len(res)} checks passed")
for name, passed, det in res:
    print(("PASS " if passed else "FAIL ") + name + (f"  [{det}]" if det else ""))
sys.exit(0 if ok == len(res) else 1)
