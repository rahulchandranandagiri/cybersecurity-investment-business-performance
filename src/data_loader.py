"""Download, verify and flatten the VERIS Community Database (VCDB).

The study uses the joined VCDB release pinned to a fixed Git commit so that every
run sees exactly the same incident records. The archive is verified with SHA-256
before use. VCDB is published by the Verizon RISK Team under CC BY-SA 4.0.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

VCDB_COMMIT = "f6f98c00f66ab35f5b49977a5852ce94a5bb31d1"  # vz-risk/VCDB master, 2026-09-30
VCDB_URL = (f"https://github.com/vz-risk/VCDB/raw/{VCDB_COMMIT}"
            "/data/joined/vcdb.json.zip")
VCDB_SHA256 = "e4be5dd432ccfad16520a6b60dd83e9d47c63b0f3352c26c4d43a5dd774c32c0"
ACTIONS = ("hacking", "malware", "social", "misuse", "error", "physical",
           "environmental", "unknown")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch_vcdb(data_dir: str | Path = "data") -> Path:
    """Return the path of the verified VCDB zip, downloading it if needed."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    zpath = data_dir / "vcdb.json.zip"
    if not zpath.exists():
        print(f"Downloading VCDB @ {VCDB_COMMIT[:10]} ...")
        urllib.request.urlretrieve(VCDB_URL, zpath)
    digest = _sha256(zpath)
    if digest != VCDB_SHA256:
        raise RuntimeError(f"SHA-256 mismatch for {zpath}: {digest}. Delete the file "
                           "and re-run, or place the pinned archive there manually.")
    return zpath


def _flatten(rec: dict) -> dict:
    """Keep only the VERIS fields used by the study (one row per incident)."""
    act = rec.get("action", {})
    victim = rec.get("victim", {})
    attr = rec.get("attribute", {})
    conf = attr.get("confidentiality", {})
    row = {
        "incident_id": rec.get("incident_id"),
        "year": rec.get("timeline", {}).get("incident", {}).get("year"),
        "security_incident": rec.get("security_incident"),
        "sub_source": rec.get("plus", {}).get("sub_source"),
        "summary": (rec.get("summary") or "")[:200],
        "industry": str(victim.get("industry", "000000")),
        "employee_count": victim.get("employee_count", "Unknown"),
        "country": "|".join(victim.get("country", ["Unknown"])),
        "actor": "|".join(sorted(rec.get("actor", {}).keys())),
        "motive": "|".join(sorted({m for a in rec.get("actor", {}).values()
                                   for m in a.get("motive", [])})),
        "asset": "|".join(sorted({a.get("variety", "Unknown")
                                  for a in rec.get("asset", {}).get("assets", [])})),
        "availability": "|".join(attr.get("availability", {}).get("variety", [])),
        "has_confidentiality": bool(conf),
        "data_disclosure": conf.get("data_disclosure"),
        "data_total": conf.get("data_total"),
    }
    for a in ACTIONS:
        block = act.get(a)
        row[f"act_{a}"] = block is not None
        row[f"{a}_variety"] = "|".join(block.get("variety", [])) if block else ""
        row[f"{a}_vector"] = "|".join(block.get("vector", [])) if block else ""
    return row


def load_vcdb(data_dir: str | Path = "data") -> pd.DataFrame:
    """Load the pinned VCDB release as a flat DataFrame."""
    with zipfile.ZipFile(fetch_vcdb(data_dir)) as zf:
        name = [n for n in zf.namelist() if n.endswith(".json")][0]
        records = json.loads(zf.read(name))
    return pd.DataFrame([_flatten(r) for r in records])
