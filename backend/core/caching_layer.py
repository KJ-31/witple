"""
통합 캐싱 레이어 시스템
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time
import json
import hashlib
import asyncio
from contextlib import asynccontextmanager
from functools import wraps

# 다양한 캐시 백엔드 지원
from cachetools import TTLCache, LRUCache, LFUCache
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import memcache
    MEMCACHED_AVAILABLE = True
except ImportError:
    MEMCACHED_AVAILABLE = False


class CacheBackendType(Enum):
    """캐시 백엔드 타입"""
    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"
    HYBRID = "hybrid"


class CacheStrategy(Enum):
    """캐시 전략"""
    TTL = "ttl"          # Time To Live
    LRU = "lru"          # Least Recently Used
    LFU = "lfu"          # Least Frequently Used
    WRITE_THROUGH = "write_through"
    WRITE_BACK = "write_back"
    WRITE_AROUND = "write_around"


@dataclass
class CacheConfig:
    """캐시 설정"""
    backend_type: CacheBackendType = CacheBackendType.MEMORY
    strategy: CacheStrategy = CacheStrategy.TTL
    ttl: int = 3600  # 1시간
    max_size: int = 1000
    redis_url: Optional[str] = None
    memcached_servers: List[str] = field(default_factory=list)
    compression_enabled: bool = False
    serialization_format: str = "json"  # json, pickle, msgpack


@dataclass
class CacheStats:
    """캐시 통계"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    hit_rate: float = 0.0
    memory_usage: int = 0  # bytes
    operations: Dict[str, int] = field(default_factory=lambda: {
        "get": 0, "set": 0, "delete": 0, "clear": 0
    })


