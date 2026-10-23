"""Knowledge base and investment decision layer of the KB-CIDS model.

Three kinds of codified knowledge are used:
  1. A production-rule base that maps VERIS threat patterns to nine cybersecurity
     control families aligned with CIS Critical Security Controls v8 and the NIST
     Cybersecurity Framework 2.0 (Table S1 in the supplementary material).
  2. Expert consequence rules that flag patterns prone to operational disruption,
     mass data exposure, or contained impact (used as features and as a baseline).
  3. A Gordon-Loeb class-I security-investment response function,
     S(z) = (alpha*z + 1) ** -beta, solved with water-filling under a budget.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FAMILIES = [
    ("F1", "Identity & access management", "CIS 5-6; PR.AA"),
    ("F2", "Vulnerability & secure configuration", "CIS 4, 7, 16; ID.RA, PR.PS"),
    ("F3", "Email/web protection & awareness", "CIS 9, 14; PR.AT"),
    ("F4", "Malware defense & threat detection", "CIS 10, 13; DE.CM"),
    ("F5", "Backup, recovery & resilience", "CIS 11, 17; RC.RP, PR.IR"),
    ("F6", "Data protection & handling", "CIS 3; PR.DS"),
    ("F7", "Insider & privileged-activity monitoring", "CIS 6, 8; DE.CM"),
    ("F8", "Physical & asset security", "CIS 1-2; PR.AA-06"),
    ("F9", "Third-party & supply-chain risk", "CIS 15; GV.SC"),
]
FAMILY_IDS = [f[0] for f in FAMILIES]
K = len(FAMILIES)
_IDX = {f: i for i, f in enumerate(FAMILY_IDS)}

# Documented rule base; mirrors family_weights() and consequence_rules() below.
RULES = [
    ("R1", "hacking", "Use of stolen creds / brute force / credential stuffing", "F1"),
    ("R2", "hacking", "Exploit vuln, SQLi, XSS, forced browsing, abuse of functionality", "F2"),
    ("R3", "hacking", "Backdoor or command-and-control use", "F4"),
    ("R4", "hacking", "Denial of service", "F5"),
    ("R5", "hacking", "Unknown variety via web application", "F2"),
    ("R6", "hacking", "Unknown variety via remote access / desktop sharing / VPN", "F1"),
    ("R7", "hacking", "Unknown variety via backdoor", "F4"),
    ("R8", "hacking", "Unknown variety and vector", "F1, F2"),
    ("R9", "malware", "Any malware", "F4"),
    ("R10", "malware", "Ransomware or data destruction", "F5"),
    ("R11", "malware", "Delivered by e-mail or web (attachment, link, drive-by)", "F3"),
    ("R12", "malware", "Remote injection", "F2"),
    ("R13", "social", "Bribery of insiders only", "F7"),
    ("R14", "social", "Phishing, pretexting and other social engineering", "F3"),
    ("R15", "misuse", "Any insider misuse (privilege, possession, knowledge abuse)", "F7"),
    ("R16", "misuse", "Data mishandling", "F6"),
    ("R17", "error", "Misconfiguration, programming error, malfunction", "F2"),
    ("R18", "error", "Misdelivery, publishing, disposal, loss and other handling errors", "F6"),
    ("R19", "physical", "Any physical action (theft, skimmer, tampering, snooping)", "F8"),
    ("R20", "physical", "Theft of user devices or media (encryption gap)", "F6"),
    ("R21", "environmental", "Fire, power failure, natural hazard", "F5"),
    ("R22", "actor", "Partner actor or partner vector", "F9"),
    ("C1", "consequence", "Ransomware, destructive malware, DoS or environmental event", "disrupt"),
    ("C2", "consequence", "Hacking of server-side data stores, data-capturing malware, "
                          "or misconfiguration/publishing of server data", "mass"),
    ("C3", "consequence", "Handling error (misdelivery, disposal, loss, gaffe), or physical "
                          "or misuse action without hacking", "contained"),
]

_CRED = {"Use of stolen creds", "Brute force", "Credential stuffing", "Password dumping"}
_VULN = {"Exploit vuln", "SQLi", "XSS", "Forced browsing", "Abuse of functionality",
         "Path traversal", "RFI", "Buffer overflow", "OS commanding", "Exploit misconfig",
         "URL redirector abuse", "Session replay", "Session fixation", "Format string attack"}
_BACKDOOR = {"Backdoor", "Use of backdoor or C2", "C2"}
_MAIL_WEB = {"Email attachment", "Email link", "Email", "Email unknown", "Email other",
             "Web application - drive-by", "Web application - download", "Web download",
             "Web drive-by"}
_CONFIG_ERR = {"Misconfiguration", "Programming error", "Malfunction", "Capacity shortage"}
_DATA_ERR = {"Misdelivery", "Publishing error", "Disposal error", "Loss", "Gaffe",
             "Data entry error", "Classification error", "Omission", "Other", "Unknown"}


def _split(value: str) -> set:
    return set(value.split("|")) if isinstance(value, str) and value else set()


def family_weights(r: pd.Series) -> np.ndarray:
    """Production rules: VERIS pattern -> control families (weights sum to 1)."""
    hits: list[str] = []
    if r["act_hacking"]:
        var, vec = _split(r["hacking_variety"]), _split(r["hacking_vector"])
        if var & _CRED:
            hits.append("F1")
        if var & _VULN:
            hits.append("F2")
        if var & _BACKDOOR:
            hits.append("F4")
        if "DoS" in var:
            hits.append("F5")
        if not var & (_CRED | _VULN | _BACKDOOR | {"DoS"}):  # unknown hacking variety
            if "Web application" in vec:
                hits.append("F2")
            elif vec & {"Desktop sharing", "Desktop sharing software", "VPN",
                        "Remote access", "Command shell"}:
                hits.append("F1")
            elif "Backdoor" in vec:
                hits.append("F4")
            else:
                hits += ["F1", "F2"]
    if r["act_malware"]:
        var, vec = _split(r["malware_variety"]), _split(r["malware_vector"])
        hits.append("F4")
        if var & {"Ransomware", "Destroy data"}:
            hits.append("F5")
        if vec & _MAIL_WEB:
            hits.append("F3")
        if "Remote injection" in vec:
            hits.append("F2")
    if r["act_social"]:
        var = _split(r["social_variety"])
        hits.append("F7" if var & {"Bribery"} and not var - {"Bribery"} else "F3")
    if r["act_misuse"]:
        var = _split(r["misuse_variety"])
        hits.append("F7")
        if "Data mishandling" in var:
            hits.append("F6")
    if r["act_error"]:
        var = _split(r["error_variety"])
        if var & _CONFIG_ERR:
            hits.append("F2")
        if var & _DATA_ERR or not var:
            hits.append("F6")
    if r["act_physical"]:
        hits.append("F8")
        if _split(r["physical_variety"]) & {"Theft"} and any(
                a[:1] in ("U", "M") for a in _split(r["asset"])):
            hits.append("F6")  # stolen unencrypted laptops/media
    if r["act_environmental"]:
        hits.append("F5")
    if "partner" in _split(r["actor"]) or "Partner" in _split(r["hacking_vector"]):
        hits.append("F9")
    w = np.zeros(K)
    for h in hits:
        w[_IDX[h]] += 1.0
    return w / w.sum() if w.sum() > 0 else w


def consequence_rules(r: pd.Series) -> dict:
    """Expert rules on the business consequence of a threat pattern."""
    hv, mv = _split(r["hacking_variety"]), _split(r["malware_variety"])
    assets = _split(r["asset"])
    server_data = bool(assets & {"S - Database", "S - Web application", "S - File",
                                 "S - Mail"})
    disrupt = bool({"Ransomware", "Destroy data"} & mv) or "DoS" in hv or bool(
        r["act_environmental"])
    mass = (bool(r["act_hacking"]) and server_data and (
        bool(hv & _VULN) or "Web application" in _split(r["hacking_vector"]))) or (
        bool({"Capture stored data", "Export data", "RAM scraper"} & mv)) or (
        bool(_split(r["error_variety"]) & {"Misconfiguration", "Publishing error"})
        and server_data)
    contained = (bool(_split(r["error_variety"]) & {"Misdelivery", "Disposal error",
                                                     "Loss", "Gaffe"})
                 or (bool(r["act_physical"]) and not r["act_hacking"])
                 or (bool(r["act_misuse"]) and not r["act_hacking"]))
    return {"kr_disrupt": int(disrupt), "kr_mass": int(mass),
            "kr_contained": int(contained)}


def rule_score(df: pd.DataFrame) -> np.ndarray:
    """Knowledge-only impact score (no learning): 2*disrupt + mass - contained."""
    return (2 * df["kr_disrupt"] + df["kr_mass"] - df["kr_contained"]).to_numpy(float)


# ---------------------------------------------------------------- decision layer
def profile_weights(df: pd.DataFrame, sector: str, size: str, lam_size: float,
                    lam_global: float, half_life: float, ref_year: int) -> np.ndarray:
    """Similarity x recency weights of historical incidents for a target firm profile.

    lam_size: weight of same-sector incidents from the other size band;
    lam_global: weight of all other incidents (np.inf = pooled, no context);
    half_life: recency half-life in years (np.inf = no recency weighting).
    """
    if np.isinf(lam_global):
        w = np.ones(len(df))
    else:
        same_sector = (df["sector"].to_numpy() == sector).astype(float)
        same_size = (df["size"].to_numpy() == size).astype(float)
        w = same_sector * (same_size + lam_size * (1 - same_size)) + lam_global
    if np.isfinite(half_life):
        w = w * 2.0 ** (-(ref_year - df["year"].to_numpy(float)) / half_life)
    return w


def risk_shares(fw: np.ndarray, impact: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Business-impact risk share of each control family: sum_i w_i p_i K_ic."""
    mass = (w * impact) @ fw
    return mass / mass.sum() if mass.sum() > 0 else np.full(fw.shape[1], 1.0 / fw.shape[1])


