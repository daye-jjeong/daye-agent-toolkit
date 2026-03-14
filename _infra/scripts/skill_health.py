#!/usr/bin/env python3
"""Skill health check — validate skill structure, references, and consistency.

Usage:
    python3 skill_health.py          # check all skills
    python3 skill_health.py --fix    # auto-fix trivial issues (not yet implemented)
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CATEGORIES = ["cc", "shared"]
REQUIRED_FILES = ["SKILL.md", ".claude-skill"]
FRONTMATTER_REQUIRED = ["name", "description"]


def find_skills() -> list[Path]:
    """Discover skill directories (those containing SKILL.md)."""
    skills = []
    for cat in CATEGORIES:
        cat_dir = REPO_ROOT / cat
        if not cat_dir.exists():
            continue
        for skill_dir in sorted(cat_dir.iterdir()):
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skills.append(skill_dir)
    return skills


def parse_frontmatter(skill_md: Path) -> dict | None:
    """Extract YAML frontmatter from SKILL.md."""
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


def check_skill(skill_dir: Path) -> list[str]:
    """Return list of issues for a skill directory."""
    issues = []

    # 1. Required files
    for fname in REQUIRED_FILES:
        if not (skill_dir / fname).exists():
            issues.append(f"missing {fname}")

    # 2. .claude-skill validity
    cs_path = skill_dir / ".claude-skill"
    cs_data = {}
    if cs_path.exists():
        try:
            cs_data = json.loads(cs_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append(".claude-skill is not valid JSON")

    # 3. SKILL.md frontmatter
    skill_md = skill_dir / "SKILL.md"
    fm = {}
    if skill_md.exists():
        fm = parse_frontmatter(skill_md) or {}
        if not fm:
            issues.append("SKILL.md missing frontmatter (---)")
        for field in FRONTMATTER_REQUIRED:
            if field not in fm:
                issues.append(f"SKILL.md missing frontmatter field: {field}")

    # 4. Name consistency
    dir_name = skill_dir.name
    if cs_data.get("name") and cs_data["name"] != dir_name:
        issues.append(f"name mismatch: dir={dir_name} .claude-skill={cs_data['name']}")
    if fm.get("name") and fm["name"] != dir_name:
        issues.append(f"name mismatch: dir={dir_name} SKILL.md={fm['name']}")

    # 5. Description length
    desc = fm.get("description", "") or cs_data.get("description", "")
    if desc and len(desc) > 80:
        issues.append(f"description too long ({len(desc)} chars, recommend ≤50)")

    # 6. Broken references
    if skill_md.exists():
        text = skill_md.read_text(encoding="utf-8")
        ref_dir = skill_dir / "references"

        def _clean_path(raw: str) -> str:
            """Strip markdown/backtick artifacts and trailing non-path chars."""
            cleaned = re.sub(r"[`*\"\']", "", raw).rstrip(".,;:)")
            # Strip trailing Korean characters (e.g., "file.md에" → "file.md")
            cleaned = re.sub(r"[가-힣]+$", "", cleaned)
            # Strip leading/trailing path separators
            return cleaned.strip("/")

        seen_refs: set[str] = set()

        # Markdown links: [text](references/file.md)
        for m in re.finditer(r"\[.*?\]\((references/[^)]+)\)", text):
            clean = _clean_path(m.group(1))
            if clean in seen_refs:
                continue
            seen_refs.add(clean)
            ref_path = skill_dir / clean
            if not ref_path.exists():
                issues.append(f"broken ref: {clean}")
        # {baseDir}/references/file patterns
        for m in re.finditer(r"\{baseDir\}/references/(\S+)", text):
            clean = _clean_path(m.group(1))
            full = f"references/{clean}"
            if full in seen_refs:
                continue
            seen_refs.add(full)
            ref_path = ref_dir / clean
            if not ref_path.exists():
                issues.append(f"broken ref: {full}")
        # {baseDir}/scripts/file patterns
        for m in re.finditer(r"\{baseDir\}/scripts/(\S+)", text):
            clean = _clean_path(m.group(1))
            script_path = skill_dir / "scripts" / clean
            if not script_path.exists():
                issues.append(f"broken script ref: scripts/{clean}")

    # 7. Orphan references (files in references/ not linked from SKILL.md)
    ref_dir = skill_dir / "references"
    if ref_dir.exists() and skill_md.exists():
        text = skill_md.read_text(encoding="utf-8")
        for ref_file in sorted(ref_dir.iterdir()):
            if ref_file.is_file() and ref_file.name not in text:
                issues.append(f"orphan ref: references/{ref_file.name}")

    return issues


def main():
    skills = find_skills()
    if not skills:
        print("No skills found.")
        return

    total_issues = 0
    healthy = 0
    results = []

    for skill_dir in skills:
        issues = check_skill(skill_dir)
        rel = skill_dir.relative_to(REPO_ROOT)
        results.append((rel, issues))
        if issues:
            total_issues += len(issues)
        else:
            healthy += 1

    # Output
    print(f"=== Skill Health Check ({len(skills)} skills) ===\n")

    for rel, issues in results:
        if issues:
            print(f"⚠ {rel}")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print(f"✓ {rel}")

    print(f"\n--- {healthy}/{len(skills)} healthy, {total_issues} issues ---")
    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
