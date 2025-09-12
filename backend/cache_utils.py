import redis
import json
import pickle
from typing import Any, Optional, Union
from functools import wraps
import logging
from config import settings
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

# Redis 클라이언트 초기화
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

class RedisCache:
    """Redis 캐싱 유틸리티 클래스"""
    
    def __init__(self, redis_client: redis.Redis = redis_client):
        self.redis = redis_client
    
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """
        캐시에 데이터 저장
        
        Args:
            key: 캐시 키
            value: 저장할 값 (dict, list, str 등)
            expire: 만료 시간 (초 단위, None이면 만료 없음)
        
        Returns:
            bool: 저장 성공 여부
        """
        try:
            if isinstance(value, (dict, list)):
                # JSON 직렬화를 위한 커스텀 인코더
                serialized_value = json.dumps(value, ensure_ascii=False, default=self._json_serializer)
            else:
                serialized_value = str(value)
            
            return self.redis.set(key, serialized_value, ex=expire)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    def _json_serializer(self, obj):
        """JSON 직렬화를 위한 커스텀 인코더"""
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 데이터 조회
        
        Args:
            key: 캐시 키
        
        Returns:
            저장된 값 또는 None
        """
        try:
            value = self.redis.get(key)
            if value is None:
                return None
            
            # JSON으로 파싱 시도
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # JSON이 아니면 문자열로 반환
                return value
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """캐시에서 데이터 삭제"""
        try:
            return bool(self.redis.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """캐시 키 존재 여부 확인"""
        try:
            return bool(self.redis.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    def set_hash(self, name: str, mapping: dict, expire: Optional[int] = None) -> bool:
        """해시 형태로 데이터 저장"""
        try:
            result = self.redis.hset(name, mapping=mapping)
            if expire:
                self.redis.expire(name, expire)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis hset error: {e}")
            return False
    
    def get_hash(self, name: str) -> Optional[dict]:
        """해시 형태로 데이터 조회"""
        try:
            return self.redis.hgetall(name) or None
        except Exception as e:
            logger.error(f"Redis hgetall error: {e}")
            return None
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """숫자 값 증가"""
        try:
            return self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis increment error: {e}")
            return None
    
    def expire(self, key: str, seconds: int) -> bool:
        """키에 만료 시간 설정"""
        try:
            return bool(self.redis.expire(key, seconds))
        except Exception as e:
            logger.error(f"Redis expire error: {e}")
            return False


# 전역 캐시 인스턴스
cache = RedisCache()


def cached(expire: int = 300, key_prefix: str = ""):
    """
    함수 결과를 캐싱하는 데코레이터
    
    Args:
        expire: 캐시 만료 시간 (초)
        key_prefix: 캐시 키 접두사
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # 캐시에서 조회
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for {cache_key}")
                return cached_result
            
            # 캐시에 없으면 함수 실행
            logger.info(f"Cache miss for {cache_key}")
            result = await func(*args, **kwargs)
            
            # 결과를 캐시에 저장
            cache.set(cache_key, result, expire=expire)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # 캐시에서 조회
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for {cache_key}")
                return cached_result
            
            # 캐시에 없으면 함수 실행
            logger.info(f"Cache miss for {cache_key}")
            result = func(*args, **kwargs)
            
            # 결과를 캐시에 저장
            cache.set(cache_key, result, expire=expire)
            return result
        
        # 비동기 함수인지 확인
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 사용 예제 함수들
def cache_user_data(user_id: int, user_data: dict, expire: int = 3600):
    """사용자 데이터 캐싱"""
    key = f"user:{user_id}"
    return cache.set(key, user_data, expire=expire)


def get_cached_user_data(user_id: int) -> Optional[dict]:
    """캐시된 사용자 데이터 조회"""
    key = f"user:{user_id}"
    return cache.get(key)


def cache_recommendations(user_id: int, recommendations: list, expire: int = 1800):
    """추천 데이터 캐싱 (30분)"""
    key = f"recommendations:{user_id}"
    return cache.set(key, recommendations, expire=expire)


def get_cached_recommendations(user_id: int) -> Optional[list]:
    """캐시된 추천 데이터 조회"""
    key = f"recommendations:{user_id}"
    return cache.get(key)


def cache_attraction_data(attraction_id: int, attraction_data: dict, expire: int = 7200):
    """관광지 데이터 캐싱 (2시간)"""
    key = f"attraction:{attraction_id}"
    return cache.set(key, attraction_data, expire=expire)


def get_cached_attraction_data(attraction_id: int) -> Optional[dict]:
    """캐시된 관광지 데이터 조회"""
    key = f"attraction:{attraction_id}"
    return cache.get(key)


def increment_view_count(attraction_id: int) -> Optional[int]:
    """관광지 조회수 증가"""
    key = f"views:attraction:{attraction_id}"
    return cache.increment(key)


def get_view_count(attraction_id: int) -> int:
    """관광지 조회수 조회"""
    key = f"views:attraction:{attraction_id}"
    count = cache.get(key)
    return int(count) if count else 0