class CacheBackend(ABC):
    """캐시 백엔드 추상 클래스"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.stats = CacheStats()

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """값 조회"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """값 저장"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """값 삭제"""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """전체 삭제"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """키 존재 여부"""
        pass

    @abstractmethod
    def get_stats(self) -> CacheStats:
        """통계 조회"""
        pass

    def _serialize(self, value: Any) -> str:
        """직렬화"""
        if self.config.serialization_format == "json":
            return json.dumps(value, default=str, ensure_ascii=False)
        # 다른 형식들 추가 가능
        return str(value)

    def _deserialize(self, data: str) -> Any:
        """역직렬화"""
        if self.config.serialization_format == "json":
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return data


class MemoryCacheBackend(CacheBackend):
    """메모리 캐시 백엔드"""

    def __init__(self, config: CacheConfig):
        super().__init__(config)

        # 전략별 캐시 구현
        if config.strategy == CacheStrategy.TTL:
            self.cache = TTLCache(maxsize=config.max_size, ttl=config.ttl)
        elif config.strategy == CacheStrategy.LRU:
            self.cache = LRUCache(maxsize=config.max_size)
        elif config.strategy == CacheStrategy.LFU:
            self.cache = LFUCache(maxsize=config.max_size)
        else:
            self.cache = TTLCache(maxsize=config.max_size, ttl=config.ttl)

    async def get(self, key: str) -> Optional[Any]:
        """값 조회"""
        self.stats.operations["get"] += 1
        try:
            if key in self.cache:
                self.stats.hits += 1
                return self.cache[key]
            else:
                self.stats.misses += 1
                return None
        except Exception:
            self.stats.misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """값 저장"""
        self.stats.operations["set"] += 1
        try:
            # TTL은 TTLCache에서만 지원
            if isinstance(self.cache, TTLCache) and ttl:
                # TTLCache는 개별 TTL 설정 불가, 전역 TTL 사용
                pass
            self.cache[key] = value
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """값 삭제"""
        self.stats.operations["delete"] += 1
        try:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
        except Exception:
            return False

    async def clear(self) -> bool:
        """전체 삭제"""
        self.stats.operations["clear"] += 1
        try:
            self.cache.clear()
            return True
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        """키 존재 여부"""
        return key in self.cache

    def get_stats(self) -> CacheStats:
        """통계 조회"""
        self.stats.size = len(self.cache)
        total_operations = self.stats.hits + self.stats.misses
        self.stats.hit_rate = self.stats.hits / max(total_operations, 1)
        return self.stats


class RedisCacheBackend(CacheBackend):
    """Redis 캐시 백엔드"""

    def __init__(self, config: CacheConfig):
        super().__init__(config)
        if not REDIS_AVAILABLE:
            raise ImportError("redis package is required for Redis backend")

        # Redis 연결 설정
        redis_url = config.redis_url or "redis://localhost:6379/0"
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = config.ttl

    async def get(self, key: str) -> Optional[Any]:
        """값 조회"""
        self.stats.operations["get"] += 1
        try:
            value = self.redis_client.get(key)
            if value is not None:
                self.stats.hits += 1
                return self._deserialize(value)
            else:
                self.stats.misses += 1
                return None
        except Exception:
            self.stats.misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """값 저장"""
        self.stats.operations["set"] += 1
        try:
            serialized_value = self._serialize(value)
            ttl_value = ttl or self.default_ttl
            result = self.redis_client.setex(key, ttl_value, serialized_value)
            return result
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """값 삭제"""
        self.stats.operations["delete"] += 1
        try:
            result = self.redis_client.delete(key)
            return result > 0
        except Exception:
            return False

    async def clear(self) -> bool:
        """전체 삭제"""
        self.stats.operations["clear"] += 1
        try:
            self.redis_client.flushdb()
            return True
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        """키 존재 여부"""
        try:
            return self.redis_client.exists(key) > 0
        except Exception:
            return False

    def get_stats(self) -> CacheStats:
        """통계 조회"""
        try:
            info = self.redis_client.info()
            self.stats.memory_usage = info.get("used_memory", 0)
            self.stats.size = self.redis_client.dbsize()
        except Exception:
            pass

        total_operations = self.stats.hits + self.stats.misses
        self.stats.hit_rate = self.stats.hits / max(total_operations, 1)
        return self.stats


class HybridCacheBackend(CacheBackend):
    """하이브리드 캐시 백엔드 (L1: 메모리, L2: Redis)"""

    def __init__(self, config: CacheConfig):
        super().__init__(config)

        # L1 캐시 (메모리)
        l1_config = CacheConfig(
            backend_type=CacheBackendType.MEMORY,
            strategy=config.strategy,
            max_size=min(config.max_size // 4, 200),  # L1은 작게
            ttl=300  # 5분
        )
        self.l1_cache = MemoryCacheBackend(l1_config)

        # L2 캐시 (Redis)
        if config.redis_url and REDIS_AVAILABLE:
            self.l2_cache = RedisCacheBackend(config)
        else:
            self.l2_cache = None

    async def get(self, key: str) -> Optional[Any]:
        """값 조회 (L1 -> L2 순서)"""
        self.stats.operations["get"] += 1

        # L1 캐시 조회
        value = await self.l1_cache.get(key)
        if value is not None:
            self.stats.hits += 1
            return value

        # L2 캐시 조회
        if self.l2_cache:
            value = await self.l2_cache.get(key)
            if value is not None:
                # L1 캐시에 복사 (write-back)
                await self.l1_cache.set(key, value)
                self.stats.hits += 1
                return value

        self.stats.misses += 1
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """값 저장 (L1, L2 모두)"""
        self.stats.operations["set"] += 1

        # L1 캐시 저장
        l1_result = await self.l1_cache.set(key, value, ttl)

        # L2 캐시 저장
        l2_result = True
        if self.l2_cache:
            l2_result = await self.l2_cache.set(key, value, ttl)

        return l1_result and l2_result

    async def delete(self, key: str) -> bool:
        """값 삭제 (L1, L2 모두)"""
        self.stats.operations["delete"] += 1

        l1_result = await self.l1_cache.delete(key)
        l2_result = True
        if self.l2_cache:
            l2_result = await self.l2_cache.delete(key)

        return l1_result or l2_result

    async def clear(self) -> bool:
        """전체 삭제"""
        self.stats.operations["clear"] += 1

        l1_result = await self.l1_cache.clear()
        l2_result = True
        if self.l2_cache:
            l2_result = await self.l2_cache.clear()

        return l1_result and l2_result

    async def exists(self, key: str) -> bool:
        """키 존재 여부"""
        if await self.l1_cache.exists(key):
            return True
        if self.l2_cache and await self.l2_cache.exists(key):
            return True
        return False

    def get_stats(self) -> CacheStats:
        """통계 조회"""
        l1_stats = self.l1_cache.get_stats()
        l2_stats = self.l2_cache.get_stats() if self.l2_cache else CacheStats()

        # 통합 통계
        self.stats.hits = l1_stats.hits + l2_stats.hits
        self.stats.misses = l1_stats.misses + l2_stats.misses
        self.stats.size = l1_stats.size + l2_stats.size

        total_operations = self.stats.hits + self.stats.misses
        self.stats.hit_rate = self.stats.hits / max(total_operations, 1)

        return self.stats


class CacheManager:
    """통합 캐시 매니저"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.backend = self._create_backend(config)
        self.key_prefix = "travel_cache"

    def _create_backend(self, config: CacheConfig) -> CacheBackend:
        """백엔드 생성"""
        if config.backend_type == CacheBackendType.MEMORY:
            return MemoryCacheBackend(config)
        elif config.backend_type == CacheBackendType.REDIS and REDIS_AVAILABLE:
            return RedisCacheBackend(config)
        elif config.backend_type == CacheBackendType.HYBRID:
            return HybridCacheBackend(config)
        else:
            # 폴백: 메모리 캐시
            print(f"⚠️ {config.backend_type} 백엔드 사용 불가, 메모리 캐시로 폴백")
            return MemoryCacheBackend(config)

    def _build_key(self, namespace: str, key: str) -> str:
        """캐시 키 구성"""
        return f"{self.key_prefix}:{namespace}:{key}"

    async def get(self, namespace: str, key: str) -> Optional[Any]:
        """값 조회"""
        cache_key = self._build_key(namespace, key)
        return await self.backend.get(cache_key)

    async def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """값 저장"""
        cache_key = self._build_key(namespace, key)
        return await self.backend.set(cache_key, value, ttl)

    async def delete(self, namespace: str, key: str) -> bool:
        """값 삭제"""
        cache_key = self._build_key(namespace, key)
        return await self.backend.delete(cache_key)

    async def clear_namespace(self, namespace: str) -> bool:
        """네임스페이스별 삭제"""
        # 간단 구현 - 전체 삭제
        return await self.backend.clear()

    async def exists(self, namespace: str, key: str) -> bool:
        """키 존재 여부"""
        cache_key = self._build_key(namespace, key)
        return await self.backend.exists(cache_key)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭"""
        stats = self.backend.get_stats()
        return {
            "backend_type": self.config.backend_type.value,
            "hit_rate": stats.hit_rate,
            "hits": stats.hits,
            "misses": stats.misses,
            "size": stats.size,
            "memory_usage": stats.memory_usage,
            "operations": stats.operations
        }

    # 편의 메서드들
    async def cache_result(self, namespace: str, key: str, func: Callable, ttl: Optional[int] = None, *args, **kwargs) -> Any:
        """결과 캐싱"""
        cached_value = await self.get(namespace, key)
        if cached_value is not None:
            return cached_value

        # 함수 실행
        if asyncio.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)

        # 결과 캐싱
        await self.set(namespace, key, result, ttl)
        return result


# 데코레이터들
def cached_method(namespace: str, key_func: Optional[Callable] = None, ttl: Optional[int] = None):
    """메서드 캐싱 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # 캐시 매니저가 있는지 확인
            if not hasattr(self, '_cache_manager'):
                return await func(self, *args, **kwargs)

            cache_manager = self._cache_manager

            # 캐시 키 생성
            if key_func:
                cache_key = key_func(self, *args, **kwargs)
            else:
                # 기본 키 생성: 함수명 + 인자 해시
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key = f"{func.__name__}:{hashlib.md5(args_str.encode()).hexdigest()[:8]}"

            return await cache_manager.cache_result(namespace, cache_key, func, ttl, self, *args, **kwargs)

        return wrapper
    return decorator


