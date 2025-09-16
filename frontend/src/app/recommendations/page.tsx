'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { BottomNavigation } from '../../components'
import { useDataCache } from '../../contexts/DataCacheContext'

interface RecommendationItem {
  id: string
  title: string
  author: string
  genre: string
  imageUrl: string
  isNew?: boolean
  isUpdated?: boolean
  episodeCount?: number
  views?: number
  tags?: string[]
}

export default function RecommendationsPage() {
  const router = useRouter()
  const { data: session } = useSession()
  const [loading, setLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState(() => {
    // 초기값을 sessionStorage에서 가져오기
    if (typeof window !== 'undefined') {
      const storedData = sessionStorage.getItem('recommendations-data')
      if (storedData) {
        try {
          const data = JSON.parse(storedData)
          return data.selectedCategory || '레저'
        } catch {
          return '레저'
        }
      }
    }
    return '레저'
  })

  const { getCachedData, setCachedData, isCacheValid } = useDataCache()
  const [leftColumnItems, setLeftColumnItems] = useState<RecommendationItem[]>([])
  const [rightColumnItems, setRightColumnItems] = useState<RecommendationItem[]>([])
  const [discoveryItems, setDiscoveryItems] = useState<RecommendationItem[]>([])
  const [newItems, setNewItems] = useState<RecommendationItem[]>([])
  const [popularItems, setPopularItems] = useState<RecommendationItem[]>([])
  const [hiddenItems, setHiddenItems] = useState<RecommendationItem[]>([])
  const [themeItems, setThemeItems] = useState<RecommendationItem[]>([])
  const [seasonalItems, setSeasonalItems] = useState<RecommendationItem[]>([])
  const [isNavigatedBack, setIsNavigatedBack] = useState(false)

  const categories = ['레저', '숙박', '쇼핑', '자연', '맛집', '인문']

  // 카테고리별 데이터 fetcher 함수
  const fetchCategoryData = async (category: string) => {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'accept': 'application/json',
    }

    if (session && (session as any).backendToken) {
      headers['Authorization'] = `Bearer ${(session as any).backendToken}`
    }

    const apiUrl = `${API_BASE_URL}/proxy/api/v2/recommendations/main-feed/personalized?limit=15`
    const response = await fetch(apiUrl, { headers })

    if (!response.ok) {
      throw new Error(`API 응답 실패: ${response.status}`)
    }

    const data = await response.json()

    let attractions = []
    if (data && typeof data === 'object') {
      if (data.featured || data.feed) {
        const allItems = []
        if (data.featured) allItems.push(data.featured)
        if (data.feed && Array.isArray(data.feed)) {
          allItems.push(...data.feed)
        }
        attractions = allItems
      }
    }

    const formattedItems = attractions.map((attraction: any, index: number) => ({
      id: attraction.id || `${attraction.table_name}_${attraction.place_id}`,
      title: attraction.name || attraction.title,
      author: attraction.city?.name || attraction.region || '여행지',
      genre: category,
      views: attraction.views || attraction.bookmark_cnt || Math.floor(Math.random() * 5000) + 1000,
      imageUrl: attraction.imageUrl || getImageUrl(attraction.image_urls) || `https://picsum.photos/100/100?random=${Date.now() + index}`
    }))

    return {
      leftColumnItems: formattedItems.slice(0, 8),
      rightColumnItems: formattedItems.slice(8, 15)
    }
  }

  // 페이지 로드/언마운트 시 스크롤 위치 관리
  useEffect(() => {
    // 페이지 로드시 뒤로가기 여부 확인 (Performance Navigation API 사용)
    const handlePageLoad = () => {
      if (typeof window !== 'undefined') {
        // 뒤로가기로 온 경우 스크롤 위치 복원
        const navigation = performance.getEntriesByType('navigation')[0] as any
        if (navigation && navigation.type === 'back_forward') {
          setIsNavigatedBack(true)
          restoreScrollPosition()
        }
      }
    }

    handlePageLoad()

    // 페이지 언마운트시 스크롤 위치 저장
    const handleBeforeUnload = () => {
      saveScrollPosition()
    }

    // visibilitychange로 탭 전환시에도 스크롤 위치 저장
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        saveScrollPosition()
      }
    }

    // popstate 이벤트로 뒤로가기 감지
    const handlePopState = () => {
      setIsNavigatedBack(true)
      setTimeout(() => {
        restoreScrollPosition()
      }, 100)
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    window.addEventListener('popstate', handlePopState)
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
      window.removeEventListener('popstate', handlePopState)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [])

  // sessionStorage에서 데이터 불러오기
  const loadFromStorage = () => {
    if (typeof window === 'undefined') return null
    try {
      const stored = sessionStorage.getItem('recommendations-data')
      return stored ? JSON.parse(stored) : null
    } catch (error) {
      console.error('Failed to load from storage:', error)
      return null
    }
  }

  // sessionStorage에 데이터 저장하기
  const saveToStorage = (data: any) => {
    if (typeof window === 'undefined') return
    try {
      sessionStorage.setItem('recommendations-data', JSON.stringify(data))
    } catch (error) {
      console.error('Failed to save to storage:', error)
    }
  }

  // 스크롤 위치 저장하기
  const saveScrollPosition = () => {
    if (typeof window !== 'undefined') {
      const scrollY = window.scrollY
      sessionStorage.setItem('recommendations-scroll', scrollY.toString())
    }
  }

  // 스크롤 위치 복원하기
  const restoreScrollPosition = () => {
    if (typeof window !== 'undefined') {
      const savedScroll = sessionStorage.getItem('recommendations-scroll')
      if (savedScroll) {
        const scrollY = parseInt(savedScroll)
        setTimeout(() => {
          window.scrollTo({ top: scrollY, behavior: 'auto' })
        }, 100)
      }
    }
  }

  // 카테고리 데이터 로드
  useEffect(() => {
    const loadCategoryData = async () => {
      const cacheKey = `recommendations-${selectedCategory}`

      // 캐시된 데이터 확인 (10분 캐시)
      if (isCacheValid(cacheKey, 10 * 60 * 1000)) {
        const cachedData = getCachedData<{leftColumnItems: RecommendationItem[], rightColumnItems: RecommendationItem[]}>(cacheKey)
        if (cachedData) {
          setLeftColumnItems(cachedData.leftColumnItems)
          setRightColumnItems(cachedData.rightColumnItems)
          setLoading(false)

          if (isNavigatedBack) {
            setTimeout(() => {
              restoreScrollPosition()
            }, 200)
          }
          return
        }
      }

      // 새 데이터 fetching
      setLoading(true)
      try {
        const categoryData = await fetchCategoryData(selectedCategory)

        setLeftColumnItems(categoryData.leftColumnItems)
        setRightColumnItems(categoryData.rightColumnItems)

        // 캐시에 저장 (10분 캐시)
        setCachedData(cacheKey, categoryData, 10 * 60 * 1000)

      } catch (error) {
        console.error('데이터 가져오기 실패:', error)
        setLeftColumnItems([])
        setRightColumnItems([])
      } finally {
        setLoading(false)
      }
    }

    loadCategoryData()
  }, [selectedCategory, session])

  // 추가 섹션 데이터 가져오기
  useEffect(() => {
    const fetchAdditionalSections = async () => {
      // 저장된 데이터 확인
      const storedData = loadFromStorage()
      if (storedData && storedData.discoveryItems && storedData.newItems &&
        storedData.popularItems && storedData.hiddenItems &&
        storedData.themeItems && storedData.seasonalItems) {
        // 저장된 데이터가 있으면 사용
        setDiscoveryItems(storedData.discoveryItems || [])
        setNewItems(storedData.newItems || [])
        setPopularItems(storedData.popularItems || [])
        setHiddenItems(storedData.hiddenItems || [])
        setThemeItems(storedData.themeItems || [])
        setSeasonalItems(storedData.seasonalItems || [])

        // 뒤로가기로 온 경우 스크롤 위치 복원을 데이터 로드 후에 실행
        if (isNavigatedBack) {
          setTimeout(() => {
            restoreScrollPosition()
          }, 300)
        }
        return
      }

      try {
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

        // ❌ v1 API 주석처리
        // "오늘의 발견" 섹션 데이터 (다양한 카테고리에서 인기 장소들)
        // const discoveryResponse = await fetch(`${API_BASE_URL}/proxy/api/v1/attractions/search?q=&limit=4`)

        // ✅ v2 탐색 피드 API 사용
        const discoveryResponse = await fetch(`${API_BASE_URL}/proxy/api/v2/recommendations/main-feed/explore`)
        let discoveryData: any = null
        if (discoveryResponse.ok) {
          discoveryData = await discoveryResponse.json()
          // v2 탐색 피드 응답 처리
          let discoveryAttractions: any[] = []
          if (discoveryData && discoveryData.data) {
            // { data: { region: { category: [items] } } } 형식에서 아이템 추출
            Object.values(discoveryData.data).forEach((regionData: any) => {
              Object.values(regionData).forEach((categoryItems: any) => {
                if (Array.isArray(categoryItems)) {
                  discoveryAttractions.push(...categoryItems)
                }
              })
            })
            discoveryAttractions = discoveryAttractions.slice(0, 4) // 4개만 선택
          }

          const formattedDiscoveryItems = discoveryAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '여행지',
            genre: getCategoryInKorean(attraction.category),
            views: Math.floor(Math.random() * 3000) + 1000,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random()}`,
            tags: ['추천', '인기', '특별']
          }))

          setDiscoveryItems(formattedDiscoveryItems)
        }

        // ❌ v1 API 주석처리 - v2 탐색 피드 재사용
        // "새로 나온 코스" 섹션 데이터 (최근 추가된 장소들)
        // const newResponse = await fetch(`${API_BASE_URL}/proxy/api/v1/attractions/search?q=&limit=3`)

        // v2 탐색 피드에서 다른 아이템들 사용
        let newAttractions: any[] = []
        if (discoveryData && discoveryData.data) {
          Object.values(discoveryData.data).forEach((regionData: any) => {
            Object.values(regionData).forEach((categoryItems: any) => {
              if (Array.isArray(categoryItems)) {
                newAttractions.push(...categoryItems)
              }
            })
          })
          newAttractions = newAttractions.slice(4, 7) // 4-6 인덱스 3개 선택
        }
        // v2 데이터를 이미 추출했으므로 조건문 수정
        if (newAttractions.length > 0) {

          const formattedNewItems = newAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '새로운 여행지',
            genre: getCategoryInKorean(attraction.category),
            views: Math.floor(Math.random() * 2000) + 500,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random() * 1000}`
          }))

          setNewItems(formattedNewItems)
        }

        // ❌ v1 API 주석처리 - v2 탐색 피드 재사용
        // "인기 여행지" 섹션 데이터 (높은 평점 위주)
        // const popularResponse = await fetch(`${API_BASE_URL}/proxy/api/v1/attractions/search?q=&limit=5`)

        // v2 탐색 피드에서 다른 아이템들 사용
        let popularAttractions: any[] = []
        if (discoveryData && discoveryData.data) {
          Object.values(discoveryData.data).forEach((regionData: any) => {
            Object.values(regionData).forEach((categoryItems: any) => {
              if (Array.isArray(categoryItems)) {
                popularAttractions.push(...categoryItems)
              }
            })
          })
          popularAttractions = popularAttractions.slice(7, 12) // 7-11 인덱스 5개 선택
        }
        // v2 데이터를 이미 추출했으므로 조건문 수정
        if (popularAttractions.length > 0) {

          const formattedPopularItems = popularAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '인기 여행지',
            genre: getCategoryInKorean(attraction.category),
            views: Math.floor(Math.random() * 8000) + 3000,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random() * 100}`
          }))

          setPopularItems(formattedPopularItems)
        }

        // ❌ v1 API 주석처리 - v2 탐색 피드 재사용
        // "숨은 명소" 섹션 데이터 (자연/인문 카테고리 위주)
        // const hiddenResponse = await fetch(`${API_BASE_URL}/proxy/api/v1/attractions/search?q=&category=nature&limit=4`)

        // v2 탐색 피드에서 nature 카테고리 아이템들 사용
        let hiddenAttractions: any[] = []
        if (discoveryData && discoveryData.data) {
          Object.values(discoveryData.data).forEach((regionData: any) => {
            if (regionData.nature && Array.isArray(regionData.nature)) {
              hiddenAttractions.push(...regionData.nature)
            }
          })
          hiddenAttractions = hiddenAttractions.slice(0, 4) // 4개만 선택
        }
        // v2 데이터를 이미 추출했으므로 조건문 수정
        if (hiddenAttractions.length > 0) {

          const formattedHiddenItems = hiddenAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '숨은 명소',
            genre: getCategoryInKorean(attraction.category),
            views: Math.floor(Math.random() * 2500) + 800,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random() * 200}`
          }))

          setHiddenItems(formattedHiddenItems)
        }

        // ❌ v1 API 주석처리 - v2 탐색 피드 재사용
        // "테마별 여행" 섹션 데이터 (다양한 카테고리 혼합)
        // const themeResponse = await fetch(`${API_BASE_URL}/proxy/api/v1/attractions/search?q=&limit=6`)

        // v2 탐색 피드에서 다양한 카테고리 아이템들 사용
        let themeAttractions: any[] = []
        if (discoveryData && discoveryData.data) {
          Object.values(discoveryData.data).forEach((regionData: any) => {
            Object.values(regionData).forEach((categoryItems: any) => {
              if (Array.isArray(categoryItems)) {
                themeAttractions.push(...categoryItems)
              }
            })
          })
          themeAttractions = themeAttractions.slice(12, 18) // 12-17 인덱스 6개 선택
        }
        // v2 데이터를 이미 추출했으므로 조건문 수정
        if (themeAttractions.length > 0) {

          const formattedThemeItems = themeAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '테마 여행',
            genre: getCategoryInKorean(attraction.category),
            views: Math.floor(Math.random() * 4000) + 1500,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random() * 300}`
          }))

          setThemeItems(formattedThemeItems)
        }

        // ❌ v1 API 주석처리 - v2 탐색 피드 재사용
        // "계절 추천" 섹션 데이터 (레저/자연 카테고리 위주)
        // const seasonalResponse = await fetch(`${API_BASE_URL}/proxy/api/v1/attractions/search?q=&category=leisure_sports&limit=4`)

        // v2 탐색 피드에서 leisure_sports 카테고리 아이템들 사용
        let seasonalAttractions: any[] = []
        if (discoveryData && discoveryData.data) {
          Object.values(discoveryData.data).forEach((regionData: any) => {
            if (regionData.activity && Array.isArray(regionData.activity)) {
              seasonalAttractions.push(...regionData.activity)
            }
          })
          seasonalAttractions = seasonalAttractions.slice(0, 4) // 4개만 선택
        }
        // v2 데이터를 이미 추출했으므로 조건문 수정
        if (seasonalAttractions.length > 0) {

          const formattedSeasonalItems = seasonalAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '계절 추천',
            genre: getCategoryInKorean(attraction.category),
            views: Math.floor(Math.random() * 3500) + 1200,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random() * 400}`
          }))

          setSeasonalItems(formattedSeasonalItems)
        }

        // 모든 API 호출이 완료된 후 데이터를 sessionStorage에 저장
        setTimeout(() => {
          const currentStoredData = loadFromStorage() || {}
          // state에서 현재 값을 가져와서 저장 (빈 배열이 아닌 경우에만)
          const dataToSave: any = { ...currentStoredData }

          // 각 섹션의 데이터가 있으면 저장
          const sections = [
            { key: 'discoveryItems', getter: () => discoveryItems },
            { key: 'newItems', getter: () => newItems },
            { key: 'popularItems', getter: () => popularItems },
            { key: 'hiddenItems', getter: () => hiddenItems },
            { key: 'themeItems', getter: () => themeItems },
            { key: 'seasonalItems', getter: () => seasonalItems }
          ]

          sections.forEach(section => {
            const data = section.getter()
            if (data && data.length > 0) {
              dataToSave[section.key] = data
            }
          })

          saveToStorage(dataToSave)
        }, 500) // state 업데이트를 충분히 기다림
      } catch (error) {
        console.error('추가 섹션 데이터 가져오기 실패:', error)
        // 실패시 빈 데이터로 설정
        setDiscoveryItems([])
        setNewItems([])
        setPopularItems([])
        setHiddenItems([])
        setThemeItems([])
        setSeasonalItems([])
      }
    }

    fetchAdditionalSections()
  }, [])

  // 카테고리 한국어 변환 함수
  const getCategoryInKorean = (category: string): string => {
    const categoryMap: { [key: string]: string } = {
      'leisure_sports': '레저',
      'accommodation': '숙박',
      'shopping': '쇼핑',
      'nature': '자연',
      'restaurants': '맛집',
      'humanities': '인문'
    }
    return categoryMap[category] || '여행'
  }

  // 이미지 URL 추출 함수
  const getImageUrl = (imageUrls: any): string => {
    if (!imageUrls) return '';

    try {
      // JSON 문자열인 경우 파싱
      const urls = typeof imageUrls === 'string' ? JSON.parse(imageUrls) : imageUrls;

      // 배열인 경우 첫 번째 이미지 반환
      if (Array.isArray(urls) && urls.length > 0) {
        return urls[0];
      }

      return '';
    } catch (error) {
      console.error('이미지 URL 파싱 오류:', error);
      return '';
    }
  }

  // 스마트한 카테고리 변경 핸들러
  const handleCategoryChange = (newCategory: string) => {
    if (newCategory === selectedCategory) return

    // 새 카테고리에 캐시된 데이터가 있는지 확인
    const cacheKey = `recommendations-${newCategory}`

    // 캐시된 데이터가 있으면 로딩 표시 없이 즉시 전환
    if (isCacheValid(cacheKey, 10 * 60 * 1000)) {
      setSelectedCategory(newCategory)
      setLoading(false)
    } else {
      // 캐시된 데이터가 없으면 로딩 표시
      setLoading(true)
      setSelectedCategory(newCategory)
    }
  }

  const handleItemClick = (item: RecommendationItem) => {
    // 상세 페이지로 이동하기 전 현재 스크롤 위치 저장
    saveScrollPosition()
    // 여행 상세 페이지로 이동
    router.push(`/attraction/${item.id}`)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
          <p className="text-[#94A9C9]">추천을 불러오는 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-white pb-20">
      {/* Header */}
      <div className="sticky top-0 z-40 bg-[#0B1220] border-b border-[#1F3C7A]/30">
        <div className="px-4 pt-4 pb-4">
          <h1 className="text-2xl font-bold text-[#3E68FF]">추천</h1>
          <p className="text-[#94A9C9] text-sm mt-1">당신을 위한 맞춤 여행 추천</p>
        </div>

        {/* Category Tabs */}
        <div className="px-4 pb-4">
          <div className="flex space-x-4 overflow-x-auto no-scrollbar">
            {categories.map((category) => (
              <button
                key={category}
                onClick={() => handleCategoryChange(category)}
                className={`flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-colors ${selectedCategory === category
                  ? 'bg-[#3E68FF] text-white'
                  : 'bg-[#1F3C7A]/30 text-[#6FA0E6] hover:bg-[#1F3C7A]/50'
                  }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-6">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-white">
            {session ? `${selectedCategory} 맞춤 추천` : `지금 많이 찾고 있는 ${selectedCategory}`}
          </h2>
        </div>

        {/* Horizontal Slide Layout */}
        <div className="overflow-x-auto no-scrollbar">
          <div className="flex gap-12 pb-4" style={{ width: 'max-content' }}>
            {/* Group items into pages of 6 (3 rows x 2 columns each) */}
            {(() => {
              const allItems = [...leftColumnItems, ...rightColumnItems]
              const pages = []
              for (let i = 0; i < allItems.length; i += 6) {
                pages.push(allItems.slice(i, i + 6))
              }

              return pages.map((pageItems, pageIndex) => (
                <div key={`page-${pageIndex}`} className="flex-shrink-0 w-[416px]">
                  <div className="flex gap-6">
                    {/* Left Column of this page */}
                    <div className="flex-1 space-y-4">
                      {pageItems.slice(0, 3).map((item) => {
                        return (
                          <div
                            key={item.id}
                            className="flex items-start space-x-3 cursor-pointer hover:bg-[#1F3C7A]/20 rounded-lg p-2 transition-colors min-h-[80px]"
                            onClick={() => handleItemClick(item)}
                          >
                            <div className="flex-shrink-0">
                              <img
                                src={item.imageUrl}
                                alt={item.title}
                                className="w-16 h-16 object-cover rounded-lg"
                                onError={(e) => {
                                  e.currentTarget.src = `https://picsum.photos/100/100?random=${Math.random() * 1000}`
                                }}
                              />
                            </div>
                            <div className="w-[116px] flex flex-col justify-center h-16 overflow-hidden">
                              <h3 className="font-semibold text-white text-sm mb-1 truncate w-full">{item.title}</h3>
                              <p className="text-[#94A9C9] text-xs mb-1 truncate w-full">{item.author}</p>
                              <div className="flex items-center w-full">
                                <svg className="w-3 h-3 text-yellow-400 mr-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                <span className="text-[#94A9C9] text-xs truncate flex-1">({item.views?.toLocaleString()})</span>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>

                    {/* Right Column of this page */}
                    <div className="flex-1 space-y-4">
                      {pageItems.slice(3, 6).map((item) => {
                        return (
                          <div
                            key={item.id}
                            className="flex items-start space-x-3 cursor-pointer hover:bg-[#1F3C7A]/20 rounded-lg p-2 transition-colors min-h-[80px]"
                            onClick={() => handleItemClick(item)}
                          >
                            <div className="flex-shrink-0">
                              <img
                                src={item.imageUrl}
                                alt={item.title}
                                className="w-16 h-16 object-cover rounded-lg"
                                onError={(e) => {
                                  e.currentTarget.src = `https://picsum.photos/100/100?random=${Math.random() * 1000}`
                                }}
                              />
                            </div>
                            <div className="w-[116px] flex flex-col justify-center h-16 overflow-hidden">
                              <h3 className="font-semibold text-white text-sm mb-1 truncate w-full">{item.title}</h3>
                              <p className="text-[#94A9C9] text-xs mb-1 truncate w-full">{item.author}</p>
                              <div className="flex items-center w-full">
                                <svg className="w-3 h-3 text-yellow-400 mr-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                <span className="text-[#94A9C9] text-xs truncate flex-1">({item.views?.toLocaleString()})</span>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              ))
            })()}
          </div>
        </div>

        {/* 오늘의 발견 섹션 */}
        <div className="mt-12 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">오늘의 발견</h2>
            <button className="text-[#6FA0E6] text-sm hover:text-[#3E68FF] transition-colors">
              더보기
            </button>
          </div>

          <div className="overflow-x-auto no-scrollbar">
            <div className="flex gap-4 pb-4" style={{ width: 'max-content' }}>
              {discoveryItems.map((item) => (
                <RecommendationCard
                  key={item.id}
                  item={item}
                  onItemClick={handleItemClick}
                  size="large"
                />
              ))}
            </div>
          </div>
        </div>

        {/* 새로 나온 코스 섹션 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">새로 나온 코스</h2>
            <button className="text-[#6FA0E6] text-sm hover:text-[#3E68FF] transition-colors">
              더보기
            </button>
          </div>

          <div className="overflow-x-auto no-scrollbar">
            <div className="flex gap-4 pb-4" style={{ width: 'max-content' }}>
              {newItems.map((item) => (
                <RecommendationCard
                  key={item.id}
                  item={item}
                  onItemClick={handleItemClick}
                  size="large"
                />
              ))}
            </div>
          </div>
        </div>

        {/* 인기 여행지 섹션 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">인기 여행지</h2>
            <button className="text-[#6FA0E6] text-sm hover:text-[#3E68FF] transition-colors">
              더보기
            </button>
          </div>

          <div className="overflow-x-auto no-scrollbar">
            <div className="flex gap-4 pb-4" style={{ width: 'max-content' }}>
              {popularItems.map((item) => (
                <RecommendationCard
                  key={item.id}
                  item={item}
                  onItemClick={handleItemClick}
                  size="large"
                />
              ))}
            </div>
          </div>
        </div>

        {/* 숨은 명소 섹션 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">숨은 명소</h2>
            <button className="text-[#6FA0E6] text-sm hover:text-[#3E68FF] transition-colors">
              더보기
            </button>
          </div>

          <div className="overflow-x-auto no-scrollbar">
            <div className="flex gap-4 pb-4" style={{ width: 'max-content' }}>
              {hiddenItems.map((item) => (
                <RecommendationCard
                  key={item.id}
                  item={item}
                  onItemClick={handleItemClick}
                  size="large"
                />
              ))}
            </div>
          </div>
        </div>

        {/* 테마별 여행 섹션 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">테마별 여행</h2>
            <button className="text-[#6FA0E6] text-sm hover:text-[#3E68FF] transition-colors">
              더보기
            </button>
          </div>

          <div className="overflow-x-auto no-scrollbar">
            <div className="flex gap-4 pb-4" style={{ width: 'max-content' }}>
              {themeItems.map((item) => (
                <RecommendationCard
                  key={item.id}
                  item={item}
                  onItemClick={handleItemClick}
                  size="large"
                />
              ))}
            </div>
          </div>
        </div>

        {/* 계절 추천 섹션 */}
        <div className="mb-8">
          <div className="overflow-x-auto no-scrollbar">
            <div className="flex gap-4 pb-4" style={{ width: 'max-content' }}>
              {seasonalItems.map((item) => (
                <RecommendationCard
                  key={item.id}
                  item={item}
                  onItemClick={handleItemClick}
                  size="large"
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      <BottomNavigation />
    </div>
  )
}

// 카테고리별 색상 반환 함수 (메인 화면과 동일)
function getCategoryColor(category: string): string {
  const colorMap: { [key: string]: string } = {
    nature: '#3FC9FF',
    humanities: '#3FC9FF',
    leisure_sports: '#3FC9FF',
    restaurants: '#FF3D00',
    shopping: '#753FFF',
    accommodation: '#FFD53F',
    자연: '#3FC9FF',
    인문: '#3FC9FF',
    레저: '#3FC9FF',
    맛집: '#FF3D00',
    쇼핑: '#753FFF',
    숙박: '#FFD53F'
  }
  return colorMap[category] || '#3E68FF'
}

// 카테고리 한국어 변환 함수 (메인 화면과 동일)
function getCategoryName(category: string): string {
  const categoryMap: { [key: string]: string } = {
    nature: '자연',
    restaurants: '맛집',
    shopping: '쇼핑',
    accommodation: '숙박',
    humanities: '인문',
    leisure_sports: '레저'
  }
  return categoryMap[category] || category
}

/** 추천 카드 컴포넌트 (정방형 스타일) */
function RecommendationCard({
  item,
  onItemClick,
  size = 'large'
}: {
  item: RecommendationItem
  onItemClick: (item: RecommendationItem) => void
  size?: 'large' | 'small'
}) {
  const categoryKey = item.genre?.trim() || ''
  const categoryColor = getCategoryColor(categoryKey)

  // 맛집과 쇼핑 카테고리는 밝은 색상, 나머지는 어두운 색상
  const textColor = (item.genre === 'restaurants' || item.genre === 'shopping' ||
    item.genre === '맛집' || item.genre === '쇼핑')
    ? '#E8EAFF'
    : '#0D121C'

  // 정방형 크기 설정
  const cardSize = size === 'large' ? 'w-[200px] h-[200px]' : 'w-[180px] h-[180px]'

  return (
    <figure
      className={`
        flex-shrink-0
        snap-start
        rounded-lg overflow-hidden
        shadow-lg
        ${cardSize}
        cursor-pointer transition-all duration-300
        group relative
      `}
      onClick={() => onItemClick(item)}
    >
      {/* 이미지 영역 (전체 카드 크기) */}
      <div className="relative w-full h-full overflow-hidden">
        {item.imageUrl ? (
          <>
            {/* 이미지 로딩 인디케이터 */}
            <div className="absolute inset-0 bg-gray-200 flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF]"></div>
            </div>

            <img
              src={item.imageUrl}
              alt={item.title}
              className="w-full h-full object-cover opacity-0 transition-opacity duration-300"
              onLoad={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.opacity = '1';
                const loadingIndicator = target.previousElementSibling as HTMLElement;
                if (loadingIndicator) loadingIndicator.style.display = 'none';
              }}
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                const loadingIndicator = target.previousElementSibling as HTMLElement;
                if (loadingIndicator) loadingIndicator.style.display = 'none';
                const fallback = target.nextElementSibling as HTMLElement;
                if (fallback) fallback.style.display = 'flex';
              }}
            />

            {/* 이미지 로드 실패 시 대체 UI */}
            <div
              className="w-full h-full bg-gradient-to-br from-gray-300 to-gray-400 flex items-center justify-center"
              style={{ display: 'none' }}
            >
              <span className="text-gray-600 text-lg text-center px-2">
                {item.title}
              </span>
            </div>
          </>
        ) : (
          /* 이미지가 없는 경우 기본 UI */
          <div className="w-full h-full bg-gradient-to-br from-gray-300 to-gray-400 flex items-center justify-center">
            <span className="text-gray-600 text-lg text-center px-2">
              {item.title}
            </span>
          </div>
        )}

        {/* 카테고리 배지 - 좌상단 */}
        <div className="absolute top-3 left-3">
          <span
            className="px-3 py-1 text-xs rounded-full font-medium"
            style={{
              backgroundColor: categoryColor,
              color: textColor
            }}
          >
            {getCategoryName(categoryKey) || item.genre}
          </span>
        </div>

        {/* 하단 제목 영역 - 카테고리 색상과 동일한 배경 */}
        <div className="absolute bottom-3 left-3 right-3">
          <div
            className="rounded-xl px-3 py-2 flex items-center justify-center"
            style={{
              backgroundColor: categoryColor
            }}
          >
            <h3
              className="font-bold text-sm text-center leading-tight"
              style={{
                color: textColor,
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden'
              }}
            >
              {item.title}
            </h3>
          </div>
        </div>
      </div>
    </figure>
  )
}