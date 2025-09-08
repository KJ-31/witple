'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'

interface RecommendationItem {
  id: string
  title: string
  author: string
  genre: string
  rating: number
  imageUrl: string
  isNew?: boolean
  isUpdated?: boolean
  episodeCount?: number
  views?: number
  tags?: string[]
}

export default function RecommendationsPage() {
  const router = useRouter()
  const { data: session, status } = useSession()
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

  // DB에서 데이터 가져오기
  useEffect(() => {
    const fetchCategoryData = async () => {
      // 저장된 데이터 확인
      const storedData = loadFromStorage()
      if (storedData && storedData.selectedCategory === selectedCategory && storedData.leftColumnItems) {
        // 저장된 데이터가 현재 선택된 카테고리와 같으면 사용
        setLeftColumnItems(storedData.leftColumnItems || [])
        setRightColumnItems(storedData.rightColumnItems || [])
        setLoading(false)
        
        // 뒤로가기로 온 경우 스크롤 위치 복원을 데이터 로드 후에 실행
        if (isNavigatedBack) {
          setTimeout(() => {
            restoreScrollPosition()
          }, 200)
        }
        return
      }

      try {
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

        // 메인 추천 데이터 (15개) - 카테고리별 필터링
        const categoryMap: { [key: string]: string } = {
          '레저': 'leisure_sports',
          '숙박': 'accommodation',
          '쇼핑': 'shopping',
          '자연': 'nature',
          '맛집': 'restaurants',
          '인문': 'humanities'
        }
        const categoryFilter = categoryMap[selectedCategory] || 'leisure_sports'
        const response = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=&category=${categoryFilter}&limit=15`)
        if (response.ok) {
          const data = await response.json()
          const attractions = data.results || []

          const formattedItems = attractions.map((attraction: any, index: number) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '여행지',
            genre: selectedCategory,
            rating: attraction.rating || (4.9 - index * 0.1),
            views: Math.floor(Math.random() * 5000) + 1000,
            imageUrl: attraction.imageUrl || `https://picsum.photos/100/100?random=${Date.now() + index}`
          }))

          const leftItems = formattedItems.slice(0, 8)
          const rightItems = formattedItems.slice(8, 15)
          
          setLeftColumnItems(leftItems)
          setRightColumnItems(rightItems)

          // 현재 카테고리 데이터를 저장 (다른 데이터는 유지)
          const currentStoredData = loadFromStorage() || {}
          saveToStorage({
            ...currentStoredData,
            selectedCategory,
            leftColumnItems: leftItems,
            rightColumnItems: rightItems
          })
        } else {
          console.error('API 응답 실패:', response.status)
          setLeftColumnItems([])
          setRightColumnItems([])
        }
      } catch (error) {
        console.error('데이터 가져오기 실패:', error)
        setLeftColumnItems([])
        setRightColumnItems([])
      }

      setLoading(false)
    }


    fetchCategoryData()
  }, [selectedCategory])

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

        // "오늘의 발견" 섹션 데이터 (다양한 카테고리에서 인기 장소들)
        const discoveryResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=&limit=4`)
        if (discoveryResponse.ok) {
          const discoveryData = await discoveryResponse.json()
          const discoveryAttractions = discoveryData.results || []

          const formattedDiscoveryItems = discoveryAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '여행지',
            genre: getCategoryInKorean(attraction.category),
            rating: attraction.rating || 4.7,
            views: Math.floor(Math.random() * 3000) + 1000,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random()}`,
            tags: ['추천', '인기', '특별']
          }))

          setDiscoveryItems(formattedDiscoveryItems)
        }

        // "새로 나온 코스" 섹션 데이터 (최근 추가된 장소들)
        const newResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=&limit=3`)
        if (newResponse.ok) {
          const newData = await newResponse.json()
          const newAttractions = newData.results || []

          const formattedNewItems = newAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '새로운 여행지',
            genre: getCategoryInKorean(attraction.category),
            rating: attraction.rating || 4.5,
            views: Math.floor(Math.random() * 2000) + 500,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random() * 1000}`
          }))

          setNewItems(formattedNewItems)
        }

        // "인기 여행지" 섹션 데이터 (높은 평점 위주)
        const popularResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=&limit=5`)
        if (popularResponse.ok) {
          const popularData = await popularResponse.json()
          const popularAttractions = popularData.results?.sort((a: any, b: any) => (b.rating || 0) - (a.rating || 0)) || []
          
          const formattedPopularItems = popularAttractions.slice(0, 5).map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '인기 여행지',
            genre: getCategoryInKorean(attraction.category),
            rating: attraction.rating || 4.8,
            views: Math.floor(Math.random() * 8000) + 3000,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random() * 100}`
          }))

          setPopularItems(formattedPopularItems)
        }

        // "숨은 명소" 섹션 데이터 (자연/인문 카테고리 위주)
        const hiddenResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=&category=nature&limit=4`)
        if (hiddenResponse.ok) {
          const hiddenData = await hiddenResponse.json()
          const hiddenAttractions = hiddenData.results || []
          
          const formattedHiddenItems = hiddenAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '숨은 명소',
            genre: getCategoryInKorean(attraction.category),
            rating: attraction.rating || 4.6,
            views: Math.floor(Math.random() * 2500) + 800,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random() * 200}`
          }))

          setHiddenItems(formattedHiddenItems)
        }

        // "테마별 여행" 섹션 데이터 (다양한 카테고리 혼합)
        const themeResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=&limit=6`)
        if (themeResponse.ok) {
          const themeData = await themeResponse.json()
          const themeAttractions = themeData.results || []
          
          const formattedThemeItems = themeAttractions.slice(0, 6).map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '테마 여행',
            genre: getCategoryInKorean(attraction.category),
            rating: attraction.rating || 4.5,
            views: Math.floor(Math.random() * 4000) + 1500,
            imageUrl: attraction.imageUrl || `https://picsum.photos/200/280?random=${Date.now() + Math.random() * 300}`
          }))

          setThemeItems(formattedThemeItems)
        }

        // "계절 추천" 섹션 데이터 (레저/자연 카테고리 위주)
        const seasonalResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=&category=leisure_sports&limit=4`)
        if (seasonalResponse.ok) {
          const seasonalData = await seasonalResponse.json()
          const seasonalAttractions = seasonalData.results || []
          
          const formattedSeasonalItems = seasonalAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '계절 추천',
            genre: getCategoryInKorean(attraction.category),
            rating: attraction.rating || 4.4,
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
      <div className="sticky top-0 bg-[#0B1220]/95 backdrop-blur-md z-40 border-b border-[#1F3C7A]/30">
        <div className="px-4 py-4">
          <h1 className="text-2xl font-bold text-[#3E68FF]">추천</h1>
          <p className="text-[#94A9C9] text-sm mt-1">당신을 위한 맞춤 여행 추천</p>
        </div>

        {/* Category Tabs */}
        <div className="px-4 pb-4">
          <div className="flex space-x-4 overflow-x-auto no-scrollbar">
            {categories.map((category) => (
              <button
                key={category}
                onClick={() => setSelectedCategory(category)}
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
          <h2 className="text-xl font-semibold text-white">지금 많이 찾고 있는 {selectedCategory}</h2>
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
                <div key={`page-${pageIndex}`} className="flex-shrink-0 w-80">
                  <div className="flex gap-6">
                    {/* Left Column of this page */}
                    <div className="flex-1 space-y-6">
                      {pageItems.slice(0, 3).map((item, index) => {
                        const globalIndex = pageIndex * 6 + index
                        return (
                          <div
                            key={item.id}
                            className="flex items-center space-x-3 cursor-pointer hover:bg-[#1F3C7A]/20 rounded-lg p-2 transition-colors"
                            onClick={() => handleItemClick(item)}
                          >
                            <div className="flex-shrink-0 relative">
                              <img
                                src={item.imageUrl}
                                alt={item.title}
                                className="w-16 h-16 object-cover rounded-lg"
                                onError={(e) => {
                                  e.currentTarget.src = `https://picsum.photos/100/100?random=${Math.random() * 1000}`
                                }}
                              />
                              <div className="absolute top-1 left-1 bg-[#3E68FF] text-white text-xs px-1 py-0.5 rounded font-bold">
                                {globalIndex + 1}
                              </div>
                            </div>
                            <div className="flex-1 min-w-0">
                              <h3 className="font-semibold text-white text-sm mb-1 truncate">{item.title}</h3>
                              <p className="text-[#94A9C9] text-xs mb-1">{item.author}</p>
                              <div className="flex items-center">
                                <svg className="w-3 h-3 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                <span className="text-[#6FA0E6] text-xs mr-2">{item.rating}</span>
                                <span className="text-[#94A9C9] text-xs">({item.views?.toLocaleString()})</span>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>

                    {/* Right Column of this page */}
                    <div className="flex-1 space-y-6">
                      {pageItems.slice(3, 6).map((item, index) => {
                        const globalIndex = pageIndex * 6 + index + 3
                        return (
                          <div
                            key={item.id}
                            className="flex items-center space-x-3 cursor-pointer hover:bg-[#1F3C7A]/20 rounded-lg p-2 transition-colors"
                            onClick={() => handleItemClick(item)}
                          >
                            <div className="flex-shrink-0 relative">
                              <img
                                src={item.imageUrl}
                                alt={item.title}
                                className="w-16 h-16 object-cover rounded-lg"
                                onError={(e) => {
                                  e.currentTarget.src = `https://picsum.photos/100/100?random=${Math.random() * 1000}`
                                }}
                              />
                              <div className="absolute top-1 left-1 bg-[#3E68FF] text-white text-xs px-1 py-0.5 rounded font-bold">
                                {globalIndex + 1}
                              </div>
                            </div>
                            <div className="flex-1 min-w-0">
                              <h3 className="font-semibold text-white text-sm mb-1 truncate">{item.title}</h3>
                              <p className="text-[#94A9C9] text-xs mb-1">{item.author}</p>
                              <div className="flex items-center">
                                <svg className="w-3 h-3 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                <span className="text-[#6FA0E6] text-xs mr-2">{item.rating}</span>
                                <span className="text-[#94A9C9] text-xs">({item.views?.toLocaleString()})</span>
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
                <div
                  key={item.id}
                  className="flex-shrink-0 w-52 cursor-pointer group"
                  onClick={() => handleItemClick(item)}
                >
                  <div className="bg-[#1F2937] rounded-2xl overflow-hidden shadow-lg group-hover:shadow-xl transition-all duration-300">
                    <div className="relative">
                      <img
                        src={item.imageUrl}
                        alt={item.title}
                        className="w-full h-32 object-cover"
                        onError={(e) => {
                          e.currentTarget.src = `https://picsum.photos/200/280?random=${Math.random() * 1000}`
                        }}
                      />
                      <div className="absolute top-3 left-3 bg-[#3E68FF] text-white text-xs font-medium px-3 py-1 rounded-lg">
                        {item.genre}
                      </div>
                    </div>
                    <div className="p-4">
                      <h3 className="font-bold text-white text-base mb-2 leading-tight">{item.title}</h3>
                      <p className="text-[#9CA3AF] text-sm mb-3">{item.author}</p>
                      <div className="flex items-center">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-white text-sm font-medium mr-1">{item.rating}</span>
                        <span className="text-[#9CA3AF] text-sm">({item.views})</span>
                      </div>
                    </div>
                  </div>
                </div>
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
                <div
                  key={item.id}
                  className="flex-shrink-0 w-52 cursor-pointer group"
                  onClick={() => handleItemClick(item)}
                >
                  <div className="bg-[#1F2937] rounded-2xl overflow-hidden shadow-lg group-hover:shadow-xl transition-all duration-300">
                    <div className="relative">
                      <img
                        src={item.imageUrl}
                        alt={item.title}
                        className="w-full h-32 object-cover"
                        onError={(e) => {
                          e.currentTarget.src = `https://picsum.photos/200/280?random=${Math.random() * 1000}`
                        }}
                      />
                      <div className="absolute top-3 left-3 bg-[#3E68FF] text-white text-xs font-medium px-3 py-1 rounded-lg">
                        {item.genre}
                      </div>
                    </div>
                    <div className="p-4">
                      <h3 className="font-bold text-white text-base mb-2 leading-tight">{item.title}</h3>
                      <p className="text-[#9CA3AF] text-sm mb-3">{item.author}</p>
                      <div className="flex items-center">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-white text-sm font-medium mr-1">{item.rating}</span>
                        <span className="text-[#9CA3AF] text-sm">({item.views})</span>
                      </div>
                    </div>
                  </div>
                </div>
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
                <div
                  key={item.id}
                  className="flex-shrink-0 w-52 cursor-pointer group"
                  onClick={() => handleItemClick(item)}
                >
                  <div className="bg-[#1F2937] rounded-2xl overflow-hidden shadow-lg group-hover:shadow-xl transition-all duration-300">
                    <div className="relative">
                      <img
                        src={item.imageUrl}
                        alt={item.title}
                        className="w-full h-32 object-cover"
                        onError={(e) => {
                          e.currentTarget.src = `https://picsum.photos/200/280?random=${Math.random() * 1000}`
                        }}
                      />
                      <div className="absolute top-3 left-3 bg-[#3E68FF] text-white text-xs font-medium px-3 py-1 rounded-lg">
                        {item.genre}
                      </div>
                    </div>
                    <div className="p-4">
                      <h3 className="font-bold text-white text-base mb-2 leading-tight">{item.title}</h3>
                      <p className="text-[#9CA3AF] text-sm mb-3">{item.author}</p>
                      <div className="flex items-center">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-white text-sm font-medium mr-1">{item.rating}</span>
                        <span className="text-[#9CA3AF] text-sm">({item.views})</span>
                      </div>
                    </div>
                  </div>
                </div>
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
                <div
                  key={item.id}
                  className="flex-shrink-0 w-52 cursor-pointer group"
                  onClick={() => handleItemClick(item)}
                >
                  <div className="bg-[#1F2937] rounded-2xl overflow-hidden shadow-lg group-hover:shadow-xl transition-all duration-300">
                    <div className="relative">
                      <img
                        src={item.imageUrl}
                        alt={item.title}
                        className="w-full h-32 object-cover"
                        onError={(e) => {
                          e.currentTarget.src = `https://picsum.photos/200/280?random=${Math.random() * 1000}`
                        }}
                      />
                      <div className="absolute top-3 left-3 bg-[#3E68FF] text-white text-xs font-medium px-3 py-1 rounded-lg">
                        {item.genre}
                      </div>
                    </div>
                    <div className="p-4">
                      <h3 className="font-bold text-white text-base mb-2 leading-tight">{item.title}</h3>
                      <p className="text-[#9CA3AF] text-sm mb-3">{item.author}</p>
                      <div className="flex items-center">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-white text-sm font-medium mr-1">{item.rating}</span>
                        <span className="text-[#9CA3AF] text-sm">({item.views})</span>
                      </div>
                    </div>
                  </div>
                </div>
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
                <div
                  key={item.id}
                  className="flex-shrink-0 w-52 cursor-pointer group"
                  onClick={() => handleItemClick(item)}
                >
                  <div className="bg-[#1F2937] rounded-2xl overflow-hidden shadow-lg group-hover:shadow-xl transition-all duration-300">
                    <div className="relative">
                      <img
                        src={item.imageUrl}
                        alt={item.title}
                        className="w-full h-32 object-cover"
                        onError={(e) => {
                          e.currentTarget.src = `https://picsum.photos/200/280?random=${Math.random() * 1000}`
                        }}
                      />
                      <div className="absolute top-3 left-3 bg-[#3E68FF] text-white text-xs font-medium px-3 py-1 rounded-lg">
                        {item.genre}
                      </div>
                    </div>
                    <div className="p-4">
                      <h3 className="font-bold text-white text-base mb-2 leading-tight">{item.title}</h3>
                      <p className="text-[#9CA3AF] text-sm mb-3">{item.author}</p>
                      <div className="flex items-center">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-white text-sm font-medium mr-1">{item.rating}</span>
                        <span className="text-[#9CA3AF] text-sm">({item.views})</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 계절 추천 섹션 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">계절 추천</h2>
            <button className="text-[#6FA0E6] text-sm hover:text-[#3E68FF] transition-colors">
              더보기
            </button>
          </div>
          
          <div className="overflow-x-auto no-scrollbar">
            <div className="flex gap-4 pb-4" style={{ width: 'max-content' }}>
              {seasonalItems.map((item) => (
                <div
                  key={item.id}
                  className="flex-shrink-0 w-52 cursor-pointer group"
                  onClick={() => handleItemClick(item)}
                >
                  <div className="bg-[#1F2937] rounded-2xl overflow-hidden shadow-lg group-hover:shadow-xl transition-all duration-300">
                    <div className="relative">
                      <img
                        src={item.imageUrl}
                        alt={item.title}
                        className="w-full h-32 object-cover"
                        onError={(e) => {
                          e.currentTarget.src = `https://picsum.photos/200/280?random=${Math.random() * 1000}`
                        }}
                      />
                      <div className="absolute top-3 left-3 bg-[#3E68FF] text-white text-xs font-medium px-3 py-1 rounded-lg">
                        {item.genre}
                      </div>
                    </div>
                    <div className="p-4">
                      <h3 className="font-bold text-white text-base mb-2 leading-tight">{item.title}</h3>
                      <p className="text-[#9CA3AF] text-sm mb-3">{item.author}</p>
                      <div className="flex items-center">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-white text-sm font-medium mr-1">{item.rating}</span>
                        <span className="text-[#9CA3AF] text-sm">({item.views})</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-[#0F1A31]/95 backdrop-blur-md border-t border-[#1F3C7A]/30">
        <div className="flex items-center justify-around px-4 py-5 max-w-md mx-auto">
          <Link
            href="/"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="홈"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </Link>

          <Link
            href="/recommendations"
            className="flex flex-col items-center py-1 px-2 text-[#3E68FF]"
            aria-label="추천"
          >
            <svg className="w-6 h-6 mb-1" fill="currentColor" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
          </Link>

          <Link
            href="/treasure"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="보물찾기"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </Link>

          <Link
            href="/feed"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="피드"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
            </svg>
          </Link>

          <button
            onClick={() => {
              // NextAuth 세션 상태를 확인하여 로그인 여부 판단
              if (status === 'authenticated' && session) {
                router.push('/profile')
              } else {
                router.push('/auth/login')
              }
            }}
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="마이페이지"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </button>
        </div>
      </nav>
    </div>
  )
}