def cached_function(namespace: str, key_func: Optional[Callable] = None, ttl: Optional[int] = None):
    """함수 캐싱 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()

            # 캐시 키 생성
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key = f"{func.__name__}:{hashlib.md5(args_str.encode()).hexdigest()[:8]}"

            return await cache_manager.cache_result(namespace, cache_key, func, ttl, *args, **kwargs)

        return wrapper
    return decorator


# 전역 캐시 매니저
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """전역 캐시 매니저 조회"""
    global _global_cache_manager
    if _global_cache_manager is None:
        # 기본 설정으로 초기화
        config = CacheConfig(
            backend_type=CacheBackendType.HYBRID,
            strategy=CacheStrategy.TTL,
            ttl=3600,  # 1시간
            max_size=2000,
            redis_url="redis://localhost:6379/1"  # 캐시 전용 DB
        )
        _global_cache_manager = CacheManager(config)

    return _global_cache_manager


def set_cache_manager(manager: CacheManager):
    """전역 캐시 매니저 설정"""
    global _global_cache_manager
    _global_cache_manager = manager


# 특화된 캐시 네임스페이스
class CacheNamespaces:
    """캐시 네임스페이스 상수"""
    RAG_RESPONSES = "rag_responses"
    DATABASE_QUERIES = "db_queries"
    PLACE_MATCHING = "place_matching"
    TRAVEL_PLANS = "travel_plans"
    USER_SESSIONS = "user_sessions"
    LLM_RESPONSES = "llm_responses"
    ENTITY_EXTRACTION = "entity_extraction"
    SEARCH_RESULTS = "search_results"


# 편의 함수들
async def cache_rag_response(query: str, response: str, ttl: int = 1800):
    """RAG 응답 캐싱 (30분)"""
    cache_manager = get_cache_manager()
    key = hashlib.md5(query.encode()).hexdigest()
    await cache_manager.set(CacheNamespaces.RAG_RESPONSES, key, response, ttl)


async def get_cached_rag_response(query: str) -> Optional[str]:
    """캐시된 RAG 응답 조회"""
    cache_manager = get_cache_manager()
    key = hashlib.md5(query.encode()).hexdigest()
    return await cache_manager.get(CacheNamespaces.RAG_RESPONSES, key)


async def cache_travel_plan(plan_id: str, plan_data: Dict, ttl: int = 7200):
    """여행 계획 캐싱 (2시간)"""
    cache_manager = get_cache_manager()
    await cache_manager.set(CacheNamespaces.TRAVEL_PLANS, plan_id, plan_data, ttl)


async def get_cached_travel_plan(plan_id: str) -> Optional[Dict]:
    """캐시된 여행 계획 조회"""
    cache_manager = get_cache_manager()
    return await cache_manager.get(CacheNamespaces.TRAVEL_PLANS, plan_id)