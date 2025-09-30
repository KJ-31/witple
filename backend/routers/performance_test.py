"""
Redis 성능 비교 테스트 API
- 캐시 사용/미사용 시나리오 비교
- 실제 API 엔드포인트 성능 측정
- Redis 캐시 효과 분석
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any, Optional
import asyncio
import time
import json
import random
from datetime import datetime
import logging

from cache_utils import cache
from routers.recommendations2 import fetch_recommendations_with_fallback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["performance"])

@router.get("/test/redis-cache")
async def test_redis_cache_performance(
    iterations: int = Query(10, ge=1, le=100, description="테스트 반복 횟수"),
    clear_cache: bool = Query(False, description="캐시 클리어 여부")
):
    """Redis 캐시 성능 테스트"""
    try:
        results = []
        
        for i in range(iterations):
            # 캐시 클리어 (필요한 경우)
            if clear_cache and i > 0:
                await clear_all_caches()
            
            # 테스트 데이터 생성
            test_key = f"perf_test:{i}:{int(time.time())}"
            test_data = {
                "id": i,
                "timestamp": datetime.now().isoformat(),
                "data": [f"item_{j}" for j in range(100)],
                "metadata": {"test": True, "iteration": i}
            }
            
            # 캐시 저장 시간 측정
            start_time = time.time()
            cache.set(test_key, test_data, expire=300)
            set_time = (time.time() - start_time) * 1000
            
            # 캐시 조회 시간 측정
            start_time = time.time()
            retrieved_data = cache.get(test_key)
            get_time = (time.time() - start_time) * 1000
            
            results.append({
                "iteration": i,
                "set_time_ms": set_time,
                "get_time_ms": get_time,
                "data_size_bytes": len(json.dumps(test_data)),
                "cache_hit": retrieved_data is not None
            })
        
        # 통계 계산
        set_times = [r["set_time_ms"] for r in results]
        get_times = [r["get_time_ms"] for r in results]
        
        return {
            "test_type": "redis_cache_performance",
            "iterations": iterations,
            "clear_cache": clear_cache,
            "results": results,
            "statistics": {
                "avg_set_time_ms": sum(set_times) / len(set_times),
                "avg_get_time_ms": sum(get_times) / len(get_times),
                "min_set_time_ms": min(set_times),
                "max_set_time_ms": max(set_times),
                "min_get_time_ms": min(get_times),
                "max_get_time_ms": max(get_times),
                "cache_hit_rate": sum(1 for r in results if r["cache_hit"]) / len(results)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Redis 캐시 성능 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"테스트 실패: {str(e)}")

@router.get("/test/api-endpoints")
async def test_api_endpoints_performance(
    iterations: int = Query(5, ge=1, le=20, description="테스트 반복 횟수"),
    clear_cache: bool = Query(False, description="캐시 클리어 여부")
):
    """실제 API 엔드포인트 성능 테스트"""
    try:
        # 테스트할 엔드포인트들
        test_endpoints = [
            {
                "name": "recommendations_main",
                "function": lambda: fetch_recommendations_with_fallback(
                    user_id="test_user",
                    region="seoul",
                    category="attraction",
                    limit=10,
                    fast_mode=True
                )
            },
            {
                "name": "recommendations_explore",
                "function": lambda: fetch_recommendations_with_fallback(
                    user_id="test_user",
                    region="seoul",
                    category="attraction",
                    limit=10,
                    fast_mode=False
                )
            }
        ]
        
        results = {}
        
        for endpoint in test_endpoints:
            endpoint_results = []
            
            for i in range(iterations):
                # 캐시 클리어 (필요한 경우)
                if clear_cache and i > 0:
                    await clear_all_caches()
                
                # API 호출 시간 측정
                start_time = time.time()
                try:
                    result = await endpoint["function"]()
                    end_time = time.time()
                    
                    response_time = (end_time - start_time) * 1000
                    success = True
                    data_size = len(json.dumps(result)) if result else 0
                    
                except Exception as e:
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    success = False
                    data_size = 0
                    logger.error(f"API 호출 실패: {e}")
                
                endpoint_results.append({
                    "iteration": i,
                    "response_time_ms": response_time,
                    "success": success,
                    "data_size_bytes": data_size
                })
            
            # 통계 계산
            response_times = [r["response_time_ms"] for r in endpoint_results if r["success"]]
            success_rate = sum(1 for r in endpoint_results if r["success"]) / len(endpoint_results)
            
            results[endpoint["name"]] = {
                "results": endpoint_results,
                "statistics": {
                    "avg_response_time_ms": sum(response_times) / len(response_times) if response_times else 0,
                    "min_response_time_ms": min(response_times) if response_times else 0,
                    "max_response_time_ms": max(response_times) if response_times else 0,
                    "success_rate": success_rate,
                    "total_requests": len(endpoint_results)
                }
            }
        
        return {
            "test_type": "api_endpoints_performance",
            "iterations": iterations,
            "clear_cache": clear_cache,
            "endpoints": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"API 엔드포인트 성능 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"테스트 실패: {str(e)}")

@router.get("/compare/cache-vs-no-cache")
async def compare_cache_vs_no_cache(
    iterations: int = Query(5, ge=1, le=20, description="테스트 반복 횟수")
):
    """캐시 사용 vs 미사용 성능 비교"""
    try:
        # 캐시 사용 테스트
        cache_enabled_results = await test_api_endpoints_performance(
            iterations=iterations, 
            clear_cache=False
        )
        
        # 캐시 미사용 테스트
        cache_disabled_results = await test_api_endpoints_performance(
            iterations=iterations, 
            clear_cache=True
        )
        
        # 비교 분석
        comparison = {}
        
        for endpoint_name in cache_enabled_results["endpoints"]:
            enabled_stats = cache_enabled_results["endpoints"][endpoint_name]["statistics"]
            disabled_stats = cache_disabled_results["endpoints"][endpoint_name]["statistics"]
            
            avg_enabled = enabled_stats["avg_response_time_ms"]
            avg_disabled = disabled_stats["avg_response_time_ms"]
            
            improvement_percent = 0
            if avg_disabled > 0:
                improvement_percent = ((avg_disabled - avg_enabled) / avg_disabled) * 100
            
            comparison[endpoint_name] = {
                "cache_enabled": {
                    "avg_response_time_ms": avg_enabled,
                    "success_rate": enabled_stats["success_rate"]
                },
                "cache_disabled": {
                    "avg_response_time_ms": avg_disabled,
                    "success_rate": disabled_stats["success_rate"]
                },
                "improvement": {
                    "response_time_improvement_percent": improvement_percent,
                    "time_saved_ms": avg_disabled - avg_enabled
                }
            }
        
        return {
            "test_type": "cache_vs_no_cache_comparison",
            "iterations": iterations,
            "comparison": comparison,
            "summary": {
                "overall_improvement_percent": sum(
                    comp["improvement"]["response_time_improvement_percent"] 
                    for comp in comparison.values()
                ) / len(comparison) if comparison else 0,
                "total_endpoints_tested": len(comparison)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"캐시 비교 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"테스트 실패: {str(e)}")

@router.get("/cache/status")
async def get_cache_status():
    """Redis 캐시 상태 조회"""
    try:
        import redis
        from config import settings
        
        redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # Redis 정보 수집
        redis_info = redis_client.info()
        
        # 캐시 키 통계
        all_keys = redis_client.keys("*")
        rec_keys = redis_client.keys("rec_*")
        main_keys = redis_client.keys("main_*")
        explore_keys = redis_client.keys("explore_*")
        profile_keys = redis_client.keys("profile_*")
        trips_keys = redis_client.keys("trips_*")
        
        return {
            "redis_connection": redis_client.ping(),
            "total_keys": len(all_keys),
            "key_breakdown": {
                "recommendations": len(rec_keys),
                "main_page": len(main_keys),
                "explore_section": len(explore_keys),
                "user_profiles": len(profile_keys),
                "trips": len(trips_keys)
            },
            "redis_info": {
                "used_memory_mb": redis_info.get("used_memory", 0) / 1024 / 1024,
                "connected_clients": redis_info.get("connected_clients", 0),
                "total_commands_processed": redis_info.get("total_commands_processed", 0),
                "keyspace_hits": redis_info.get("keyspace_hits", 0),
                "keyspace_misses": redis_info.get("keyspace_misses", 0)
            },
            "cache_hit_ratio": calculate_redis_hit_ratio(redis_info),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"캐시 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"상태 조회 실패: {str(e)}")

@router.post("/cache/clear")
async def clear_cache():
    """Redis 캐시 전체 클리어"""
    try:
        await clear_all_caches()
        return {
            "status": "success",
            "message": "캐시가 성공적으로 클리어되었습니다.",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"캐시 클리어 실패: {e}")
        raise HTTPException(status_code=500, detail=f"캐시 클리어 실패: {str(e)}")

@router.get("/benchmark/simple")
async def simple_benchmark():
    """간단한 성능 벤치마크"""
    try:
        # 1. Redis 기본 작업 벤치마크
        redis_results = await test_redis_cache_performance(iterations=10, clear_cache=False)
        
        # 2. API 엔드포인트 벤치마크
        api_results = await test_api_endpoints_performance(iterations=3, clear_cache=False)
        
        # 3. 캐시 상태
        cache_status = await get_cache_status()
        
        return {
            "benchmark_type": "simple_performance_test",
            "redis_performance": redis_results,
            "api_performance": api_results,
            "cache_status": cache_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"간단한 벤치마크 실패: {e}")
        raise HTTPException(status_code=500, detail=f"벤치마크 실패: {str(e)}")

async def clear_all_caches():
    """모든 캐시 클리어"""
    try:
        import redis
        from config import settings
        
        redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # 모든 추천 관련 캐시 클리어
        keys_to_clear = [
            "rec_*", "main_*", "explore_*", "profile_*", "trips_*", "perf_test_*"
        ]
        
        for pattern in keys_to_clear:
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} keys matching pattern: {pattern}")
        
    except Exception as e:
        logger.error(f"캐시 클리어 중 오류: {e}")
        raise

def calculate_redis_hit_ratio(redis_info: Dict) -> float:
    """Redis 캐시 히트율 계산"""
    hits = redis_info.get("keyspace_hits", 0)
    misses = redis_info.get("keyspace_misses", 0)
    total = hits + misses
    return hits / total if total > 0 else 0.0
