import redis
import json
import logging
from typing import Optional, Any
from config import settings

logger = logging.getLogger(__name__)

# Redis 클라이언트 초기화 (연결 실패 시 None으로 설정)
redis_client = None
try:
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    redis_client.ping()  # 연결 테스트
    logger.info("Cache Redis 연결 성공")
except Exception as e:
    logger.warning(f"Cache Redis 연결 실패: {e}")
    redis_client = None

def cache_get(key: str) -> Optional[Any]:
    """캐시에서 데이터 조회"""
    if not redis_client:
        logger.debug(f"Redis not available, skipping cache get for key: {key}")
        return None
    
    try:
        cached_data = redis_client.get(key)
        if cached_data:
            logger.info(f"Cache hit for key: {key}")
            return json.loads(cached_data)
        else:
            logger.info(f"Cache miss for key: {key}")
            return None
    except Exception as e:
        logger.error(f"Cache get error for key {key}: {e}")
        return None

def cache_set(key: str, data: Any, expire_seconds: int = 3600) -> bool:
    """캐시에 데이터 저장"""
    if not redis_client:
        logger.debug(f"Redis not available, skipping cache set for key: {key}")
        return False
    
    try:
        json_data = json.dumps(data, ensure_ascii=False)
        redis_client.setex(key, expire_seconds, json_data)
        logger.info(f"Cache set for key: {key}, expire: {expire_seconds}s")
        return True
    except Exception as e:
        logger.error(f"Cache set error for key {key}: {e}")
        return False

def cache_delete(key: str) -> bool:
    """캐시에서 데이터 삭제"""
    if not redis_client:
        logger.debug(f"Redis not available, skipping cache delete for key: {key}")
        return False
    
    try:
        redis_client.delete(key)
        logger.info(f"Cache deleted for key: {key}")
        return True
    except Exception as e:
        logger.error(f"Cache delete error for key {key}: {e}")
        return False

def cache_exists(key: str) -> bool:
    """캐시 키 존재 여부 확인"""
    if not redis_client:
        logger.debug(f"Redis not available, skipping cache exists check for key: {key}")
        return False
    
    try:
        return redis_client.exists(key) > 0
    except Exception as e:
        logger.error(f"Cache exists error for key {key}: {e}")
        return False

def is_redis_available() -> bool:
    """Redis 연결 상태 확인"""
    return redis_client is not None

def get_redis_status() -> dict:
    """Redis 상태 정보 반환"""
    if not redis_client:
        return {
            "available": False,
            "status": "disconnected",
            "message": "Redis client not initialized"
        }
    
    try:
        redis_client.ping()
        return {
            "available": True,
            "status": "connected",
            "message": "Redis connection successful"
        }
    except Exception as e:
        return {
            "available": False,
            "status": "error",
            "message": f"Redis connection failed: {str(e)}"
        }

def cache_invalidate_pattern(pattern: str) -> int:
    """패턴에 맞는 캐시 키들을 삭제"""
    if not redis_client:
        logger.debug(f"Redis not available, skipping cache invalidation for pattern: {pattern}")
        return 0
    
    try:
        # 패턴에 맞는 키들을 찾아서 삭제
        keys = redis_client.keys(pattern)
        if keys:
            deleted_count = redis_client.delete(*keys)
            logger.info(f"Cache invalidated: {deleted_count} keys matching pattern '{pattern}'")
            return deleted_count
        else:
            logger.info(f"No cache keys found matching pattern '{pattern}'")
            return 0
    except Exception as e:
        logger.error(f"Cache invalidation error for pattern '{pattern}': {e}")
        return 0

def cache_invalidate_user_recommendations(user_id: str) -> int:
    """특정 사용자의 추천 관련 캐시 삭제"""
    patterns = [
        f"mixed_recommendations:{user_id}:*",
        f"filtered:{user_id}:*",
        f"personalized_recommendations:{user_id}:*"
    ]
    
    total_deleted = 0
    for pattern in patterns:
        total_deleted += cache_invalidate_pattern(pattern)
    
    logger.info(f"User recommendations cache invalidated for user {user_id}: {total_deleted} keys")
    return total_deleted

def cache_invalidate_attractions() -> int:
    """관광지 관련 캐시 삭제"""
    patterns = [
        "attractions:regions",
        "attractions:categories",
        "search:*",
        "filtered:*"
    ]
    
    total_deleted = 0
    for pattern in patterns:
        total_deleted += cache_invalidate_pattern(pattern)
    
    logger.info(f"Attractions cache invalidated: {total_deleted} keys")
    return total_deleted
