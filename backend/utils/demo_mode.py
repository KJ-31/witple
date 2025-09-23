"""
실시간 데모 모드 관리 모듈
"""
import os
from typing import Optional

class DemoModeManager:
    """데모 모드 실시간 관리 클래스"""

    def __init__(self):
        # 환경변수에서 초기값 로드
        initial_mode = os.getenv('DEMO_MODE', 'false').lower() == 'true'
        self._demo_mode = initial_mode
        self._demo_places = os.getenv('DEMO_PLACE_NAMES',
            '달맞이근린공원,한강 다리밑 영화제,응암동돈까스,서울 중앙시장,서대문형무소역사관,켄싱턴호텔 여의도,한강 종이비행기 축제,한강').split(',')

    def is_demo_mode(self) -> bool:
        """현재 데모 모드 상태 반환"""
        return self._demo_mode

    def enable_demo_mode(self) -> str:
        """데모 모드 활성화"""
        self._demo_mode = True
        return "🎭 데모 모드가 활성화되었습니다. 서울 지역 질문 시 고정된 장소들이 반환됩니다."

    def disable_demo_mode(self) -> str:
        """데모 모드 비활성화"""
        self._demo_mode = False
        return "✅ 데모 모드가 비활성화되었습니다. 일반 검색 모드로 동작합니다."

    def toggle_demo_mode(self) -> str:
        """데모 모드 토글"""
        if self._demo_mode:
            return self.disable_demo_mode()
        else:
            return self.enable_demo_mode()

    def get_demo_places(self) -> list:
        """데모용 고정 장소 목록 반환"""
        return [place.strip() for place in self._demo_places if place.strip()]

    def get_status(self) -> dict:
        """현재 데모 모드 상태 정보 반환"""
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