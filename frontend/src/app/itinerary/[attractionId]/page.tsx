'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

interface ItineraryBuilderProps {
  params: { attractionId: string }
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

interface SelectedPlace {
  id: string
  name: string
  category: string
  rating: number
  description: string
  dayNumber?: number // 선택된 날짜 (1, 2, 3...)
  sourceTable?: string // 어떤 테이블에서 온 데이터인지 추적
}

type CategoryKey = 'all' | 'accommodation' | 'humanities' | 'leisure_sports' | 'nature' | 'restaurants' | 'shopping'

export default function ItineraryBuilder({ params }: ItineraryBuilderProps) {
  const router = useRouter()
  const searchParams = useSearchParams()

  // URL에서 선택된 날짜들 파싱
  const startDateParam = searchParams.get('startDate')
  const endDateParam = searchParams.get('endDate')
  const daysParam = searchParams.get('days')

  // 상태 관리
  const [attraction, setAttraction] = useState<AttractionData | null>(null)
  const [relatedAttractions, setRelatedAttractions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [noMoreResults, setNoMoreResults] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey>('all')
  const [selectedDayForAdding, setSelectedDayForAdding] = useState<number>(1) // 현재 선택된 날짜 탭
  const [placesByDay, setPlacesByDay] = useState<{ [dayNumber: number]: SelectedPlace[] }>({}) // 날짜별로 장소 저장

  // 선택된 날짜 범위 생성
  const generateDateRange = () => {
    if (!startDateParam || !daysParam) {
      // fallback: 임시로 3일간의 날짜 생성
      const dates = []
      const start = new Date()
      start.setDate(start.getDate() + 1)
      for (let i = 0; i < 3; i++) {
        const date = new Date(start)
        date.setDate(start.getDate() + i)
        dates.push(date)
      }
      return dates
    }

    const dates = []
    const startDate = new Date(startDateParam)
    const dayCount = parseInt(daysParam)

    for (let i = 0; i < dayCount; i++) {
      const date = new Date(startDate)
      date.setDate(startDate.getDate() + i)
      dates.push(date)
    }
    return dates
  }

  const dateRange = generateDateRange()

  // 더 많은 관광지 로드 함수
  const loadMoreAttractions = async (cityName: string, region: string, page: number, isFirstLoad: boolean = false) => {
    if (isFirstLoad) {
      setLoading(true)
    } else {
      setLoadingMore(true)
    }

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const searchResponse = await fetch(
        `${API_BASE_URL}/api/v1/attractions/search?q=${encodeURIComponent(cityName)}&region=${encodeURIComponent(region)}&page=${page}&limit=50`
      )
      
      if (searchResponse.ok) {
        const searchData = await searchResponse.json()
        // 현재 관광지 제외
        const filtered = searchData.results.filter((item: any) => item.id !== params.attractionId)
        
        if (isFirstLoad) {
          setRelatedAttractions(filtered)
          setCurrentPage(0)
          setNoMoreResults(false)
        } else {
          if (filtered.length === 0) {
            setNoMoreResults(true)
            setHasMore(false)
          } else {
            setRelatedAttractions(prev => [...prev, ...filtered])
            setCurrentPage(page)
          }
        }
        
        setHasMore(searchData.hasMore || false)
      }
    } catch (error) {
      console.error('추가 관광지 로드 오류:', error)
    } finally {
      if (isFirstLoad) {
        setLoading(false)
      } else {
        setLoadingMore(false)
      }
    }
  }

  // API에서 관광지 상세 정보와 관련 관광지 가져오기
  useEffect(() => {
    let isCancelled = false // cleanup을 위한 플래그
    
    const fetchAttractionData = async () => {
      try {
        if (isCancelled) return // 이미 취소된 경우 중단
        
        setLoading(true)
        setRelatedAttractions([]) // 새로 로드하기 전에 기존 데이터 초기화
        
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
        
        // 선택된 관광지 정보 가져오기
        const attractionResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/attractions/${params.attractionId}`)
        if (!attractionResponse.ok) {
          throw new Error(`HTTP error! status: ${attractionResponse.status}`)
        }
        const attractionData = await attractionResponse.json()
        
        if (isCancelled) return // 이미 취소된 경우 중단
        
        setAttraction(attractionData)

        // 같은 도시의 다른 관광지들 검색으로 가져오기 (첫 페이지)
        await loadMoreAttractions(attractionData.city.name, attractionData.region, 0, true)
      } catch (error) {
        if (!isCancelled) {
          console.error('관광지 정보 로드 오류:', error)
          setError('관광지 정보를 불러올 수 없습니다.')
        }
      } finally {
        if (!isCancelled) {
          setLoading(false)
        }
      }
    }

    if (params.attractionId) {
      fetchAttractionData()
    }
    
    return () => {
      isCancelled = true // cleanup 시 플래그 설정
    }
  }, [params.attractionId])

  // 날짜별 장소 관리 헬퍼 함수들
  const getAllSelectedPlaces = (): SelectedPlace[] => {
    return Object.values(placesByDay).flat()
  }

  const getPlacesForDay = (dayNumber: number): SelectedPlace[] => {
    return placesByDay[dayNumber] || []
  }

  const isPlaceSelectedOnDay = (placeId: string, dayNumber: number): boolean => {
    const placesForDay = getPlacesForDay(dayNumber)
    return placesForDay.some(p => p.id === placeId)
  }

  const isPlaceSelectedOnAnyDay = (placeId: string): boolean => {
    return getAllSelectedPlaces().some(p => p.id === placeId)
  }


  // 카테고리 정의
  const categories = [
    { key: 'all' as CategoryKey, name: '전체', icon: '🏠' },
    { key: 'accommodation' as CategoryKey, name: '숙박', icon: '🏨' },
    { key: 'humanities' as CategoryKey, name: '인문', icon: '🏛️' },
    { key: 'leisure_sports' as CategoryKey, name: '레포츠', icon: '⚽' },
    { key: 'nature' as CategoryKey, name: '자연', icon: '🌿' },
    { key: 'restaurants' as CategoryKey, name: '맛집', icon: '🍽️' },
    { key: 'shopping' as CategoryKey, name: '쇼핑', icon: '🛍️' }
  ]

  // 모든 장소 가져오기
  const getAllPlaces = () => {
    return relatedAttractions
  }

  const allPlaces = getAllPlaces()

  // 선택된 카테고리에 따른 장소 필터링
  const getFilteredPlaces = () => {
    if (selectedCategory === 'all') {
      return allPlaces
    }
    
    // sourceTable 기준으로 필터링 (더 정확함)
    const filtered = allPlaces.filter(place => {
      // sourceTable이 있으면 그것을 우선 사용
      if (place.sourceTable) {
        return place.sourceTable === selectedCategory
      }
      // 없으면 category 사용 (폴백)
      return place.category === selectedCategory
    })
    
    return filtered
  }

  const filteredPlaces = getFilteredPlaces()

  const handleBack = () => {
    router.back()
  }

  const handleAddToItinerary = (place: any) => {
    const selectedPlace: SelectedPlace = {
      id: place.id,
      name: place.name,
      category: place.category,
      rating: place.rating,
      description: place.description,
      dayNumber: selectedDayForAdding,
      sourceTable: place.sourceTable // 테이블 정보 저장
    }

    setPlacesByDay(prev => {
      const newState = { ...prev }

      // 현재 선택된 날짜에서 해당 장소가 이미 있는지 확인
      if (isPlaceSelectedOnDay(place.id, selectedDayForAdding)) {
        // 해당 날짜에서 장소 제거
        newState[selectedDayForAdding] = getPlacesForDay(selectedDayForAdding).filter(p => p.id !== place.id)

        // 빈 배열이면 키 삭제
        if (newState[selectedDayForAdding].length === 0) {
          delete newState[selectedDayForAdding]
        }
      } else {
        // 다른 날짜에 이미 있다면 먼저 제거
        Object.keys(newState).forEach(dayKey => {
          const dayNumber = parseInt(dayKey, 10)
          newState[dayNumber] = newState[dayNumber].filter(p => p.id !== place.id)
          if (newState[dayNumber].length === 0) {
            delete newState[dayNumber]
          }
        })

        // 현재 날짜에 장소 추가
        if (!newState[selectedDayForAdding]) {
          newState[selectedDayForAdding] = []
        }
        newState[selectedDayForAdding].push(selectedPlace)
      }

      return newState
    })
  }

  const isPlaceSelected = (placeId: string) => {
    return isPlaceSelectedOnAnyDay(placeId)
  }

  const handleCreateItinerary = () => {
    const allSelectedPlaces = getAllSelectedPlaces()
    if (allSelectedPlaces.length === 0) {
      alert('최소 1개 이상의 장소를 선택해주세요!')
      return
    }

    // 선택된 장소와 날짜별 정보를 query parameter로 전달하며 지도 페이지로 이동
    const selectedPlaceIds = allSelectedPlaces.map(place => place.id).join(',')
    const dayNumbers = allSelectedPlaces.map(place => place.dayNumber || 1).join(',')
    const sourceTables = allSelectedPlaces.map(place => place.sourceTable || 'unknown').join(',')
    const startDate = dateRange[0].toISOString().split('T')[0]
    const endDate = dateRange[dateRange.length - 1].toISOString().split('T')[0]

    const queryParams = new URLSearchParams({
      places: selectedPlaceIds,
      dayNumbers: dayNumbers,
      sourceTables: sourceTables,
      startDate,
      endDate,
      days: dateRange.length.toString(),
      baseAttraction: params.attractionId
    })

    router.push(`/map?${queryParams.toString()}`)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
          <p className="text-[#94A9C9]">일정을 준비하는 중...</p>
        </div>
      </div>
    )
  }

  if (error || !attraction) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-[#94A9C9] text-lg mb-4">{error || '명소를 찾을 수 없습니다'}</p>
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
    <div className="min-h-screen bg-[#0B1220] text-white overflow-y-auto no-scrollbar">
      {/* Header */}
      <div className="flex items-center justify-between p-4">
        <button
          onClick={handleBack}
          className="p-2 hover:bg-[#1F3C7A]/30 rounded-full transition-colors"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <h1 className="text-lg font-semibold text-[#94A9C9]">
          여행 기간이 어떻게 되시나요?
        </h1>

        <div className="w-10 h-10" /> {/* Spacer */}
      </div>

      {/* Travel Period Info */}
      <div className="px-4 mb-6 text-center">
        <p className="text-[#6FA0E6] text-sm mb-2">
          {dateRange[0].getMonth() + 1}월 {dateRange[0].getDate()}일 - {dateRange[dateRange.length - 1].getMonth() + 1}월 {dateRange[dateRange.length - 1].getDate()}일
        </p>
        <p className="text-[#94A9C9] text-xs">
          {dateRange.length}일간의 여행 • 선택된 장소: {getAllSelectedPlaces().length}개
        </p>
      </div>

      {/* Day Selection Tabs */}
      <div className="px-4 mb-6">
        {/* <p className="text-[#94A9C9] text-sm mb-3 text-center">어느 날에 추가하실까요?</p> */}
        <div className="flex justify-center gap-2 overflow-x-auto no-scrollbar">
          {dateRange.map((date, index) => {
            const dayNumber = index + 1
            const isSelected = selectedDayForAdding === dayNumber
            const placesForDay = getPlacesForDay(dayNumber).length

            return (
              <button
                key={dayNumber}
                onClick={() => setSelectedDayForAdding(dayNumber)}
                className={`
                  flex-shrink-0 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 min-w-[70px]
                  ${isSelected
                    ? 'bg-[#3E68FF] text-white shadow-lg'
                    : 'bg-[#12345D]/50 text-[#94A9C9] hover:text-white hover:bg-[#1F3C7A]/50'
                  }
                `}
              >
                <div className="text-center">
                  <div className="font-semibold">Day {dayNumber}</div>
                  <div className="text-xs opacity-80">
                    {date.getMonth() + 1}/{date.getDate() + 1}
                  </div>
                  {placesForDay > 0 && (
                    <div className={`text-xs mt-1 ${isSelected ? 'text-white' : 'text-[#3E68FF]'}`}>
                      {placesForDay}개
                    </div>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Category Tabs */}
      <div className="px-4 mb-6">
        <div className="flex space-x-2 overflow-x-auto no-scrollbar">
          {categories.map(category => (
            <button
              key={category.key}
              onClick={() => setSelectedCategory(category.key)}
              className={`
                flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 flex items-center space-x-1
                ${selectedCategory === category.key
                  ? 'bg-[#3E68FF] text-white shadow-lg'
                  : 'bg-[#12345D]/50 text-[#94A9C9] hover:text-white hover:bg-[#1F3C7A]/50'
                }
              `}
            >
              <span>{category.icon}</span>
              <span>{category.name}</span>
              {category.key !== 'all' && (
                <span className="text-xs bg-white/20 px-1.5 py-0.5 rounded-full">
                  {allPlaces.filter(place => place.category === category.key).length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Places List */}
      <div key={selectedCategory} className="px-4 space-y-3">
        {filteredPlaces.length === 0 ? (
          <div className="bg-[#0F1A31]/30 rounded-xl p-8 text-center">
            <p className="text-[#6FA0E6] text-lg mb-2">추천할 장소가 없습니다</p>
            <p className="text-[#94A9C9] text-sm">다른 카테고리를 선택해보세요</p>
          </div>
        ) : (
          filteredPlaces.map(place => {
            const isSelectedOnCurrentDay = isPlaceSelectedOnDay(place.id, selectedDayForAdding)
            const isSelectedOnAnyOtherDay = isPlaceSelectedOnAnyDay(place.id) && !isSelectedOnCurrentDay
            return (
              <div
                key={`${selectedCategory}-${place.id}-${place.sourceTable}`}
                className={`
                  bg-[#0F1A31]/50 rounded-xl p-4 transition-all duration-200
                  ${isSelectedOnCurrentDay ? 'ring-2 ring-[#3E68FF] bg-[#3E68FF]/10' :
                    isSelectedOnAnyOtherDay ? 'ring-2 ring-[#6FA0E6] bg-[#6FA0E6]/10' : 'hover:bg-[#12345D]/50'}
                `}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-2">
                      <h3 className="font-semibold text-white text-lg">{place.name}</h3>
                      <span className="text-[#6FA0E6] text-xs bg-[#1F3C7A]/50 px-2 py-1 rounded-full">
                        {getCategoryName(place.category)}
                      </span>
                    </div>

                    <p className="text-[#94A9C9] text-sm mb-3 line-clamp-2">
                      {place.description}
                    </p>

                    <div className="flex items-center space-x-4">
                      <div className="flex items-center">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-[#6FA0E6] text-sm font-medium">{place.rating}</span>
                      </div>

                      {/* 추가 정보들 (거리, 예상 소요시간 등 - 실제 구현시 추가) */}
                      <span className="text-[#94A9C9] text-xs">📍 2.3km</span>
                      <span className="text-[#94A9C9] text-xs">⏱️ 1시간</span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleAddToItinerary(place)}
                    className={`
                      ml-4 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex-shrink-0
                      ${isSelectedOnCurrentDay
                        ? 'bg-[#3E68FF] text-white hover:bg-[#4C7DFF]'
                        : isSelectedOnAnyOtherDay
                          ? 'bg-[#6FA0E6] text-white hover:bg-[#5A8FD0]'
                          : 'bg-[#1F3C7A]/50 text-[#6FA0E6] hover:bg-[#3E68FF] hover:text-white'
                      }
                    `}
                  >
                    {isSelectedOnCurrentDay ? '선택됨' :
                      isSelectedOnAnyOtherDay ? `다른날` : '+ 추가'}
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Load More Button / No More Results Message */}
      {!loading && (
        <div className="px-4 mb-6">
          {hasMore && !noMoreResults ? (
            <button
              onClick={() => {
                if (attraction && !loadingMore) {
                  loadMoreAttractions(attraction.city.name, attraction.region, currentPage + 1, false)
                }
              }}
              disabled={loadingMore}
              className={`
                w-full py-3 rounded-xl text-sm font-medium transition-all duration-200
                ${loadingMore 
                  ? 'bg-[#1F3C7A]/30 text-[#6FA0E6] cursor-not-allowed' 
                  : 'bg-[#12345D]/50 text-[#94A9C9] hover:bg-[#1F3C7A]/50 hover:text-white'
                }
              `}
            >
              {loadingMore ? (
                <div className="flex items-center justify-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[#6FA0E6]"></div>
                  더 많은 장소 로딩 중...
                </div>
              ) : (
                '더 많은 장소 보기'
              )}
            </button>
          ) : noMoreResults || !hasMore ? (
            <div className="bg-[#0F1A31]/30 rounded-xl p-4 text-center">
              <div className="text-[#6FA0E6] text-sm mb-1">🏁</div>
              <p className="text-[#94A9C9] text-sm">더 이상 추천할 장소가 없습니다</p>
              <p className="text-[#6FA0E6] text-xs mt-1">위의 장소들 중에서 선택해보세요!</p>
            </div>
          ) : null}
        </div>
      )}

      {/* Selected Places Summary & Create Button */}
      {getAllSelectedPlaces().length > 0 && (
        <div className="px-4 py-6">
          <div className="bg-[#12345D]/50 rounded-2xl p-4 mb-4">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-white font-semibold">선택된 장소</h4>
              <span className="text-[#3E68FF] font-semibold">{getAllSelectedPlaces().length}개</span>
            </div>

            {/* 날짜별로 그룹화해서 표시 */}
            <div className="space-y-3">
              {dateRange.map((date, index) => {
                const dayNumber = index + 1
                const placesForDay = getPlacesForDay(dayNumber)

                if (placesForDay.length === 0) return null

                return (
                  <div key={dayNumber} className="border-l-2 border-[#3E68FF] pl-3">
                    <div className="text-xs text-[#6FA0E6] font-semibold mb-2">
                      Day {dayNumber} ({date.getMonth() + 1}/{date.getDate()})
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {placesForDay.map(place => (
                        <span key={place.id} className="text-xs bg-[#3E68FF]/20 text-[#6FA0E6] px-2 py-1 rounded-full">
                          {place.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Create Itinerary Button */}
      <div className="px-4 pb-8">
        <button
          onClick={handleCreateItinerary}
          disabled={getAllSelectedPlaces().length === 0}
          className={`
            w-full py-4 rounded-2xl text-lg font-semibold transition-all duration-200
            ${getAllSelectedPlaces().length > 0
              ? 'bg-[#3E68FF] hover:bg-[#4C7DFF] text-white shadow-lg'
              : 'bg-[#1F3C7A]/30 text-[#6FA0E6] cursor-not-allowed'
            }
          `}
        >
          여행 일정 만들기
        </button>
      </div>
    </div>
  )
}

// 카테고리 한국어 변환 함수
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