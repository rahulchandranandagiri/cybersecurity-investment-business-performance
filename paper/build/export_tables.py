"""Export manuscript-ready numbers from the repository results (single source of truth)."""
import json, sys
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent
R = HERE.parents[1] / 'results'
t1 = pd.read_csv(R/'tables'/'Table_1_predictive_validity.csv')
t2 = pd.read_csv(R/'tables'/'Table_2_decision_performance.csv')
def fp(p):
    return '<0.001' if p < 0.001 else f'{p:.3f}'
rows1 = []
names1 = {"Historical lookup (action category)": "Historical lookup (action category)",
          "Knowledge rules (expert, calibrated)": "Expert consequence rules (Platt-calibrated)",
          "Logistic regression": "Logistic regression",
          "Random forest": "Random forest",
          "Gradient boosting": "Gradient boosting (no knowledge features)",
          "KB-CIDS risk model (GB + knowledge, calibrated)": "KB-CIDS materiality model"}
for _, r in t1.iterrows():
    lo, hi = r['ROC-AUC CI'].strip('[]').split(', ')
    d = '' if pd.isna(r['dAUC vs proposed']) else f"{r['dAUC vs proposed']:+.3f} ({fp(r['p (paired bootstrap)'])})"
    rows1.append([names1[r['Model']], f"{r['ROC-AUC']:.3f} ({lo}–{hi})", f"{r['PR-AUC']:.3f}", f"{r['Brier']:.3f}", f"{r['ECE']:.3f}", d or '—'])
names2 = {"Equal allocation": "Equal allocation (undifferentiated)",
          "Threat frequency (pooled)": "Threat frequency, pooled",
          "Threat frequency (context)": "Threat frequency, context-weighted",
          "Impact-aligned (pooled)": "Impact-aligned, pooled",
          "KB-CIDS w/o context": "KB-CIDS without context weighting",
          "KB-CIDS w/o recency": "KB-CIDS without recency weighting",
          "KB-CIDS w/o AI imputation": "KB-CIDS without AI imputation",
          "KB-CIDS (full)": "KB-CIDS (full model)",
          "Oracle (ex post)": "Oracle (ex post upper bound)"}
rows2 = []
for _, r in t2.iterrows():
    lo, hi = r['BIRR 95% CI'].strip('[]').split(', ')
    ci = '' if r['Strategy'] == 'Equal allocation' else f" ({lo}–{hi})"
    pk = '—' if r['Strategy'] == 'KB-CIDS (full)' else fp(r['Wilcoxon p vs KB-CIDS'])
    rows2.append([names2[r['Strategy']], f"{r['Mean BIRR']:.3f}{ci}", f"{r['Delta vs equal (pp)']:+.1f}", f"{r['Oracle gap closed (%)']:.1f}", f"{int(r['Profiles better than equal'])}/18", pk])
s = json.load(open(R/'summary.json'))
out = {'table1': rows1, 'table2': rows2, 'summary': {k: s[k] for k in ['cohort','development','evaluation','development_determined','evaluation_determined','mbi_rate_development','mbi_rate_evaluation','kb_coverage','profiles']}}
# supplementary tables
sup = {}
sup['S1'] = pd.read_csv(R/'tables'/'S1_knowledge_base.csv').values.tolist()
sup['S1b'] = pd.read_csv(R/'tables'/'S1b_control_families.csv').values.tolist()
sc = pd.read_csv(R/'tables'/'S2_profile_scores.csv', index_col=0)
cols = ['Equal allocation','Threat frequency (context)','Impact-aligned (pooled)','KB-CIDS w/o AI imputation','KB-CIDS (full)','Oracle (ex post)']
sup['S2'] = [[i.replace(' | ', ', ')] + [f"{sc.loc[i, c]:.3f}" for c in cols] for i in sc.index]
tl = pd.read_csv(R/'tables'/'S3_validation_tuning.csv')
best = tl.sort_values('validation_BIRR', ascending=False).groupby('strategy', sort=False).head(1)
def hv(v):
    return '∞' if (isinstance(v, float) and (v == float('inf'))) or str(v) == 'inf' else f"{float(v):g}"
sup['S3'] = [[r.strategy, hv(r.lam_size), hv(r.lam_global), hv(r.half_life), f"{r.validation_BIRR:.4f}"] for r in best.itertuples()]
cur = pd.read_csv(R/'tables'/'S4_budget_curve.csv'); cur['rel'] = cur['budget']/9
sel = cur.iloc[[0,3,6,9,12,15,18,21,24]]
sup['S4'] = [[f"{r.rel:.2f}", f"{r['Equal allocation']:.3f}", f"{r['Threat frequency (context)']:.3f}", f"{r['Impact-aligned (pooled)']:.3f}", f"{r['KB-CIDS (full)']:.3f}", f"{r['Oracle (ex post)']:.3f}"] for _, r in sel.iterrows()]
sens = pd.read_csv(R/'tables'/'S5_sensitivity_alpha_beta.csv')
sup['S5'] = [[f"{r.alpha:g}", f"{r.beta:g}", f"{r['Equal allocation']:.3f}", f"{r['Threat frequency (context)']:.3f}", f"{r['KB-CIDS (full)']:.3f}", f"{r['Oracle (ex post)']:.3f}", f"{r['KB-CIDS gap closed (%)']:.1f}"] for _, r in sens.iterrows()]
rob = pd.read_csv(R/'tables'/'S6_robustness.csv', index_col=0)
sup['S6'] = [[i, f"{int(r['Profiles'])}", f"{r['Equal allocation']:.3f}", f"{r['Threat frequency (context)']:.3f}", f"{r['Impact-aligned (pooled)']:.3f}", f"{r['KB-CIDS w/o AI imputation']:.3f}", f"{r['KB-CIDS (full)']:.3f}", f"{r['Oracle (ex post)']:.3f}", f"{r['KB-CIDS gap closed (%)']:.1f}", fp(r['p (KB-CIDS vs threat frequency)'])] for i, r in rob.iterrows()]
imp = pd.read_csv(R/'tables'/'S7_permutation_importance.csv').head(15)
sup['S7'] = [[r.feature, f"{r.mean_drop_auc:.4f}", f"{r.sd:.4f}"] for r in imp.itertuples()]
ra = pd.read_csv(R/'tables'/'S8_allocation_rationale_healthcare_small.csv')
sup['S8'] = [[r.family, r.pattern, f"{100*r.share_of_family_risk:.1f}"] for r in ra.itertuples()]
al = pd.read_csv(R/'tables'/'S9_allocations.csv')
fam = [f'F{i}' for i in range(1,10)]
m = al.groupby('strategy')[fam].mean()
sup['S9'] = [[{'freq':'Threat frequency, context-weighted','kb':'KB-CIDS','realized':'Realized risk share 2017–2026'}[k]] + [f"{100*m.loc[k,f]:.1f}" for f in fam] for k in ['freq','kb','realized']]
t1full = pd.read_csv(R/'tables'/'Table_1_predictive_validity.csv')
sup['S10'] = [[names1[r['Model']], f"{r['PR-AUC']:.3f} {r['PR-AUC CI'].replace(', ', '–')}", f"{r['Brier']:.3f} {r['Brier CI'].replace(', ', '–')}", f"{r['ECE']:.3f} {r['ECE CI'].replace(', ', '–')}"] for _, r in t1full.iterrows()]
out['sup'] = sup
json.dump(out, open(HERE / 'tables.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out['table1'], ensure_ascii=False, indent=0)); print(json.dumps(out['table2'], ensure_ascii=False, indent=0)); print(out['summary'])