def gl_allocate(shares: np.ndarray, budget: float, alpha: float = 1.0,
                beta: float = 1.0) -> np.ndarray:
    """Minimise sum_c s_c (alpha z_c + 1)^-beta  s.t. sum z = budget, z >= 0."""
    s = np.clip(np.asarray(shares, float), 1e-12, None)

    def alloc(lmb: float) -> np.ndarray:
        return np.maximum(0.0, ((alpha * beta * s / lmb) ** (1.0 / (beta + 1)) - 1) / alpha)

    lo, hi = 1e-12, alpha * beta * s.max()          # z(hi) = 0, z(lo) -> large
    for _ in range(200):
        mid = np.sqrt(lo * hi)
        lo, hi = (mid, hi) if alloc(mid).sum() > budget else (lo, mid)
    z = alloc(hi)
    return z * budget / z.sum() if z.sum() > 0 else np.full_like(s, budget / len(s))


def residual(z: np.ndarray, alpha: float = 1.0, beta: float = 1.0) -> np.ndarray:
    return (alpha * np.asarray(z) + 1.0) ** (-beta)


def birr(realized_shares: np.ndarray, z: np.ndarray, alpha: float = 1.0,
         beta: float = 1.0) -> float:
    """Business-impact risk reduction achieved by allocation z (0..1)."""
    return float(1.0 - realized_shares @ residual(z, alpha, beta))
