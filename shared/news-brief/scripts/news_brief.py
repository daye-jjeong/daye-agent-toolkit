#!/usr/bin/env python3
"""Generate a ranked daily news/trends brief from RSS feeds.

- Prefers RSS (stable, low rate-limit) over web search.
- Clusters similar articles → scores by coverage, source tier, recency, entity density.
- Produces compact text suitable for Slack/Telegram.

This script does NOT attempt to be a crawler. Keep feeds curated.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import feedparser

from html_source import fetch_entries as fetch_html_entries
from kst_utils import format_pub_kst, parse_pub_date

# Low-signal patterns filtered from general news
NOISE_PATTERNS = re.compile(
    r"\[부고\]|\[인사\]|부고|부음|별세|발인|빈소|조문|부친상|모친상|"
    r"\[알림\]|\[공고\]|\[광고\]|\[스포츠\]|포토\]|사진\]",
    re.IGNORECASE,
)

# Feed URL → category tag mapping
_FEED_TAGS: list[tuple[str, str]] = [
    ("reuters.com/reuters/business", "경제"),
    ("yna.co.kr/rss/economy", "경제"),
    ("reuters.com", "국제"),
    ("nytimes.com", "국제"),
    ("bbc", "국제"),
    ("yna.co.kr", "국내"),
    ("donga.com", "국내"),
    ("hankyung.com", "국내"),
]

# Feed URL → source authority tier (1=highest, 3=lowest)
_SOURCE_TIERS: list[tuple[str, int]] = [
    # Tier 1: Major wire services, top papers
    ("reuters.com", 1),
    ("nytimes.com", 1),
    ("bbc", 1),
    ("yna.co.kr", 1),
    # Tier 2: Quality outlets
    ("hankyung.com", 2),
    ("donga.com", 2),
    ("therobotreport.com", 2),
    ("spectrum.ieee.org", 2),
    ("techcrunch.com", 2),
    ("qsrmagazine.com", 2),
    ("restaurantbusinessonline.com", 2),
    ("reutersagency.com", 2),
]

# Recency decay constant: half-life ~14 hours
_DECAY_LAMBDA = 0.05


def _strip_html(s: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:200] if s else ""


def detect_feed_tag(feed_url: str) -> str:
    """Detect category tag from feed URL."""
    for pattern, tag in _FEED_TAGS:
        if pattern in feed_url:
            return tag
    return ""


def detect_source_tier(feed_url: str) -> int:
    """Detect source authority tier from feed URL."""
    for pattern, tier in _SOURCE_TIERS:
        if pattern in feed_url:
            return tier
    return 3


@dataclass
class Item:
    title: str
    link: str
    source: str
    published: str | None
    description: str = ""
    tag: str = ""
    source_tier: int = 2
    score: float = 0.0
    coverage: int = 1


def norm_title(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    # strip common boilerplate
    s = re.sub(r"\b(update|live|breaking|exclusive|report)\b", "", s)
    s = re.sub(r"[^a-z0-9가-힣 ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def load_list(path: str) -> list[str]:
    out: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line)
    return out


def fetch_items(feeds: list[str]) -> list[Item]:
    items: list[Item] = []
    for u in feeds:
        d = feedparser.parse(u)
        src = domain(u) or (d.feed.get("title") if hasattr(d, "feed") else "")
        tag = detect_feed_tag(u)
        tier = detect_source_tier(u)
        for e in d.entries[:30]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            if not title or not link:
                continue
            desc = _strip_html(e.get("summary") or e.get("description") or "")
            items.append(
                Item(
                    title=title,
                    link=link,
                    source=src or domain(link),
                    published=e.get("published") or e.get("updated"),
                    description=desc,
                    tag=tag,
                    source_tier=tier,
                )
            )
    return items


def filter_by_time(items: list[Item], since_hours: float) -> list[Item]:
    """Keep only items published within the last `since_hours` hours."""
    if since_hours <= 0:
        return items
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    for it in items:
        dt = parse_pub_date(it.published)
        if dt is None:
            # No date info — keep it (benefit of doubt)
            out.append(it)
            continue
        age_hours = (now - dt).total_seconds() / 3600
        if age_hours <= since_hours:
            out.append(it)
    return out


def filter_by_keywords(items: list[Item], keywords: list[str]) -> list[Item]:
    if not keywords:
        return items
    kws = [k.lower() for k in keywords]
    out: list[Item] = []
    for it in items:
        t = it.title.lower()
        if any(k in t for k in kws):
            out.append(it)
    return out


# ── Entity extraction ────────────────────────────────────────────────

# Common Korean trailing particles (조사) to strip
_KO_PARTICLES = re.compile(
    r"(?:은|는|이|가|에|을|를|도|의|와|과|로|에서|으로|에게|까지|부터"
    r"|만|라고|라며|에도|이라|에는|으로는|으로서|에게는|과는)$"
)


def extract_entities(title: str) -> set[str]:
    """Extract entity candidates from a title.

    Korean: 2+ character words after stripping trailing particles.
    English: 3+ character words (lowercased).
    No external NLP dependencies — heuristic extraction only.
    """
    entities: set[str] = set()
    # Strip brackets, quotes, punctuation for cleaner extraction
    t = re.sub(r"[\[\]()\"\"''·…「」『』〈〉《》%↑↓]", " ", title)

    # Korean: extract 2+ char Hangul sequences, strip particles
    for m in re.findall(r"[가-힣]{2,}", t):
        if len(m) >= 3:
            # Only strip particles from 3+ char words;
            # 2-char words (한은, 금리, 미국) are kept as-is to avoid
            # destroying abbreviations (한은 → 한 + 은(particle) → 삭제)
            cleaned = _KO_PARTICLES.sub("", m)
            if len(cleaned) >= 2:
                entities.add(cleaned)
        else:
            entities.add(m)

    # English: 3+ char words (proper nouns, terms)
    for m in re.findall(r"[a-zA-Z]{3,}", t):
        entities.add(m.lower())

    return entities


def _entity_overlap_count(ent_a: set[str], ent_b: set[str]) -> int:
    """Count entity matches including substring containment.

    "금리" matches "기준금리" or "시장금리" (substring relationship).
    Each entity in B is matched at most once.
    """
    count = 0
    used_b: set[str] = set()
    for a in ent_a:
        for b in ent_b:
            if b in used_b:
                continue
            if a == b or (len(a) >= 2 and len(b) >= 2 and (a in b or b in a)):
                count += 1
                used_b.add(b)
                break
    return count


def _should_cluster(
    nt_a: str,
    nt_b: str,
    ent_a: set[str],
    ent_b: set[str],
    sim_threshold: float = 0.65,
    min_entity_overlap: int = 2,
) -> bool:
    """Decide if two articles should be in the same cluster.

    Two methods (either triggers clustering):
    1. Title similarity >= threshold (catches near-duplicates)
    2. Entity overlap >= min_entity_overlap (catches same-event different-angle)
    """
    # Method 1: title text similarity
    if similar(nt_a, nt_b) >= sim_threshold:
        return True
    # Method 2: shared key entities
    if len(ent_a) < 2 or len(ent_b) < 2:
        return False
    return _entity_overlap_count(ent_a, ent_b) >= min_entity_overlap


# ── Clustering + Scoring ─────────────────────────────────────────────


def cluster_by_story(
    items: list[Item],
    threshold: float = 0.65,
    min_entity_overlap: int = 2,
) -> list[list[Item]]:
    """Group articles covering the same story.

    Two-signal clustering:
    1. Normalized title similarity >= threshold (near-duplicates)
    2. Entity overlap >= min_entity_overlap (same event, different angle)

    Uses seed article's entities to prevent cluster inflation.
    """
    clusters: list[list[Item]] = []
    cluster_norms: list[str] = []
    cluster_entities: list[set[str]] = []
    seen_links: set[str] = set()

    for it in items:
        # Exact URL dedup
        if it.link in seen_links:
            continue
        seen_links.add(it.link)

        nt = norm_title(it.title)
        if not nt:
            continue

        ents = extract_entities(it.title)

        placed = False
        for i, cn in enumerate(cluster_norms):
            if _should_cluster(
                nt, cn, ents, cluster_entities[i], threshold, min_entity_overlap
            ):
                clusters[i].append(it)
                placed = True
                break
        if not placed:
            clusters.append([it])
            cluster_norms.append(nt)
            cluster_entities.append(ents)

    return clusters


def title_entity_density(title: str) -> float:
    """Score how information-dense a title is (0.0 - 1.0).

    High: "Samsung acquires $2.3B robotics firm Boston Dynamics"
    Low:  "Things are changing in the industry"
    """
    words = title.split()
    if not words:
        return 0.0

    signals = 0.0
    for i, w in enumerate(words):
        # Proper nouns (capitalized, not sentence-start)
        if len(w) > 1 and w[0].isupper() and i > 0:
            signals += 1
        # Numbers (dollar amounts, percentages, dates)
        if any(c.isdigit() for c in w):
            signals += 1.5
        # Korean proper nouns (quoted or specific patterns)
        if w.startswith("'") or w.startswith('"'):
            signals += 0.5

    return min(1.0, signals / max(len(words), 1))


def _pick_best(cluster: list[Item]) -> Item:
    """Pick the best representative article from a cluster.

    Prefers: lowest tier (best source) → most recent → longest description.
    """
    return min(
        cluster,
        key=lambda it: (
            it.source_tier,
            # Negate timestamp so more recent = smaller
            -(parse_pub_date(it.published) or datetime.min.replace(
                tzinfo=timezone.utc
            )).timestamp(),
            -len(it.description),
        ),
    )


def rank_clusters(clusters: list[list[Item]]) -> list[Item]:
    """Score each cluster and return ranked items (best article per cluster)."""
    now = datetime.now(timezone.utc)
    ranked: list[Item] = []

    for cluster in clusters:
        best = _pick_best(cluster)

        # 1. Coverage breadth: how many different sources report this story
        sources = {it.source for it in cluster}
        coverage = len(sources)
        coverage_score = math.log2(coverage + 1) * 3

        # 2. Source authority: tier 1=3, tier 2=2, tier 3=1
        source_score = max(1, 4 - best.source_tier)

        # 3. Recency: exponential decay, half-life ~14 hours
        dt = parse_pub_date(best.published)
        if dt:
            hours_old = max(0, (now - dt).total_seconds() / 3600)
            recency = math.exp(-_DECAY_LAMBDA * hours_old)
        else:
            recency = 0.5  # unknown time = moderate penalty

        # 4. Title entity density
        entity_bonus = title_entity_density(best.title) * 2

        raw = coverage_score + source_score + entity_bonus
        best.score = round(raw * recency, 2)
        best.coverage = coverage

        # Inherit tag from best-tagged article in cluster
        if not best.tag:
            for it in cluster:
                if it.tag:
                    best.tag = it.tag
                    break

        ranked.append(best)

    ranked.sort(key=lambda it: it.score, reverse=True)
    return ranked


# ── Legacy dedupe (kept for backward compat) ─────────────────────────


def dedupe(items: list[Item], threshold: float = 0.86) -> list[Item]:
    seen_links: set[str] = set()
    kept: list[Item] = []
    kept_norm: list[str] = []

    for it in items:
        if it.link in seen_links:
            continue
        nt = norm_title(it.title)
        if not nt:
            continue
        dup = False
        for knt in kept_norm:
            if similar(nt, knt) >= threshold:
                dup = True
                break
        if dup:
            continue
        kept.append(it)
        kept_norm.append(nt)
        seen_links.add(it.link)

    return kept


def fetch_web_items(sources_path: str, keywords: list[str], since_hours: float) -> list[Item]:
    """Fetch items from non-RSS sources (those with 'scrape' config) in rss_sources.json."""
    with open(sources_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    sources = data.get("sources", data) if isinstance(data, dict) else data

    items: list[Item] = []
    for src in sources:
        scrape_cfg = src.get("scrape")
        if not scrape_cfg:
            continue
        url = src.get("url", "")
        if not url:
            continue

        entries = fetch_html_entries(url, scrape_cfg, since_hours)
        tier = detect_source_tier(url)
        src_domain = domain(url) or src.get("name", url)

        for e in entries:
            title = e.get("title", "").strip()
            link = e.get("link", "").strip()
            if not title or not link:
                continue
            items.append(Item(
                title=title,
                link=link,
                source=src_domain,
                published=e.get("published"),
                description=e.get("summary", ""),
                tag="",
                source_tier=tier,
            ))

    if keywords:
        items = filter_by_keywords(items, keywords)
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", required=True, help="Path to rss_feeds.txt")
    ap.add_argument("--keywords", required=False, help="Path to keywords.txt")
    ap.add_argument("--max-items", type=int, default=5)
    ap.add_argument("--since", type=float, default=0,
                    help="Only include items published within this many hours (0=no filter)")
    ap.add_argument("--cluster-threshold", type=float, default=0.65,
                    help="Title similarity threshold for story clustering (default: 0.65)")
    ap.add_argument("--no-rank", action="store_true",
                    help="Disable scoring/ranking, use legacy dedupe + time order")
    ap.add_argument("--output-format", choices=["text", "json"], default="text",
                    help="Output format: text (Telegram) or json (for compose-newspaper.py)")
    ap.add_argument("--web-sources",
                    help="rss_sources.json path — non-RSS sources with 'scrape' config")
    args = ap.parse_args()

    feeds = load_list(args.feeds)
    keywords = load_list(args.keywords) if args.keywords else []

    items = fetch_items(feeds)
    # Merge non-RSS web sources
    if args.web_sources:
        since = args.since if args.since > 0 else 24
        web_items = fetch_web_items(args.web_sources, keywords, since)
        items.extend(web_items)
    # Filter noise (부고, 인사, 광고 등)
    items = [it for it in items if not NOISE_PATTERNS.search(it.title)]
    if args.since > 0:
        items = filter_by_time(items, args.since)
    items = filter_by_keywords(items, keywords)

    if args.no_rank:
        # Legacy behavior: dedupe + time order
        items = dedupe(items)[: args.max_items]
    else:
        # Cluster by story → score → rank
        clusters = cluster_by_story(items, threshold=args.cluster_threshold)
        items = rank_clusters(clusters)[: args.max_items]

    # JSON output for compose-newspaper.py
    if args.output_format == "json":
        out = []
        for it in items:
            obj: dict = {
                "title": it.title,
                "link": it.link,
                "source": it.source,
                "published": format_pub_kst(it.published),
                "domain": domain(it.link),
                "tag": it.tag,
            }
            if it.description:
                obj["description"] = it.description
            if not args.no_rank:
                obj["score"] = it.score
                obj["coverage"] = it.coverage
            out.append(obj)
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        print()  # trailing newline
        return

    # Default text output (Telegram)
    today = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = []
    lines.append(f"[뉴스/트렌드] 로봇·조리자동화 데일리 브리프 — {today}")

    if not items:
        lines.append("- 오늘은 RSS에서 관련 뉴스를 못 찾았어(피드/키워드 확인 필요).")
        print("\n".join(lines))
        return

    lines.append("- Top headlines")
    for it in items:
        score_str = f" [score:{it.score}]" if not args.no_rank else ""
        lines.append(f"  - {it.title} ({it.source}){score_str}")
        lines.append(f"    {it.link}")

    # Keep impact section as placeholders; LLM can rewrite, but this stays deterministic
    lines.append("- Ronik impact (초안)")
    for it in items:
        lines.append(f"  - {it.title.split(' — ')[0][:60]}...")
        lines.append("    • 기회: (작성 필요)")
        lines.append("    • 리스크: (작성 필요)")
        lines.append("    • 액션: (작성 필요)")

    lines.append("- Today's bet: (작성 필요)")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
