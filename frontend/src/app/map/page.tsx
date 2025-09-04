'use client'

import React, { useState, useRef, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

type CategoryKey = 'all' | 'tourist' | 'restaurants' | 'humanities' | 'nature' | 'shopping'

interface SelectedPlace {
  id: string
  name: string
  category: string
  rating: number
  description: string
  dayNumber?: number
  address?: string
  region?: string
  imageUrl?: string
  city?: {
    id: string
    name: string
    region: string
  }
  cityName?: string
  isPinned?: boolean
}

interface AttractionData {
  id: string
  name: string
  description: string
  imageUrl: string
  rating: number
  category: string
  address: string
  region: string
  city: {
    id: string
    name: string
    region: string
  }
  latitude?: number
  longitude?: number
  phoneNumber?: string
  parkingAvailable?: string
  usageHours?: string
  closedDays?: string
  detailedInfo?: string
  majorCategory?: string
  middleCategory?: string
  minorCategory?: string
  imageUrls?: string[]
  businessHours?: string
  signatureMenu?: string
  menu?: string
  roomCount?: string
  roomType?: string
  checkIn?: string
  checkOut?: string
  cookingAvailable?: string
}

export default function MapPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey>('all')
  const [bottomSheetHeight, setBottomSheetHeight] = useState(320)
  const [isDragging, setIsDragging] = useState(false)
  const [startY, setStartY] = useState(0)
  const [startHeight, setStartHeight] = useState(0)
  const [viewportHeight, setViewportHeight] = useState<number>(0)
  // URL 파라미터 읽기
  const placesParam = searchParams.get('places')
  const dayNumbersParam = searchParams.get('dayNumbers')
  const startDateParam = searchParams.get('startDate')
  const endDateParam = searchParams.get('endDate')
  const daysParam = searchParams.get('days')
  
  const [selectedItineraryPlaces, setSelectedItineraryPlaces] = useState<SelectedPlace[]>([])
  const [categoryPlaces, setCategoryPlaces] = useState<AttractionData[]>([])
  const [categoryLoading, setCategoryLoading] = useState(false)
  // 일정이 있으면 처음부터 일정을 보여줌
  const [showItinerary, setShowItinerary] = useState(!!placesParam)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const dragRef = useRef<HTMLDivElement>(null)

  // 화면 높이 측정
  useEffect(() => {
    const updateViewportHeight = () => {
      setViewportHeight(window.innerHeight)
    }
    updateViewportHeight()
    window.addEventListener('resize', updateViewportHeight)
    return () => window.removeEventListener('resize', updateViewportHeight)
  }, [])

  // 바텀 시트 드래그 핸들러
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true)
    setStartY(e.clientY)
    setStartHeight(bottomSheetHeight)
  }

  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches[0]) {
      setIsDragging(true)
      setStartY(e.touches[0].clientY)
      setStartHeight(bottomSheetHeight)
    }
  }

  // 드래그 이벤트 리스너
  useEffect(() => {
    const handleMove = (clientY: number) => {
      if (!isDragging) return
      const diff = startY - clientY
      // 카테고리 바 아래까지만 확장 가능 (상단 120px 남김)
      const maxHeight = viewportHeight - 120
      const newHeight = Math.max(100, Math.min(startHeight + diff, maxHeight))
      setBottomSheetHeight(newHeight)
    }

    const handleMouseMove = (e: MouseEvent) => handleMove(e.clientY)
    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches[0]) handleMove(e.touches[0].clientY)
    }

    const handleUp = () => {
      setIsDragging(false)
      // 스냅 로직
      const maxHeight = viewportHeight - 120
      if (bottomSheetHeight < 200) {
        setBottomSheetHeight(100)
      } else if (bottomSheetHeight > viewportHeight * 0.7) {
        setBottomSheetHeight(Math.min(maxHeight, viewportHeight - 120))
      }
    }

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleUp)
      document.addEventListener('touchmove', handleTouchMove)
      document.addEventListener('touchend', handleUp)
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleUp)
      document.removeEventListener('touchmove', handleTouchMove)
      document.removeEventListener('touchend', handleUp)
    }
  }, [isDragging, startY, startHeight, viewportHeight, bottomSheetHeight])

  // URL 파라미터에서 선택된 장소들 로드
  useEffect(() => {
    const loadSelectedPlaces = async () => {
      if (!placesParam || !dayNumbersParam) {
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        const placeIds = placesParam.split(',')
        const dayNumbers = dayNumbersParam.split(',').map(Number)
        
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
        const places: SelectedPlace[] = []
        
        for (let i = 0; i < placeIds.length; i++) {
          try {
            const response = await fetch(`${API_BASE_URL}/api/v1/attractions/attractions/${placeIds[i]}`)
            if (response.ok) {
              const attraction = await response.json()
              places.push({
                ...attraction,
                dayNumber: dayNumbers[i] || 1,
                isPinned: false
              })
            }
          } catch (error) {
            console.error(`Failed to load place ${placeIds[i]}:`, error)
          }
        }
        
        setSelectedItineraryPlaces(places)
      } catch (error) {
        console.error('선택된 장소들 로드 오류:', error)
        setError('선택된 장소들을 불러올 수 없습니다.')
      } finally {
        setLoading(false)
      }
    }

    loadSelectedPlaces()
  }, [placesParam, dayNumbersParam])

  // 카테고리별 장소 가져오기
  const fetchPlacesByCategory = async (category: CategoryKey) => {
    try {
      setCategoryLoading(true)
      const API_BASE_URL = 'http://localhost:8000'
      let url = `${API_BASE_URL}/api/v1/attractions/search?q=&limit=50`
      
      // category 매개변수 대신 검색어로 카테고리 처리
      if (category !== 'all') {
        // 카테고리별 검색어 매핑
        const categorySearchMap: { [key in CategoryKey]: string } = {
          'all': '',
          'tourist': '관광지',
          'restaurants': '맛집',
          'humanities': '문화',
          'nature': '자연',
          'shopping': '쇼핑'
        }
        
        const searchTerm = categorySearchMap[category] || ''
        if (searchTerm) {
          url = `${API_BASE_URL}/api/v1/attractions/search?q=${encodeURIComponent(searchTerm)}&limit=50`
        }
      }
      
      const response = await fetch(url)
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      
      const data = await response.json()
      setCategoryPlaces(data.attractions || [])
    } catch (error) {
      console.error('카테고리 장소 로드 오류:', error)
      setCategoryPlaces([])
    } finally {
      setCategoryLoading(false)
    }
  }

  // 카테고리 선택 시 장소 가져오기
  useEffect(() => {
    if (!showItinerary) {
      fetchPlacesByCategory(selectedCategory)
    }
  }, [selectedCategory, showItinerary])

  // 초기 로딩 시 전체 장소 가져오기 (일정 보기 모드가 아닐 때만)
  useEffect(() => {
    if (!placesParam) {
      fetchPlacesByCategory('all')
    }
  }, [])

  // 카테고리 정의
  const categories = [
    { key: 'all' as CategoryKey, name: '전체', icon: '🏠' },
    { key: 'tourist' as CategoryKey, name: '관광', icon: '🏛️' },
    { key: 'restaurants' as CategoryKey, name: '맛집', icon: '🍽️' },
    { key: 'humanities' as CategoryKey, name: '문화', icon: '🎭' },
    { key: 'nature' as CategoryKey, name: '자연', icon: '🌿' },
    { key: 'shopping' as CategoryKey, name: '쇼핑', icon: '🛍️' }
  ]

  // 일정 관리 함수들
  const handleRemoveFromItinerary = (placeId: string, dayNumber: number) => {
    const updatedPlaces = selectedItineraryPlaces.filter(
      place => !(place.id === placeId && place.dayNumber === dayNumber)
    );
    setSelectedItineraryPlaces(updatedPlaces);
    updateUrlParameters(updatedPlaces);
  };


  const updateUrlParameters = (places: SelectedPlace[]) => {
    if (places.length === 0) {
      router.replace('/map');
      return;
    }
    
    const placeIds = places.map(p => p.id).join(',');
    const dayNumbers = places.map(p => p.dayNumber || 1).join(',');
    const queryParams = new URLSearchParams();
    
    queryParams.set('places', placeIds);
    queryParams.set('dayNumbers', dayNumbers);
    
    if (startDateParam) queryParams.set('startDate', startDateParam);
    if (endDateParam) queryParams.set('endDate', endDateParam);
    if (daysParam) queryParams.set('days', daysParam);
    
    router.replace(`/map?${queryParams.toString()}`);
  };

  // 위아래 순서 변경 함수
  const movePlace = (placeId: string, direction: 'up' | 'down') => {
    setSelectedItineraryPlaces(prev => {
      const currentPlace = prev.find(p => p.id === placeId)
      if (!currentPlace) return prev
      
      // 같은 날짜의 장소들만 필터링
      const sameDayPlaces = prev.filter(p => p.dayNumber === currentPlace.dayNumber)
      const otherDayPlaces = prev.filter(p => p.dayNumber !== currentPlace.dayNumber)
      
      // 현재 장소의 인덱스 찾기
      const currentIndex = sameDayPlaces.findIndex(p => p.id === placeId)
      if (currentIndex === -1) return prev
      
      // 이동할 새 인덱스 계산
      let newIndex = currentIndex
      if (direction === 'up' && currentIndex > 0) {
        newIndex = currentIndex - 1
      } else if (direction === 'down' && currentIndex < sameDayPlaces.length - 1) {
        newIndex = currentIndex + 1
      } else {
        return prev // 이동할 수 없는 경우
      }
      
      // 배열에서 현재 장소 제거하고 새 위치에 삽입
      const updatedSameDayPlaces = [...sameDayPlaces]
      const [movedPlace] = updatedSameDayPlaces.splice(currentIndex, 1)
      updatedSameDayPlaces.splice(newIndex, 0, movedPlace)
      
      // 전체 배열 재구성
      const result = [...otherDayPlaces, ...updatedSameDayPlaces]
      const sortedResult = result.sort((a, b) => {
        if ((a.dayNumber || 0) !== (b.dayNumber || 0)) {
          return (a.dayNumber || 0) - (b.dayNumber || 0)
        }
        // 같은 날짜 내에서는 업데이트된 순서 유지
        if (a.dayNumber === currentPlace.dayNumber) {
          const aIndex = updatedSameDayPlaces.findIndex(p => p.id === a.id)
          const bIndex = updatedSameDayPlaces.findIndex(p => p.id === b.id)
          return aIndex - bIndex
        }
        return 0
      })
      
      // 업데이트된 결과로 URL 파라미터 즉시 업데이트
      setTimeout(() => {
        updateUrlParameters(sortedResult)
      }, 0)
      
      return sortedResult
    })
  };

  // 유틸리티 함수
  const handleBack = () => router.back()
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
  }
  const isFullScreen = bottomSheetHeight >= (viewportHeight || 0) - 2

  const getCategoryName = (category: string): string => {
    const categoryMap: { [key: string]: string } = {
      tourist: '관광',
      restaurants: '맛집',
      humanities: '문화',
      nature: '자연',
      shopping: '쇼핑',
      accommodation: '숙박',
      leisure: '레저'
    }
    return categoryMap[category] || category
  }

  // 로딩 상태
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
          <p className="text-[#94A9C9]">지도를 준비하는 중...</p>
        </div>
      </div>
    )
  }

  // 에러 상태
  if (error) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-[#94A9C9] text-lg mb-4">{error}</p>
          <button 
            onClick={() => router.back()}
            className="text-[#3E68FF] hover:text-[#6FA0E6] transition-colors"
          >
            돌아가기
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-white relative">
      {/* Header Back */}
      <div className="absolute top-4 left-4 z-50">
        <button
          onClick={handleBack}
          className="p-2 bg-black/30 rounded-full backdrop-blur-sm hover:bg-black/50 transition-colors"
        >
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Search Bar */}
      <div className="absolute top-4 left-16 right-4 z-40">
        <form onSubmit={handleSearch} className="relative">
          <div className="relative">
            <input
              type="text"
              placeholder="장소나 도시를 검색하세요"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 pr-12 py-3 text-sm rounded-2xl bg-black/30 backdrop-blur-sm text-white placeholder-gray-300 ring-1 ring-white/20 focus:outline-none focus:ring-2 focus:ring-[#3E68FF]/60"
            />
            <button
              type="submit"
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-300 hover:text-white transition"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
          </div>
        </form>
      </div>

      {/* Category Filter */}
      <div className="absolute top-20 left-4 right-4 z-40">
        <div className="flex space-x-2 overflow-x-auto no-scrollbar">
          {categories.map(category => (
            <button
              key={category.key}
              onClick={() => {
                setSelectedCategory(category.key)
                setShowItinerary(false)
              }}
              className={`flex-shrink-0 px-3 py-2 rounded-full text-xs font-medium transition-all duration-200 flex items-center space-x-1 backdrop-blur-sm ${
                selectedCategory === category.key
                  ? 'bg-[#3E68FF] text-white shadow-lg'
                  : 'bg-black/30 text-gray-300 hover:text-white hover:bg-black/50'
              }`}
            >
              <span>{category.icon}</span>
              <span>{category.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Map Area */}
      <div className="absolute top-0 left-0 right-0 bottom-0 bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
        <div className="text-center text-white/70">
          <div className="text-6xl mb-4">🗺️</div>
          <p className="text-lg font-medium mb-2">지도 영역</p>
          <p className="text-sm opacity-75">외부 지도 API 연동 예정</p>
        </div>
      </div>

      {/* Bottom Sheet */}
      <div
        className={`absolute bottom-0 left-0 right-0 bg-[#0B1220] z-30 shadow-2xl border-t border-[#1F3C7A]/30 ${
          isDragging ? '' : 'transition-all duration-300 ease-out'
        } ${isFullScreen ? 'rounded-none' : 'rounded-t-3xl'}`}
        style={{ 
          height: `${bottomSheetHeight}px`,
          minHeight: '100px',
          maxHeight: `${viewportHeight || 800}px`
        }}
      >
        {/* Drag Handle */}
        <div
          ref={dragRef}
          className="w-full flex justify-center py-4 cursor-grab active:cursor-grabbing hover:bg-[#1F3C7A]/20 transition-colors flex-shrink-0"
          onMouseDown={handleMouseDown}
          onTouchStart={handleTouchStart}
        >
          <div className={`w-12 h-1.5 rounded-full transition-colors ${isDragging ? 'bg-[#3E68FF]' : 'bg-[#6FA0E6]'}`} />
        </div>

        {/* Content */}
        <div 
          className="overflow-y-auto overflow-x-hidden no-scrollbar relative"
          style={{ 
            height: `${bottomSheetHeight - 60}px`,
            maxHeight: `${bottomSheetHeight - 60}px`
          }}
        >
          {showItinerary && selectedItineraryPlaces.length > 0 ? (
            /* 일정 보기 모드 */
            <div className="px-4 py-4">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-[#3E68FF]">내 일정</h2>
                <button
                  onClick={() => setShowItinerary(false)}
                  className="px-3 py-1.5 bg-[#1F3C7A]/30 hover:bg-[#3E68FF]/30 rounded-full text-sm text-[#6FA0E6] hover:text-white transition-colors"
                >
                  장소 찾기
                </button>
              </div>
              
              {/* 여행 정보 */}
              {startDateParam && endDateParam && daysParam && (
                <div className="bg-[#12345D]/50 rounded-2xl p-4 mb-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[#6FA0E6] text-sm mb-1">여행 기간</p>
                      <p className="text-white font-semibold">
                        {new Date(startDateParam).toLocaleDateString('ko-KR', { 
                          month: 'long', 
                          day: 'numeric' 
                        })} - {new Date(endDateParam).toLocaleDateString('ko-KR', { 
                          month: 'long', 
                          day: 'numeric' 
                        })}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[#6FA0E6] text-sm mb-1">총 일수</p>
                      <p className="text-white font-semibold">{daysParam}일</p>
                    </div>
                  </div>
                </div>
              )}

              {/* 날짜별 일정 */}
              {(() => {
                const groupedPlaces = selectedItineraryPlaces.reduce<{[key: number]: SelectedPlace[]}>((acc, place) => {
                  const day = place.dayNumber || 1;
                  if (!acc[day]) acc[day] = [];
                  acc[day].push(place);
                  return acc;
                }, {});

                const sortedDays = Object.keys(groupedPlaces).map(Number).sort((a, b) => a - b);

                return sortedDays.map(day => (
                  <div key={day} className="mb-6">
                    <div className="flex items-center mb-3">
                      <div className="bg-[#3E68FF] rounded-full w-8 h-8 flex items-center justify-center mr-3">
                        <span className="text-white text-sm font-bold">{day}</span>
                      </div>
                      <h3 className="text-lg font-semibold text-white">
                        {day}일차
                        {startDateParam && (
                          <span className="text-sm text-[#94A9C9] ml-2">
                            ({new Date(new Date(startDateParam).getTime() + (day - 1) * 24 * 60 * 60 * 1000).toLocaleDateString('ko-KR', { 
                              month: 'short', 
                              day: 'numeric' 
                            })})
                          </span>
                        )}
                      </h3>
                    </div>
                    
                    <div className="space-y-3 ml-5">
                      {groupedPlaces[day].map((place, index) => (
                        <div
                          key={`${place.id}-${day}-${index}`}
                          className="bg-[#1F3C7A]/20 border border-[#1F3C7A]/40 rounded-xl p-4 hover:bg-[#1F3C7A]/30 transition-colors"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1 cursor-pointer" onClick={() => router.push(`/attraction/${place.id}`)}>
                              <div className="flex items-center space-x-2 mb-2">
                                <h4 className="font-semibold text-white">{place.name}</h4>
                                <span className="text-[#6FA0E6] text-xs bg-[#1F3C7A]/50 px-2 py-1 rounded-full">
                                  {getCategoryName(place.category)}
                                </span>
                              </div>
                              <p className="text-[#94A9C9] text-sm mb-2">📍 {place.cityName || place.city?.name}</p>
                              <p className="text-[#94A9C9] text-sm mb-2 line-clamp-2">{place.description}</p>
                              <div className="flex items-center">
                                <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                <span className="text-[#6FA0E6] text-sm font-medium">{place.rating}</span>
                              </div>
                            </div>
                            
                            {/* 액션 버튼들 */}
                            <div className="flex gap-2 ml-3">
                              {/* 순서 이동 버튼들 */}
                              <div className="flex flex-col gap-1">
                                {/* 위로 이동 버튼 - 첫 번째 장소가 아닐 때만 표시 */}
                                {index > 0 ? (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      movePlace(place.id, 'up');
                                    }}
                                    className="p-1.5 bg-[#1F3C7A]/30 text-[#6FA0E6] hover:text-white hover:bg-[#3E68FF]/50 rounded-lg transition-colors"
                                    title="위로 이동"
                                  >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                    </svg>
                                  </button>
                                ) : (
                                  <div className="p-1.5 w-[32px] h-[32px]"></div>
                                )}
                                
                                {/* 아래로 이동 버튼 - 마지막 장소가 아닐 때만 표시 */}
                                {index < groupedPlaces[day].length - 1 ? (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      movePlace(place.id, 'down');
                                    }}
                                    className="p-1.5 bg-[#1F3C7A]/30 text-[#6FA0E6] hover:text-white hover:bg-[#3E68FF]/50 rounded-lg transition-colors"
                                    title="아래로 이동"
                                  >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                    </svg>
                                  </button>
                                ) : (
                                  <div className="p-1.5 w-[32px] h-[32px]"></div>
                                )}
                              </div>
                              
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRemoveFromItinerary(place.id, day);
                                }}
                                className="p-2 text-red-400 hover:text-red-300 hover:bg-red-500/20 rounded-full transition-colors"
                                title="일정에서 제거"
                              >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ));
              })()}

              {/* 일정 없음 메시지 */}
              {selectedItineraryPlaces.length === 0 && (
                <div className="text-center py-8">
                  <div className="text-6xl mb-4">📝</div>
                  <p className="text-[#94A9C9] text-lg mb-2">아직 선택된 장소가 없습니다</p>
                  <p className="text-[#6FA0E6] text-sm">장소를 찾아서 일정에 추가해보세요</p>
                </div>
              )}
            </div>
          ) : (
            /* 카테고리 보기 모드 */
            <div className="px-4 py-4">
              {/* 카테고리 헤더 */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xl font-bold text-[#3E68FF]">
                    {getCategoryName(selectedCategory)} 장소
                  </h2>
                  {selectedItineraryPlaces.length > 0 && (
                    <button
                      onClick={() => setShowItinerary(true)}
                      className="flex items-center space-x-1 px-3 py-1.5 bg-[#1F3C7A]/30 hover:bg-[#3E68FF]/30 rounded-full transition-colors text-sm text-[#6FA0E6] hover:text-white"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3a1 1 0 011-1h6a1 1 0 011 1v4M8 7h8M8 7H6a2 2 0 00-2 2v8a2 2 0 002-2V9a2 2 0 00-2-2h-2m-6 4v4m-4-2h8" />
                      </svg>
                      <span>내 일정</span>
                    </button>
                  )}
                </div>
                <p className="text-[#94A9C9] text-sm">
                  {categoryLoading ? '로딩 중...' : `${categoryPlaces.length}개의 장소를 찾았습니다`}
                </p>
              </div>
              
              {/* 카테고리 장소 목록 */}
              {categoryLoading ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF]"></div>
                </div>
              ) : categoryPlaces.length > 0 ? (
                <div className="space-y-3">
                  {categoryPlaces.map(place => (
                    <div
                      key={place.id}
                      className="bg-[#1F3C7A]/20 border border-[#1F3C7A]/40 rounded-xl p-4 hover:bg-[#1F3C7A]/30 transition-colors cursor-pointer"
                      onClick={() => router.push(`/attraction/${place.id}`)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            <h3 className="font-semibold text-white text-lg">{place.name}</h3>
                            <span className="text-[#6FA0E6] text-xs bg-[#1F3C7A]/50 px-2 py-1 rounded-full">
                              {getCategoryName(place.category)}
                            </span>
                          </div>
                          <p className="text-[#94A9C9] text-sm mb-2">📍 {place.city.name}</p>
                          <p className="text-[#94A9C9] text-sm mb-3 line-clamp-2">{place.description}</p>
                          <div className="flex items-center">
                            <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                            </svg>
                            <span className="text-[#6FA0E6] text-sm font-medium">{place.rating}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-[#94A9C9] text-lg mb-2">해당 카테고리의 장소가 없습니다</p>
                  <p className="text-[#6FA0E6] text-sm">다른 카테고리를 선택해보세요</p>
                </div>
              )}
            </div>
          )}
          
          {/* 하단 여백 */}
          <div className="h-20"></div>
        </div>
      </div>
    </div>
  )
}