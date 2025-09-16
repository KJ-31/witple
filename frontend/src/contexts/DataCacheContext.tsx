'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface CacheItem<T = any> {
  data: T
  timestamp: number
  version: string // 앱 버전으로 캐시 무효화
}

interface CacheStore {
  [key: string]: CacheItem
}

interface DataCacheContextType {
  getCachedData: <T>(key: string) => T | null
  setCachedData: <T>(key: string, data: T, ttl?: number) => void
  clearCache: (key?: string) => void
  isCacheValid: (key: string, ttl?: number) => boolean
}

const DataCacheContext = createContext<DataCacheContextType | undefined>(undefined)

const APP_VERSION = '1.0.0' // 앱 업데이트 시 이 값을 변경하면 캐시가 초기화됩니다
const DEFAULT_TTL = 30 * 60 * 1000 // 30분 기본 캐시 시간
const CACHE_KEY = 'witple-app-cache'

export function DataCacheProvider({ children }: { children: ReactNode }) {
  const [cache, setCache] = useState<CacheStore>({})
  const [isInitialized, setIsInitialized] = useState(false)

  // 앱 시작 시 캐시 로드
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const storedCache = sessionStorage.getItem(CACHE_KEY)
        if (storedCache) {
          const parsedCache = JSON.parse(storedCache)

          // 버전이 다르면 캐시 무효화
          const validCache: CacheStore = {}
          Object.entries(parsedCache).forEach(([key, item]) => {
            const cacheItem = item as CacheItem
            if (cacheItem.version === APP_VERSION) {
              validCache[key] = cacheItem
            }
          })

          setCache(validCache)
        }
      } catch (error) {
        console.warn('캐시 로드 실패:', error)
      } finally {
        setIsInitialized(true)
      }
    }
  }, [])

  // 캐시 변경 시 sessionStorage에 저장
  useEffect(() => {
    if (isInitialized && typeof window !== 'undefined') {
      try {
        sessionStorage.setItem(CACHE_KEY, JSON.stringify(cache))
      } catch (error) {
        console.warn('캐시 저장 실패:', error)
      }
    }
  }, [cache, isInitialized])

  const getCachedData = <T,>(key: string): T | null => {
    const item = cache[key]
    if (!item) return null

    // 버전 체크
    if (item.version !== APP_VERSION) {
      return null
    }

    return item.data as T
  }

  const setCachedData = <T,>(key: string, data: T, ttl: number = DEFAULT_TTL) => {
    const cacheItem: CacheItem<T> = {
      data,
      timestamp: Date.now(),
      version: APP_VERSION
    }

    setCache(prev => ({
      ...prev,
      [key]: cacheItem
    }))
  }

  const isCacheValid = (key: string, ttl: number = DEFAULT_TTL): boolean => {
    const item = cache[key]
    if (!item) return false

    // 버전 체크
    if (item.version !== APP_VERSION) return false

    // TTL 체크
    const now = Date.now()
    return (now - item.timestamp) < ttl
  }

  const clearCache = (key?: string) => {
    if (key) {
      setCache(prev => {
        const newCache = { ...prev }
        delete newCache[key]
        return newCache
      })
    } else {
      setCache({})
      if (typeof window !== 'undefined') {
        sessionStorage.removeItem(CACHE_KEY)
      }
    }
  }

  const value: DataCacheContextType = {
    getCachedData,
    setCachedData,
    clearCache,
    isCacheValid
  }

  return (
    <DataCacheContext.Provider value={value}>
      {children}
    </DataCacheContext.Provider>
  )
}

export function useDataCache() {
  const context = useContext(DataCacheContext)
  if (context === undefined) {
    throw new Error('useDataCache must be used within a DataCacheProvider')
  }
  return context
}

// 편의 함수들
export const useCachedData = <T,>(
  key: string,
  fetcher: () => Promise<T>,
  ttl?: number
) => {
  const { getCachedData, setCachedData, isCacheValid } = useDataCache()
  const [data, setData] = useState<T | null>(getCachedData<T>(key))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchData = async (force = false) => {
    // 강제 갱신이 아니고 유효한 캐시가 있으면 사용
    if (!force && isCacheValid(key, ttl)) {
      const cachedData = getCachedData<T>(key)
      if (cachedData) {
        setData(cachedData)
        return cachedData
      }
    }

    setLoading(true)
    setError(null)

    try {
      const result = await fetcher()
      setCachedData(key, result, ttl)
      setData(result)
      return result
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error')
      setError(error)
      throw error
    } finally {
      setLoading(false)
    }
  }

  return {
    data,
    loading,
    error,
    fetchData,
    isValid: isCacheValid(key, ttl)
  }
}