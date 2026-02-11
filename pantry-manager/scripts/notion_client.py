#!/usr/bin/env python3
"""
Notion API 클라이언트
"""

import os
import requests
from datetime import datetime, timedelta
from pathlib import Path

class NotionPantryClient:
    def __init__(self):
        # API 키 로드 (NEW HOME 워크스페이스)
        key_path = Path.home() / ".config" / "notion" / "api_key_daye_personal"
        with open(key_path) as f:
            self.api_key = f.read().strip()
        
        # DB ID 로드
        db_id_path = Path(__file__).parent.parent / "config" / "notion_db_id.txt"
        if db_id_path.exists():
            with open(db_id_path) as f:
                self.database_id = f.read().strip()
        else:
            raise FileNotFoundError(
                f"Notion DB ID 파일이 없습니다: {db_id_path}\n"
                "SKILL.md를 참조하여 설정해주세요."
            )
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
    
    def add_item(self, name, category, quantity, unit, location, 
                 expiry_date=None, purchase_date=None, notes=""):
        """식재료 추가"""
        if purchase_date is None:
            purchase_date = datetime.now().strftime("%Y-%m-%d")
        
        properties = {
            "Name": {"title": [{"text": {"content": name}}]},
            "Category": {"select": {"name": category}},
            "Quantity": {"number": quantity},
            "Unit": {"select": {"name": unit}},
            "Location": {"select": {"name": location}},
            "Purchase Date": {"date": {"start": purchase_date}},
            "Status": {"select": {"name": "재고 있음"}}
        }
        
        if expiry_date:
            properties["Expiry Date"] = {"date": {"start": expiry_date}}
        
        if notes:
            properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}
        
        payload = {"parent": {"database_id": self.database_id}, "properties": properties}
        
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code == 200:
            return {"success": True, "page_id": response.json()["id"]}
        else:
            return {"success": False, "error": response.text}
    
    def query_items(self, filter_dict=None):
        """식재료 조회"""
        payload = {"database_id": self.database_id}
        
        if filter_dict:
            payload["filter"] = filter_dict
        
        response = requests.post(
            f"https://api.notion.com/v1/databases/{self.database_id}/query",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()["results"]
        else:
            raise Exception(f"Query failed: {response.text}")
    
    def check_expiring_items(self, days_ahead=3):
        """유통기한 임박/만료 항목 체크"""
        all_items = self.query_items()
        
        today = datetime.now().date()
        threshold = today + timedelta(days=days_ahead)
        
        expiring = []
        expired = []
        
        for item in all_items:
            props = item["properties"]
            
            # 유통기한 확인
            expiry_prop = props.get("Expiry Date", {})
            if not expiry_prop.get("date"):
                continue
            
            expiry_str = expiry_prop["date"]["start"]
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            
            # 이름 추출
            name = props["Name"]["title"][0]["text"]["content"] if props["Name"]["title"] else "Unknown"
            
            # 카테고리, 위치 추출
            category = props.get("Category", {}).get("select", {}).get("name", "")
            location = props.get("Location", {}).get("select", {}).get("name", "")
            
            days_left = (expiry_date - today).days
            
            if days_left < 0:
                expired.append({
                    "name": name,
                    "expiry_date": expiry_str,
                    "days_ago": abs(days_left),
                    "category": category,
                    "location": location
                })
            elif days_left <= days_ahead:
                expiring.append({
                    "name": name,
                    "expiry_date": expiry_str,
                    "days_left": days_left,
                    "category": category,
                    "location": location
                })
        
        return {"expiring": expiring, "expired": expired}
    
    def update_item_status(self, page_id, status):
        """아이템 상태 업데이트"""
        payload = {
            "properties": {
                "Status": {"select": {"name": status}}
            }
        }
        
        response = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=self.headers,
            json=payload
        )
        
        return response.status_code == 200
    
    def get_all_items_by_location(self, location=None):
        """위치별 식재료 목록"""
        filter_dict = None
        if location:
            filter_dict = {
                "property": "Location",
                "select": {"equals": location}
            }
        
        items = self.query_items(filter_dict)
        
        result = []
        for item in items:
            props = item["properties"]
            name = props["Name"]["title"][0]["text"]["content"] if props["Name"]["title"] else "Unknown"
            category = props.get("Category", {}).get("select", {}).get("name", "")
            quantity = props.get("Quantity", {}).get("number", 0)
            unit = props.get("Unit", {}).get("select", {}).get("name", "")
            
            result.append({
                "name": name,
                "category": category,
                "quantity": quantity,
                "unit": unit
            })
        
        return result
