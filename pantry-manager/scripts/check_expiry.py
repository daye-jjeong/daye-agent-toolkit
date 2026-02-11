#!/usr/bin/env python3
"""
유통기한 체크 스크립트
"""

from notion_client import NotionPantryClient
from pathlib import Path

def main():
    client = NotionPantryClient()
    
    result = client.check_expiring_items(days_ahead=3)
    
    report_lines = []
    report_lines.append("🧊 **냉장고 유통기한 체크**\n")
    
    if result["expired"]:
        report_lines.append("⚠️ **만료된 식재료:**")
        for item in result["expired"]:
            report_lines.append(
                f"  • {item['name']} ({item['category']}, {item['location']}) "
                f"- {item['days_ago']}일 전 만료"
            )
        report_lines.append("")
    
    if result["expiring"]:
        report_lines.append("⏰ **유통기한 임박 (3일 이내):**")
        for item in result["expiring"]:
            emoji = "🔴" if item["days_left"] == 0 else "🟡"
            report_lines.append(
                f"  {emoji} {item['name']} ({item['category']}, {item['location']}) "
                f"- {item['days_left']}일 남음"
            )
        report_lines.append("")
    
    if not result["expired"] and not result["expiring"]:
        report_lines.append("✅ 모든 식재료가 안전합니다!")
    
    report_text = "\n".join(report_lines)
    
    # 콘솔 출력
    print(report_text)
    
    # 파일 저장 (텔레그램 전송용)
    cache_dir = Path.home() / ".cache" / "pantry-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    report_file = cache_dir / "expiry_report.txt"
    with open(report_file, "w") as f:
        f.write(report_text)
    
    # 임시 파일도 생성 (cron용)
    with open("/tmp/pantry_expiry_report.txt", "w") as f:
        f.write(report_text)

if __name__ == "__main__":
    main()
