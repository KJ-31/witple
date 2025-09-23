"""
DB 기반 데모 모드 관리 모듈
"""
import os
from typing import Optional, List
from sqlalchemy import text
from database import engine as shared_engine

class DemoModeManager:
    """데모 모드 DB 기반 관리 클래스"""

    def __init__(self):
        # DB에서 초기값 로드
        self._load_from_db()

    def _load_from_db(self):
        """DB에서 설정값 로드"""
        with shared_engine.connect() as conn:
            # 데모 모드 상태 로드
            demo_mode_query = text("SELECT setting_value FROM app_settings WHERE setting_key = 'demo_mode'")
            result = conn.execute(demo_mode_query).fetchone()
            self._demo_mode = result.setting_value.lower() == 'true' if result else False

            # 데모 장소 목록 로드
            demo_places_query = text("SELECT setting_value FROM app_settings WHERE setting_key = 'demo_place_names'")
            result = conn.execute(demo_places_query).fetchone()
            if result:
                self._demo_places = [place.strip() for place in result.setting_value.split(',')]
            else:
                self._demo_places = []

    def _save_demo_mode_to_db(self, value: bool):
        """데모 모드 상태를 DB에 저장"""
        with shared_engine.connect() as conn:
            query = text("""
                INSERT INTO app_settings (setting_key, setting_value, description)
                VALUES ('demo_mode', :value, '데모 모드 활성화 여부 (true/false)')
                ON CONFLICT (setting_key)
                DO UPDATE SET setting_value = :value
            """)
            conn.execute(query, {"value": str(value).lower()})
            conn.commit()
            self._demo_mode = value

    def is_demo_mode(self) -> bool:
        """현재 데모 모드 상태 반환 (DB에서 실시간 조회)"""
        self._load_from_db()
        return self._demo_mode

    def enable_demo_mode(self) -> str:
        """데모 모드 활성화"""
        self._save_demo_mode_to_db(True)
        return "🎭 데모 모드가 활성화되었습니다. 서울 지역 질문 시 고정된 장소들이 반환됩니다."

    def disable_demo_mode(self) -> str:
        """데모 모드 비활성화"""
        self._save_demo_mode_to_db(False)
        return "✅ 데모 모드가 비활성화되었습니다. 일반 검색 모드로 동작합니다."

    def toggle_demo_mode(self) -> str:
        """데모 모드 토글"""
        if self._demo_mode:
            return self.disable_demo_mode()
        else:
            return self.enable_demo_mode()

    def get_demo_places(self) -> list:
        """데모용 고정 장소 목록 반환 (DB에서 실시간 조회)"""
        self._load_from_db()
        return [place.strip() for place in self._demo_places if place.strip()]

    def get_status(self) -> dict:
        """현재 데모 모드 상태 정보 반환"""
        self._load_from_db()
        return {
            "demo_mode": self._demo_mode,
            "demo_places_count": len(self.get_demo_places()),
            "demo_places": self.get_demo_places()
        }

# 전역 데모 모드 매니저 인스턴스
_demo_manager = DemoModeManager()

def get_demo_manager() -> DemoModeManager:
    """데모 모드 매니저 인스턴스 반환"""
    return _demo_manager

def is_demo_mode() -> bool:
    """데모 모드 상태 확인 (기존 호환성을 위한 함수)"""
    return _demo_manager.is_demo_mode()

def get_demo_places() -> list:
    """데모용 장소 목록 반환 (기존 호환성을 위한 함수)"""
    return _demo_manager.get_demo_places()