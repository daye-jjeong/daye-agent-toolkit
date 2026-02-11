#!/usr/bin/env python3
"""
Jarvis News Analyzer - Tier 3 Skill

Reads raw news JSON from stdin, analyzes Ronik impact, formats for Telegram.

TODO (Phase 2 - Next Sprint):
- Implement LLM integration for impact analysis
- Add prioritization logic
- Complete Telegram formatting
- Add error handling
"""

import json
import sys
from datetime import datetime
from typing import List, Dict


def analyze_ronik_impact(item: Dict) -> Dict:
    """
    LLM-powered analysis of news item for Ronik relevance.
    
    Args:
        item: {title, link, source, published, domain}
    
    Returns:
        {
            "opportunity": str,  # 1-line opportunity
            "risk": str,         # 1-line risk
            "action": str        # 1-line suggested action
        }
    """
    # TODO (Phase 2): Call LLM with context:
    # - Ronik focus: robotics, commercial kitchen, retail automation
    # - Ask: opportunity? risk? action?
    
    # Stub implementation for testing
    return {
        "opportunity": "TBD - LLM analysis needed",
        "risk": "TBD - LLM analysis needed",
        "action": "TBD - LLM analysis needed"
    }


def prioritize_items(items: List[Dict]) -> List[Dict]:
    """
    Sort items by relevance/urgency for Ronik.
    
    Uses LLM to score each item (0-10) on:
    - Direct relevance to robotics/kitchen/retail
    - Urgency (funding, acquisition, product launch)
    - Actionability
    
    Args:
        items: List of news items with analysis
    
    Returns:
        Sorted list (highest priority first)
    """
    # TODO (Phase 2): LLM scoring + sort
    
    # Stub: return as-is
    return items


def format_telegram_message(items: List[Dict]) -> str:
    """
    Format analyzed news for Telegram (topic 171).
    
    Output format:
    📰 오늘의 뉴스 (2026-02-03)
    
    1. [Title]
       🔗 source.com
       💡 Opportunity: ...
       ⚠️ Risk: ...
       🎯 Action: ...
    
    2. ...
    
    🎲 Today's Bet: [LLM-suggested experiment/outreach]
    
    Args:
        items: Top prioritized news items with analysis
    
    Returns:
        Formatted markdown string
    """
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"📰 오늘의 뉴스 ({today})",
        ""
    ]
    
    for i, item in enumerate(items[:5], 1):  # Top 5
        analysis = item.get("analysis", {})
        lines.extend([
            f"{i}. {item['title']}",
            f"   🔗 {item.get('domain', item.get('source', 'unknown'))}",
            f"   💡 Opportunity: {analysis.get('opportunity', 'N/A')}",
            f"   ⚠️ Risk: {analysis.get('risk', 'N/A')}",
            f"   🎯 Action: {analysis.get('action', 'N/A')}",
            ""
        ])
    
    # TODO (Phase 2): LLM-generated daily bet
    lines.append("🎲 Today's Bet: TBD (LLM suggestion)")
    
    return "\n".join(lines)


def main():
    """
    Main pipeline: stdin → analyze → prioritize → format → stdout
    """
    try:
        # Read JSON from stdin
        raw_items = json.load(sys.stdin)
        
        if not raw_items:
            print("⚠️ No news items to analyze", file=sys.stderr)
            sys.exit(0)
        
        # Analyze impact (LLM) - Phase 2
        analyzed_items = [
            {**item, "analysis": analyze_ronik_impact(item)}
            for item in raw_items
        ]
        
        # Prioritize (LLM) - Phase 2
        prioritized = prioritize_items(analyzed_items)
        
        # Format for Telegram
        message = format_telegram_message(prioritized)
        
        # Output to stdout (will be piped to clawdbot message send)
        print(message)
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
