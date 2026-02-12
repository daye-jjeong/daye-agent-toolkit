#!/usr/bin/env python3
"""
영수증/장바구니 이미지 파싱 스크립트 (OCR + AI)
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
except ImportError:
    print("❌ 필요한 라이브러리가 설치되지 않았습니다.")
    print("설치 명령어: pip3 install pillow pytesseract")
    print("Tesseract 설치: brew install tesseract tesseract-lang")
    sys.exit(1)

def extract_text_from_image(image_path):
    """이미지에서 텍스트 추출 (OCR)"""
    img = Image.open(image_path)
    
    # 한국어 + 영어 OCR
    text = pytesseract.image_to_string(img, lang='kor+eng')
    
    return text

def parse_items_simple(text):
    """간단한 규칙 기반 파싱"""
    lines = text.strip().split('\n')
    items = []
    
    # 일반적인 패턴: "상품명 수량 가격" 또는 "상품명 가격"
    for line in lines:
        line = line.strip()
        if not line or len(line) < 2:
            continue
        
        # 숫자만 있는 라인은 스킵
        if line.replace(',', '').replace('.', '').isdigit():
            continue
        
        # 합계, 총액 등 키워드 스킵
        skip_keywords = ['합계', '총액', '카드', '현금', '영수증', '감사합니다']
        if any(kw in line for kw in skip_keywords):
            continue
        
        items.append(line)
    
    return items

def main():
    parser = argparse.ArgumentParser(description="영수증/장바구니 이미지 파싱")
    parser.add_argument("--image", required=True, help="이미지 파일 경로")
    parser.add_argument("--auto-add", action="store_true", help="자동으로 vault에 추가")
    
    args = parser.parse_args()
    
    if not Path(args.image).exists():
        print(f"❌ 이미지 파일을 찾을 수 없습니다: {args.image}")
        sys.exit(1)
    
    print("📸 이미지 분석 중...\n")
    
    # OCR 실행
    try:
        text = extract_text_from_image(args.image)
    except Exception as e:
        print(f"❌ OCR 실패: {e}")
        print("\n💡 Tesseract가 설치되지 않았을 수 있습니다.")
        print("   설치: brew install tesseract tesseract-lang")
        sys.exit(1)
    
    print("📝 **추출된 텍스트:**")
    print(text)
    print("\n" + "="*50 + "\n")
    
    # 간단한 파싱
    items = parse_items_simple(text)
    
    print("🛒 **인식된 항목:**")
    if items:
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item}")
    else:
        print("  (항목을 인식하지 못했습니다)")
    
    print("\n💡 **다음 단계:**")
    print("  1. 에이전트에게 '이 항목들을 냉장고에 추가해줘'라고 요청")
    print("  2. 또는 수동으로 add_item.py 사용")
    
    # 파싱 결과 저장
    cache_dir = Path.home() / ".cache" / "pantry-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = cache_dir / "last_parse.txt"
    with open(result_file, "w") as f:
        f.write("추출된 텍스트:\n")
        f.write(text)
        f.write("\n\n인식된 항목:\n")
        for item in items:
            f.write(f"  • {item}\n")
    
    print(f"\n💾 결과 저장: {result_file}")

if __name__ == "__main__":
    main()
