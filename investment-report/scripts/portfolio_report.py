#!/usr/bin/env python3
"""Portfolio report from Obsidian vault markdown files.

Reads investment data from vault/finance/investments/*.md (YAML frontmatter)
and emits a compact JSON summary with KR/US split and daily delta.

Designed for Clawdbot cron runs (stdlib only, no external deps).

Data source: banksalad-import skill → vault/finance/investments/*.md
Each file has YAML frontmatter with: product_type, institution, invested,
current_value, return_pct, currency, source, updated.

US vs KR rule (confirmed by Daye):
- If institution == '토스증권' => US
- If name starts with 'TIGER' => US
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

DEFAULT_VAULT = str(Path.home() / "openclaw" / "vault" / "finance" / "investments")
DEFAULT_SNAPSHOT_DIR = str(Path.home() / "openclaw" / "portfolio" / "snapshots")


@dataclass
class Holding:
    asset: str
    broker: str
    name: str
    principal: float
    valuation: float
    return_pct: Optional[float]

    @property
    def pnl(self) -> float:
        return (self.valuation or 0.0) - (self.principal or 0.0)


def _parse_frontmatter(text: str) -> Dict[str, str]:
    """Parse YAML frontmatter from markdown text."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: Dict[str, str] = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip().strip("'\"")
    return fm


def _extract_name(text: str, filename: str, institution: str) -> str:
    """Extract product name from markdown heading or filename."""
    # Try markdown heading first: # ProductName
    for line in text.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    # Fallback: derive from filename by removing institution suffix
    stem = Path(filename).stem
    suffix = f"_{institution}"
    if stem.endswith(suffix):
        return stem[: -len(suffix)].replace("_", " ")
    return stem.replace("_", " ")


def _to_float(val: str) -> Optional[float]:
    """Convert frontmatter string value to float."""
    if not val or val in ("", "-", "None"):
        return None
    try:
        return float(val.replace(",", ""))
    except (ValueError, TypeError):
        return None


def parse_holdings(vault_dir: str) -> List[Holding]:
    """Read all investment markdown files from vault directory."""
    holdings: List[Holding] = []
    vault_path = Path(vault_dir)

    if not vault_path.exists():
        print(f"Warning: vault directory not found: {vault_dir}", file=__import__("sys").stderr)
        return holdings

    for md_file in sorted(vault_path.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        fm = _parse_frontmatter(text)

        # Only process investment files
        if fm.get("type") != "investment":
            continue

        institution = fm.get("institution", "")
        product_type = fm.get("product_type", "주식")
        invested = _to_float(fm.get("invested", ""))
        current_value = _to_float(fm.get("current_value", ""))
        return_pct = _to_float(fm.get("return_pct", ""))

        name = _extract_name(text, md_file.name, institution)

        holdings.append(
            Holding(
                asset=product_type,
                broker=institution,
                name=name,
                principal=invested or 0.0,
                valuation=current_value or 0.0,
                return_pct=return_pct,
            )
        )

    return holdings


def split_kr_us(holds: List[Holding]) -> Tuple[List[Holding], List[Holding]]:
    us: List[Holding] = []
    kr: List[Holding] = []
    for h in holds:
        is_us = (h.broker == "토스증권") or (h.name.startswith("TIGER"))
        (us if is_us else kr).append(h)
    return kr, us


def summarize(holds: List[Holding], top_n: int = 5) -> Dict[str, Any]:
    total_val = sum(h.valuation for h in holds) or 0.0
    total_principal = sum(h.principal for h in holds) or 0.0
    total_pnl = total_val - total_principal
    total_return_pct = (total_pnl / total_principal) if total_principal else None

    def with_weight(h: Holding) -> Dict[str, Any]:
        w = (h.valuation / total_val) if total_val else 0.0
        return {
            "name": h.name,
            "broker": h.broker,
            "principal": h.principal,
            "valuation": h.valuation,
            "pnl": h.pnl,
            "returnPct": h.return_pct,
            "weight": w,
        }

    top_holdings = sorted(holds, key=lambda x: x.valuation, reverse=True)[:top_n]
    top_winners = sorted(holds, key=lambda x: x.pnl, reverse=True)[:top_n]
    top_losers = sorted(holds, key=lambda x: x.pnl)[:top_n]

    return {
        "count": len(holds),
        "totalPrincipal": total_principal,
        "totalValuation": total_val,
        "totalPnL": total_pnl,
        "totalReturnPct": total_return_pct,
        "topHoldings": [with_weight(h) for h in top_holdings],
        "topWinners": [with_weight(h) for h in top_winners],
        "topLosers": [with_weight(h) for h in top_losers],
    }


def _today_ymd_kst() -> str:
    if ZoneInfo is None:
        return datetime.now().strftime("%Y-%m-%d")
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")


def _load_latest_snapshot(snapshot_dir: str) -> Optional[Dict[str, Any]]:
    paths = sorted(glob(os.path.join(snapshot_dir, "*.json")))
    if not paths:
        return None
    with open(paths[-1], "r", encoding="utf-8") as f:
        return json.load(f)


def _compute_daily_delta(cur: Dict[str, Any], prev: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not prev:
        return {"available": False}

    out: Dict[str, Any] = {"available": True}
    for k in ("kr", "us"):
        try:
            c = cur[k]
            p = prev[k]
            out[k] = {
                "deltaValuation": (c.get("totalValuation", 0.0) - p.get("totalValuation", 0.0)),
                "deltaPnL": (c.get("totalPnL", 0.0) - p.get("totalPnL", 0.0)),
            }
        except Exception:
            out[k] = {"deltaValuation": None, "deltaPnL": None}
    return out


def main():
    ap = argparse.ArgumentParser(description="Portfolio report from vault markdown files")
    ap.add_argument("--vault", default=DEFAULT_VAULT, help="Path to investments vault directory")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR, help="Daily snapshot directory")
    args = ap.parse_args()

    holds = parse_holdings(args.vault)
    kr, us = split_kr_us(holds)

    cur = {
        "asOf": _today_ymd_kst(),
        "source": args.vault,
        "kr": summarize(kr, top_n=args.top),
        "us": summarize(us, top_n=args.top),
    }

    os.makedirs(args.snapshot_dir, exist_ok=True)
    prev = _load_latest_snapshot(args.snapshot_dir)
    cur["daily"] = _compute_daily_delta({"kr": cur["kr"], "us": cur["us"]}, prev)
    snap_path = os.path.join(args.snapshot_dir, f"{cur['asOf']}.json")
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump({"asOf": cur["asOf"], "kr": cur["kr"], "us": cur["us"]}, f, ensure_ascii=False)
    cur["snapshotPath"] = snap_path

    print(json.dumps(cur, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
