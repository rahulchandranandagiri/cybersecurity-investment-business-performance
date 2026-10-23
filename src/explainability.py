"""Explanations (feature importance, allocation rationale) and publication figures."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from sklearn.inspection import permutation_importance

from .decision_intelligence import FAMILIES, FAMILY_IDS

INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = {"kb": "#2a78d6", "freq": "#eb6834", "impact": "#1baf7a"}  # fixed slot order
BLUES = LinearSegmentedColormap.from_list("blues", ["#fcfcfb", "#cde2fb", "#86b6ef",
                                                     "#3987e5", "#1c5cab", "#0d366b"])
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": AXIS,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.titlesize": 9, "axes.titleweight": "bold", "axes.linewidth": 0.6,
                     "figure.dpi": 150, "savefig.dpi": 600, "pdf.fonttype": 42})


def grouped_importance(model, X: pd.DataFrame, y: np.ndarray, n_repeats: int = 10,
                       seed: int = 42) -> pd.DataFrame:
    """Permutation importance (drop in ROC-AUC) on the evaluation period."""
    r = permutation_importance(model, X, y, scoring="roc_auc", n_repeats=n_repeats,
                               random_state=seed, n_jobs=-1)
    imp = pd.DataFrame({"feature": X.columns, "mean_drop_auc": r.importances_mean,
                        "sd": r.importances_std})
    return imp.sort_values("mean_drop_auc", ascending=False).reset_index(drop=True)


def allocation_rationale(D: pd.DataFrame, impact: np.ndarray, w: np.ndarray,
                         top: int = 3) -> pd.DataFrame:
    """For each control family, the threat patterns contributing most risk mass."""
    pattern = D.apply(lambda r: " + ".join(
        f"{a}:{(r[f'{a}_variety'] or 'Unknown').split('|')[0]}"
        for a in ("hacking", "malware", "social", "misuse", "error", "physical")
        if r[f"act_{a}"]) or "unknown", axis=1)
    rows = []
    for j, f in enumerate(FAMILY_IDS):
        mass = pd.Series(w * impact * D[f"kb_{f}"].to_numpy()).groupby(pattern.values).sum()
        total = mass.sum()
        for pat, m in mass.sort_values(ascending=False).head(top).items():
            if m > 0:
                rows.append({"family": f, "pattern": pat, "share_of_family_risk": m / total})
    return pd.DataFrame(rows)


def _style(ax):
    ax.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def figure_1(alloc: dict, real: dict, profs: list, path_stem: str) -> None:
    """Heatmaps: threat-frequency allocation, KB-CIDS allocation, realized risk."""
    labels = [f"{s} ({z.lower()})" for s, z in profs]
    panels = [("(a) Threat-frequency budget", alloc["freq"]),
              ("(b) KB-CIDS budget", alloc["kb"]),
              ("(c) Realized risk, 2017-2026", real)]
    fig, axes = plt.subplots(1, 3, figsize=(7.48, 5.4), sharey=True,
                             gridspec_kw={"wspace": 0.08})
    for ax, (title, data) in zip(axes, panels):
        M = np.array([data[p] for p in profs]) * 100
        im = ax.imshow(M, cmap=BLUES, vmin=0, vmax=60, aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                if M[i, j] >= 15:
                    ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=6,
                            color="#ffffff" if M[i, j] >= 35 else INK)
        ax.set_xticks(range(len(FAMILY_IDS)), FAMILY_IDS, fontsize=7)
        ax.set_title(title, loc="left", fontsize=8, color=INK)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0].set_yticks(range(len(profs)), labels, fontsize=7)
    cb = fig.colorbar(im, ax=axes, orientation="horizontal", fraction=0.03, pad=0.055,
                      aspect=60)
    cb.set_label("Share of budget (a, b) or of realized material-impact risk (c), %",
                 color=INK2, fontsize=7)
    cb.ax.tick_params(labelsize=7)
    cb.outline.set_visible(False)
    names = [f"{fid} {name}" for fid, name, _ in FAMILIES]
    for k, line in enumerate(("     ".join(names[:5]), "     ".join(names[5:]))):
        fig.text(0.5, 0.0 - 0.022 * k, line, ha="center", fontsize=6, color=INK2)
    fig.savefig(f"{path_stem}.png", bbox_inches="tight", facecolor="white")
    fig.savefig(f"{path_stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def figure_2(curve: pd.DataFrame, scores: pd.DataFrame, ref_budget: float,
             path_stem: str) -> None:
    """(a) BIRR against budget; (b) per-profile paired comparison at the reference budget."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.48, 3.5), gridspec_kw={"width_ratios": [1.1, 1]})
    _style(a)
    x = curve["budget"] / ref_budget
    series = [("KB-CIDS (full)", SERIES["kb"], "KB-CIDS"),
              ("Impact-aligned (pooled)", SERIES["impact"], "Impact-aligned, pooled"),
              ("Threat frequency (context)", SERIES["freq"], "Threat frequency")]
    a.fill_between(x, curve["KB-CIDS (full) lo"], curve["KB-CIDS (full) hi"],
                   color=SERIES["kb"], alpha=0.15, linewidth=0)
    a.plot(x, curve["Oracle (ex post)"], color=INK2, lw=1.2, ls=":", label="Oracle (ex post)")
    for col, colour, lab in series:
        a.plot(x, curve[col], color=colour, lw=2, label=lab)
    a.plot(x, curve["Equal allocation"], color=MUTED, lw=1.5, label="Equal allocation")
    a.set_xscale("log")
    a.set_xticks([0.1, 0.25, 0.5, 1, 2, 4, 10], ["0.1", "0.25", "0.5", "1", "2", "4", "10"])
    a.axvline(1, color=AXIS, lw=0.8)
    a.set_xlabel("Security budget relative to reference (B / B$_{ref}$)")
    a.set_ylabel("Business-impact risk reduction (BIRR)")
    a.set_title("(a) Risk reduction across budget levels", loc="left", color=INK)
    a.legend(frameon=False, fontsize=6.5, loc="upper left")
    _style(b)
    order = (scores["KB-CIDS (full)"] - scores["Equal allocation"]).sort_values().index
    yy = np.arange(len(order))
    s_kb = scores.loc[order, "KB-CIDS (full)"].to_numpy()
    s_fr = scores.loc[order, "Threat frequency (context)"].to_numpy()
    b.hlines(yy, s_fr, s_kb, color=AXIS, lw=1.2)
    b.scatter(s_fr, yy, s=22, color=SERIES["freq"], edgecolor="white", lw=0.8, zorder=3,
              label="Threat frequency")
    b.scatter(s_kb, yy, s=22, color=SERIES["kb"], edgecolor="white", lw=0.8, zorder=3,
              label="KB-CIDS")
    b.axvline(scores["Equal allocation"].iloc[0], color=MUTED, lw=1.2)
    b.text(scores["Equal allocation"].iloc[0], len(order) - 0.3, " Equal allocation",
           fontsize=6.5, color=INK2, va="bottom")
    b.set_yticks(yy, [f"{s} ({z.lower()})" for s, z in order], fontsize=6.3)
    b.set_xlabel("BIRR at reference budget")
    b.set_title("(b) Paired comparison by firm profile", loc="left", color=INK)
    b.legend(frameon=False, fontsize=6.5, loc="lower right")
    b.set_xlim(min(s_fr.min(), 0.5) - 0.02, max(s_kb.max(), 0.5) + 0.06)
    b.set_ylim(-0.7, len(order) + 0.4)
    fig.tight_layout()
    fig.savefig(f"{path_stem}.png", bbox_inches="tight", facecolor="white")
    fig.savefig(f"{path_stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def graphical_abstract(stats: dict, path_stem: str) -> None:
    """Explanatory pipeline schematic (drawn programmatically, no generative imagery)."""
    fig, ax = plt.subplots(figsize=(10.0, 4.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")
    boxes = [
        ("Real-world\nincident data", f"VCDB: {stats['n_incidents']:,} incidents\n"
                                       f"{stats['n_sectors']} sectors, 2000-2026"),
        ("AI materiality\nmodel", "P(material business impact)\n"
                                  f"out-of-time AUC = {stats['auc']:.2f}"),
        ("Knowledge\nbase", f"{stats['n_rules']} production rules\n9 control families\n"
                             "(CIS v8 / NIST CSF 2.0)"),
        ("Investment\ndecision layer", "context & recency\nweighting; Gordon-Loeb\n"
                                        "budget water-filling"),
        ("Business-impact\nrisk reduction", f"KB-CIDS {stats['birr_kb']:.2f}\n"
                                             f"equal split {stats['birr_eq']:.2f}\n"
                                             f"threat counts {stats['birr_freq']:.2f}"),
    ]
    w, gap, x0 = 17.2, 3.3, 0.4
    for k, (head, body) in enumerate(boxes):
        x = x0 + k * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 7), w, 23, boxstyle="round,pad=0.3,rounding_size=1.2",
                                    fc="#f0f6fe", ec=SERIES["kb"], lw=1.1))
        ax.text(x + w / 2, 25.6, head, ha="center", va="center", fontsize=9.0,
                weight="bold", color=INK, linespacing=1.15)
        ax.text(x + w / 2, 14.2, body, ha="center", va="center", fontsize=7.2, color=INK2,
                linespacing=1.45)
        if k < len(boxes) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.6, 18.5), (x + w + gap - 0.6, 18.5),
                                         arrowstyle="-|>", mutation_scale=14,
                                         color=SERIES["kb"], lw=1.6))
    ax.text(50, 36.2, "Aligning cybersecurity investment with business-impact risk",
            ha="center", fontsize=12, weight="bold", color=INK)
    ax.text(50, 2.2, "Governance loop: exposure, materiality and allocation are re-estimated "
                     "as new incident data arrive", ha="center", fontsize=8, color=INK2,
            style="italic")
    fig.savefig(f"{path_stem}.png", bbox_inches="tight", facecolor="white", dpi=300)
    fig.savefig(f"{path_stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)
