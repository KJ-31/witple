"""
최적화된 장소 매칭 시스템
"""
from functools import lru_cache
from cachetools import TTLCache
import hashlib
import re
from typing import List, Dict, Any, Set, Optional, Tuple
import time
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class MatchResult:
    """매칭 결과"""
    day_number: int
    confidence: float
    matched_schedule_item: Optional[Dict] = None
    match_type: str = "none"  # exact, partial, category, default


class OptimizedPlaceMatcher:
    """캐싱과 인덱싱을 활용한 고성능 장소 매칭"""

    def __init__(self, cache_ttl: int = 3600, cache_maxsize: int = 1000):
        # 캐시 설정
        self.cache = TTLCache(maxsize=cache_maxsize, ttl=cache_ttl)

        # 인덱스
        self.normalized_places_index: Dict[str, Dict] = {}  # 정규화된 장소명 -> 장소 정보
        self.itinerary_index: Dict[str, Dict] = {}         # 일정별 인덱스
        self.category_index: Dict[str, List[int]] = defaultdict(list)  # 카테고리별 일차

        # 성능 메트릭
        self.metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "index_builds": 0,
            "match_attempts": 0
        }

    @lru_cache(maxsize=2000)
    def normalize_place_name(self, place_name: str) -> str:
        """장소명 정규화 (LRU 캐시 적용)"""
        if not place_name:
            return ""

        # 효율적인 정규화 로직
        cleaned = place_name.strip().lower()

        # 한글, 영숫자, 공백만 유지
        cleaned = ''.join(char for char in cleaned
                         if char.isalnum() or char.isspace() or ord(char) >= 0xAC00)

        # 연속된 공백을 하나로 변경
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # 일반적인 접미사 제거 (성능 최적화)
        suffixes = ['카페', '레스토랑', '식당', '박물관', '미술관', '공원', '해변', '시장', '호텔', '펜션']
        for suffix in suffixes:
            if cleaned.endswith(suffix) and len(cleaned) > len(suffix):
                base_name = cleaned[:-len(suffix)].strip()
                if len(base_name) >= 2:  # 최소 길이 확인
                    cleaned = base_name
                    break

        return cleaned

    def build_itinerary_index(self, itinerary: List[Dict]) -> str:
        """일정 인덱스 구축"""
        # 일정 해시 생성 (캐시 키용)
        itinerary_hash = hashlib.md5(str(itinerary).encode()).hexdigest()[:8]

        if itinerary_hash in self.itinerary_index:
            return itinerary_hash

        print(f"🏗️ 일정 인덱스 구축 시작: {len(itinerary)}일차")
        self.metrics["index_builds"] += 1

        # 일차별 정규화된 장소 매핑
        day_places_index = {}
        category_day_mapping = defaultdict(set)

        for day_info in itinerary:
            day_num = day_info.get("day", 1)
            day_places = []

            for schedule in day_info.get("schedule", []):
                # 다양한 필드에서 장소명 추출
                place_names = self._extract_place_names_from_schedule(schedule)

                for place_name_raw in place_names:
                    if place_name_raw:
                        normalized = self.normalize_place_name(place_name_raw)
                        if normalized:
                            day_places.append({
                                'original': place_name_raw,
                                'normalized': normalized,
                                'schedule_item': schedule
                            })

                            # 카테고리별 인덱싱
                            category = self._extract_category_from_schedule(schedule)
                            if category:
                                category_day_mapping[category].add(day_num)

            day_places_index[day_num] = day_places

        # 인덱스 저장
        self.itinerary_index[itinerary_hash] = {
            'day_places': day_places_index,
            'category_mapping': dict(category_day_mapping),
            'total_days': len(itinerary),
            'build_time': time.time()
        }

        print(f"✅ 일정 인덱스 구축 완료: {len(day_places_index)}일차, "
              f"{sum(len(places) for places in day_places_index.values())}개 장소")

        return itinerary_hash

    def _extract_place_names_from_schedule(self, schedule: Dict) -> List[str]:
        """스케줄 항목에서 장소명 추출"""
        possible_fields = [
            "place_name", "place", "name", "location",
            "venue", "attraction", "restaurant"
        ]

        place_names = []

        # 직접 필드에서 추출
        for field in possible_fields:
            if schedule.get(field):
                place_names.append(str(schedule[field]))

        # place_info 내부에서 추출
        if schedule.get("place_info"):
            place_info = schedule["place_info"]
            for field in possible_fields:
                if place_info.get(field):
                    place_names.append(str(place_info[field]))

        return place_names

    def _extract_category_from_schedule(self, schedule: Dict) -> Optional[str]:
        """스케줄 항목에서 카테고리 추출"""
        category_fields = ["category", "type", "classification"]

        for field in category_fields:
            if schedule.get(field):
                return str(schedule[field]).lower()

            if schedule.get("place_info", {}).get(field):
                return str(schedule["place_info"][field]).lower()

        # 설명에서 카테고리 추론
        description = schedule.get("description", "").lower()
        if any(keyword in description for keyword in ["식당", "맛집", "음식"]):
            return "식당"
        elif any(keyword in description for keyword in ["관광", "명소", "박물관"]):
            return "관광지"

        return None

    def find_day_for_place(self, place_name: str, itinerary: List[Dict]) -> MatchResult:
        """캐시를 활용한 고성능 장소-일차 매칭"""
        self.metrics["match_attempts"] += 1

        # 일정 인덱스 구축
        itinerary_hash = self.build_itinerary_index(itinerary)

        # 캐시 키 생성
        place_normalized = self.normalize_place_name(place_name)
        cache_key = f"{place_normalized}:{itinerary_hash}"

        # 캐시에서 조회
        if cache_key in self.cache:
            self.metrics["cache_hits"] += 1
            cached_result = self.cache[cache_key]
            print(f"🎯 캐시 히트: '{place_name}' -> {cached_result.day_number}일차")
            return cached_result

        self.metrics["cache_misses"] += 1

        # 실제 매칭 수행
        result = self._perform_matching(place_name, place_normalized, itinerary_hash)

        # 결과 캐싱
        self.cache[cache_key] = result

        print(f"🔍 매칭 결과: '{place_name}' -> {result.day_number}일차 "
              f"(신뢰도: {result.confidence:.2f}, 타입: {result.match_type})")

        return result

    def _perform_matching(self, original_place: str, normalized_place: str, itinerary_hash: str) -> MatchResult:
        """실제 매칭 로직"""
        index_data = self.itinerary_index[itinerary_hash]
        day_places = index_data['day_places']

        # 1단계: 정확 매칭
        for day_num, places_list in day_places.items():
            for place_data in places_list:
                if normalized_place == place_data['normalized']:
                    return MatchResult(
                        day_number=day_num,
                        confidence=1.0,
                        matched_schedule_item=place_data['schedule_item'],
                        match_type="exact"
                    )

        # 2단계: 부분 매칭 (포함 관계)
        best_match = None
        best_confidence = 0.0

        for day_num, places_list in day_places.items():
            for place_data in places_list:
                schedule_normalized = place_data['normalized']

                # 양방향 포함 관계 확인
                confidence = self._calculate_similarity_confidence(normalized_place, schedule_normalized)

                if confidence > 0.5 and confidence > best_confidence:
                    best_match = MatchResult(
                        day_number=day_num,
                        confidence=confidence,
                        matched_schedule_item=place_data['schedule_item'],
                        match_type="partial"
                    )
                    best_confidence = confidence

        if best_match:
            return best_match

        # 3단계: 카테고리 기반 매칭
        category_result = self._match_by_category(original_place, index_data)
        if category_result:
            return category_result

        # 4단계: 기본값 (최소 장소가 있는 일차)
        if day_places:
            min_places_day = min(day_places.keys(),
                                key=lambda x: len(day_places[x]))
            return MatchResult(
                day_number=min_places_day,
                confidence=0.1,
                match_type="default"
            )

        # 최종 폴백
        return MatchResult(day_number=1, confidence=0.0, match_type="none")

    def _calculate_similarity_confidence(self, place1: str, place2: str) -> float:
        """유사도 신뢰도 계산"""
        if not place1 or not place2:
            return 0.0

        # 길이 확인
        min_len = min(len(place1), len(place2))
        if min_len < 2:
            return 0.0

        # 포함 관계 확인
        if place1 in place2:
            return len(place1) / len(place2)
        elif place2 in place1:
            return len(place2) / len(place1)

        # Jaccard 유사도 계산 (단어 기반)
        words1 = set(place1.split())
        words2 = set(place2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def _match_by_category(self, place_name: str, index_data: Dict) -> Optional[MatchResult]:
        """카테고리 기반 매칭"""
        # 장소명에서 카테고리 추론
        inferred_category = None
        place_lower = place_name.lower()

        if any(keyword in place_lower for keyword in ["식당", "맛집", "카페", "레스토랑"]):
            inferred_category = "식당"
        elif any(keyword in place_lower for keyword in ["박물관", "미술관", "관광", "명소"]):
            inferred_category = "관광지"

        if not inferred_category:
            return None

        category_mapping = index_data.get('category_mapping', {})
        if inferred_category in category_mapping:
            possible_days = list(category_mapping[inferred_category])
            if possible_days:
                # 가장 적게 사용된 일차 선택
                day_places = index_data['day_places']
                best_day = min(possible_days,
                             key=lambda x: len(day_places.get(x, [])))
                return MatchResult(
                    day_number=best_day,
                    confidence=0.3,
                    match_type="category"
                )

        return None

    def batch_match_places(self, places: List[Dict], itinerary: List[Dict]) -> Dict[str, MatchResult]:
        """배치 장소 매칭 (성능 최적화)"""
        print(f"🔄 배치 매칭 시작: {len(places)}개 장소")

        # 일정 인덱스 미리 구축
        itinerary_hash = self.build_itinerary_index(itinerary)

        results = {}
        for place in places:
            place_name = place.get('name', '')
            if place_name:
                result = self.find_day_for_place(place_name, itinerary)
                results[place_name] = result

        print(f"✅ 배치 매칭 완료: {len(results)}개 결과")
        return results

    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        cache_hit_rate = (self.metrics["cache_hits"] /
                         max(self.metrics["cache_hits"] + self.metrics["cache_misses"], 1))

        return {
            "cache_size": len(self.cache),
            "cache_hit_rate": cache_hit_rate,
            "total_matches": self.metrics["match_attempts"],
            "index_builds": self.metrics["index_builds"],
            "metrics": self.metrics.copy()
        }

    def clear_cache(self):
        """캐시 초기화"""
        self.cache.clear()
        self.itinerary_index.clear()
        self.normalized_places_index.clear()
        self.category_index.clear()
        print("🧹 장소 매칭 캐시 초기화 완료")

    def warm_up_cache(self, common_places: List[str], sample_itineraries: List[List[Dict]]):
        """캐시 예열 (자주 사용되는 장소들)"""
        print(f"🔥 캐시 예열 시작: {len(common_places)}개 장소, {len(sample_itineraries)}개 일정")

        for itinerary in sample_itineraries:
            for place_name in common_places:
                self.find_day_for_place(place_name, itinerary)

        print(f"✅ 캐시 예열 완료: {len(self.cache)}개 항목")


# 전역 인스턴스
_global_place_matcher: Optional[OptimizedPlaceMatcher] = None


def get_place_matcher() -> OptimizedPlaceMatcher:
    """전역 장소 매칭기 조회"""
    global _global_place_matcher
    if _global_place_matcher is None:
        _global_place_matcher = OptimizedPlaceMatcher()
    return _global_place_matcher


def reset_place_matcher():
    """전역 장소 매칭기 리셋"""
    global _global_place_matcher
    _global_place_matcher = None


# 편의 함수들
def match_place_to_day(place_name: str, itinerary: List[Dict]) -> int:
    """장소를 일차에 매칭 (간단한 인터페이스)"""
    matcher = get_place_matcher()
    result = matcher.find_day_for_place(place_name, itinerary)
    return result.day_number


def match_places_batch(places: List[Dict], itinerary: List[Dict]) -> Dict[str, int]:
    """장소들을 일차에 배치 매칭"""
    matcher = get_place_matcher()
    results = matcher.batch_match_places(places, itinerary)
    return {name: result.day_number for name, result in results.items()}