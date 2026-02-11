#!/usr/bin/env python3
"""
주간 냉장고 정리 체크 스크립트
"""

from notion_client import NotionPantryClient
from pathlib import Path

def main():
    client = NotionPantryClient()
    
    # 전체 식재료 조회
    all_items = client.query_items()
    
    report_lines = []
    report_lines.append("🗓️ **주간 냉장고 정리 체크**\n")
    
    # 통계
    total = len(all_items)
    by_location = {"냉장": 0, "냉동": 0, "실온": 0}
    by_status = {"재고 있음": 0, "부족": 0, "만료": 0}
    
    for item in all_items:
        props = item["properties"]
        location = props.get("Location", {}).get("select", {}).get("name", "")
        status = props.get("Status", {}).get("select", {}).get("name", "재고 있음")
        
        if location in by_location:
            by_location[location] += 1
        if status in by_status:
            by_status[status] += 1
    
    report_lines.append(f"**전체 식재료:** {total}개")
    report_lines.append(f"  • 냉장: {by_location['냉장']}개")
    report_lines.append(f"  • 냉동: {by_location['냉동']}개")
    report_lines.append(f"  • 실온: {by_location['실온']}개")
    report_lines.append("")
    
    report_lines.append("**상태 요약:**")
    report_lines.append(f"  ✅ 재고 있음: {by_status['재고 있음']}개")
    report_lines.append(f"  ⚠️ 부족: {by_status['부족']}개")
    report_lines.append(f"  ❌ 만료: {by_status['만료']}개")
    report_lines.append("")
    
    # 유통기한 체크
    expiry_result = client.check_expiring_items(days_ahead=7)
    
    if expiry_result["expiring"]:
        report_lines.append(f"⏰ **이번 주 유통기한 임박:** {len(expiry_result['expiring'])}개")
        for item in expiry_result["expiring"][:5]:  # 최대 5개만 표시
            report_lines.append(f"  • {item['name']} - {item['days_left']}일 남음")
        report_lines.append("")
    
    if expiry_result["expired"]:
        report_lines.append(f"🗑️ **정리 필요 (만료):** {len(expiry_result['expired'])}개")
        report_lines.append("")
    
    report_lines.append("💡 **추천 행동:**")
    if expiry_result["expired"]:
        report_lines.append("  • 만료된 식재료를 정리하세요")
    if expiry_result["expiring"]:
        report_lines.append("  • 유통기한 임박 식재료를 우선 소비하세요")
    if by_status["부족"] > 0:
        report_lines.append("  • 장보기 목록을 확인하세요")
    if not expiry_result["expired"] and not expiry_result["expiring"] and by_status["부족"] == 0:
        report_lines.append("  ✨ 냉장고 관리가 잘 되고 있습니다!")
    
    report_text = "\n".join(report_lines)
    
    # 콘솔 출력
    print(report_text)
    
    # 파일 저장
    cache_dir = Path.home() / ".cache" / "pantry-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    report_file = cache_dir / "weekly_report.txt"
    with open(report_file, "w") as f:
        f.write(report_text)
    
    # 임시 파일 (cron용)
    with open("/tmp/pantry_weekly_report.txt", "w") as f:
        f.write(report_text)

if __name__ == "__main__":
    main()
