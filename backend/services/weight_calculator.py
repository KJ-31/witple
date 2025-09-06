"""
사용자 선호도 태그 가중치 계산 시스템
- 태그 빈도, 카테고리, 사용자 행동 패턴을 기반으로 지능적 가중치 계산
"""
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class TagWeightCalculator:
    def __init__(self):
        # 태그 카테고리별 기본 가중치
        self.category_base_weights = {
            # 핵심 여행 스타일 (높은 가중치)
            'travel_style': 3.0,  # 럭셔리, 백패킹, 가족여행, 커플여행
            'activity_preference': 2.5,  # 액티비티, 휴식, 문화체험, 자연탐방
            
            # 장소 카테고리 (중간 가중치)
            'place_category': 2.0,  # 숙박, 음식, 쇼핑, 관광지
            'region_preference': 1.8,  # 지역 선호도
            
            # 세부 선호도 (낮은 가중치)
            'detailed_preference': 1.2,  # 구체적인 세부사항
            'seasonal': 1.0,  # 계절적 선호도
            'budget': 0.8,  # 예산 관련
        }
        
        # 태그별 카테고리 매핑
        self.tag_categories = {
            # 여행 스타일
            'luxury': 'travel_style',
            'budget': 'travel_style', 
            'backpacking': 'travel_style',
            'family': 'travel_style',
            'couple': 'travel_style',
            'solo': 'travel_style',
            'group': 'travel_style',
            
            # 활동 선호도
            'activity': 'activity_preference',
            'adventure': 'activity_preference',
            'relaxation': 'activity_preference',
            'culture': 'activity_preference',
            'nature': 'activity_preference',
            'nightlife': 'activity_preference',
            'photography': 'activity_preference',
            
            # 장소 카테고리
            'accommodation': 'place_category',
            'restaurants': 'place_category',
            'shopping': 'place_category',
            'attractions': 'place_category',
            'entertainment': 'place_category',
            
            # 지역 선호도
            'urban': 'region_preference',
            'rural': 'region_preference',
            'coastal': 'region_preference',
            'mountain': 'region_preference',
            'island': 'region_preference',
            
            # 세부 선호도
            'pet_friendly': 'detailed_preference',
            'accessibility': 'detailed_preference',
            'wifi': 'detailed_preference',
            'parking': 'detailed_preference',
            
            # 계절
            'spring': 'seasonal',
            'summer': 'seasonal', 
            'autumn': 'seasonal',
            'winter': 'seasonal',
            
            # 예산
            'expensive': 'budget',
            'cheap': 'budget',
            'mid_range': 'budget'
        }
    
    def calculate_tag_weight(self, tag: str, user_tag_frequency: int = 1, total_user_tags: int = 1) -> float:
        """
        개별 태그의 가중치를 계산
        
        Args:
            tag: 태그명
            user_tag_frequency: 사용자가 이 태그를 선택한 빈도
            total_user_tags: 사용자의 총 태그 수
        
        Returns:
            계산된 가중치 (0.3 ~ 5.0)
        """
        try:
            # 1. 카테고리 기반 기본 가중치
            category = self.tag_categories.get(tag.lower(), 'detailed_preference')
            base_weight = self.category_base_weights[category]
            
            # 2. 빈도 기반 가중치 조정 (자주 선택된 태그일수록 높은 가중치)
            frequency_multiplier = min(2.0, 1.0 + (user_tag_frequency - 1) * 0.3)
            
            # 3. 사용자 태그 분산도 고려 (태그가 너무 많으면 가중치 감소)
            if total_user_tags > 10:
                diversity_penalty = max(0.7, 1.0 - (total_user_tags - 10) * 0.02)
            else:
                diversity_penalty = 1.0
            
            # 4. 최종 가중치 계산
            final_weight = base_weight * frequency_multiplier * diversity_penalty
            
            # 5. 가중치 범위 제한 (0.3 ~ 5.0)
            final_weight = max(0.3, min(5.0, final_weight))
            
            logger.info(f"Tag: {tag} -> Category: {category}, Base: {base_weight}, "
                       f"Freq: {frequency_multiplier}, Diversity: {diversity_penalty}, "
                       f"Final: {final_weight:.2f}")
            
            return round(final_weight, 2)
            
        except Exception as e:
            logger.error(f"Error calculating weight for tag {tag}: {str(e)}")
            return 1.0  # 기본값
    
    def calculate_all_user_weights(self, user_tags: List[Dict]) -> List[Dict]:
        """
        사용자의 모든 태그에 대해 가중치를 계산
        
        Args:
            user_tags: [{'tag': 'luxury', 'frequency': 2}, ...] 형태의 리스트
        
        Returns:
            가중치가 추가된 태그 리스트
        """
        try:
            total_tags = len(user_tags)
            
            # 각 태그별 빈도 계산
            tag_frequencies = {}
            for tag_info in user_tags:
                tag = tag_info['tag']
                frequency = tag_info.get('frequency', 1)
                tag_frequencies[tag] = frequency
            
            # 가중치 계산
            weighted_tags = []
            for tag_info in user_tags:
                tag = tag_info['tag']
                frequency = tag_frequencies[tag]
                
                calculated_weight = self.calculate_tag_weight(
                    tag=tag,
                    user_tag_frequency=frequency,
                    total_user_tags=total_tags
                )
                
                weighted_tags.append({
                    'tag': tag,
                    'original_weight': tag_info.get('weight', 1),
                    'calculated_weight': calculated_weight,
                    'frequency': frequency,
                    'category': self.tag_categories.get(tag.lower(), 'detailed_preference')
                })
            
            # 가중치 순으로 정렬
            weighted_tags.sort(key=lambda x: x['calculated_weight'], reverse=True)
            
            return weighted_tags
            
        except Exception as e:
            logger.error(f"Error calculating user weights: {str(e)}")
            return []
    
    def get_weight_distribution_summary(self, weighted_tags: List[Dict]) -> Dict:
        """가중치 분포 요약 정보"""
        if not weighted_tags:
            return {}
        
        weights = [tag['calculated_weight'] for tag in weighted_tags]
        categories = {}
        
        for tag in weighted_tags:
            category = tag['category']
            if category not in categories:
                categories[category] = {'count': 0, 'avg_weight': 0, 'total_weight': 0}
            categories[category]['count'] += 1
            categories[category]['total_weight'] += tag['calculated_weight']
        
        for category in categories:
            categories[category]['avg_weight'] = round(
                categories[category]['total_weight'] / categories[category]['count'], 2
            )
        
        return {
            'total_tags': len(weighted_tags),
            'weight_range': {
                'min': round(min(weights), 2),
                'max': round(max(weights), 2),
                'avg': round(sum(weights) / len(weights), 2)
            },
            'category_distribution': categories,
            'high_priority_tags': [tag['tag'] for tag in weighted_tags if tag['calculated_weight'] >= 2.5],
            'low_priority_tags': [tag['tag'] for tag in weighted_tags if tag['calculated_weight'] <= 1.0]
        }

# 싱글톤 인스턴스
tag_weight_calculator = TagWeightCalculator()