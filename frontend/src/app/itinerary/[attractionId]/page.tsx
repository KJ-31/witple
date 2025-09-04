'use client'

import React, { useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { RECOMMENDED_CITY_SECTIONS } from '../../../lib/dummyData'

interface ItineraryBuilderProps {
  params: { attractionId: string }
}

interface SelectedPlace {
  id: string
  name: string
  category: string
  rating: number
  description: string
  dayNumber?: number // 선택된 날짜 (1, 2, 3...)
}

type CategoryKey = 'all' | 'tourist' | 'food' | 'culture' | 'nature' | 'shopping'

export default function ItineraryBuilder({ params }: ItineraryBuilderProps) {
  const router = useRouter()
  const searchParams = useSearchParams()

  // URL에서 선택된 날짜들 파싱
  const startDateParam = searchParams.get('startDate')
  const endDateParam = searchParams.get('endDate')
  const daysParam = searchParams.get('days')

  // 상태 관리
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

  // 명소 정보 찾기
  const findAttractionAndCity = (attractionId: string) => {
    for (const city of RECOMMENDED_CITY_SECTIONS) {
      const attraction = city.attractions.find(attr => attr.id === attractionId)
      if (attraction) {
        return { attraction, city } // 명소, 도시
      }
    }
    return null
  }

  const result = findAttractionAndCity(params.attractionId)

  // 카테고리 정의
  const categories = [
    { key: 'all' as CategoryKey, name: '전체', icon: '🏠' },
    { key: 'tourist' as CategoryKey, name: '관광', icon: '🏛️' },
    { key: 'food' as CategoryKey, name: '맛집', icon: '🍽️' },
    { key: 'culture' as CategoryKey, name: '문화', icon: '🎭' },
    { key: 'nature' as CategoryKey, name: '자연', icon: '🌿' },
    { key: 'shopping' as CategoryKey, name: '쇼핑', icon: '🛍️' }
  ]

  // 모든 장소 가져오기
  const getAllPlaces = () => {
    if (!result) return []

    const { city, attraction } = result
    // 선택한 명소 제외하고 같은 도시의 다른 명소들과 전국의 관련 명소들 포함
    const allCityPlaces = city.attractions.filter(place => place.id !== attraction.id)

    // 다른 도시의 같은 카테고리 명소들도 추가 (추천 확장)
    const otherCityPlaces = RECOMMENDED_CITY_SECTIONS
      .filter(otherCity => otherCity.id !== city.id)
      .flatMap(otherCity => otherCity.attractions)
      .slice(0, 5) // 다른 도시에서 최대 5개만

    return [...allCityPlaces, ...otherCityPlaces]
  }

  const allPlaces = getAllPlaces()

  // 선택된 카테고리에 따른 장소 필터링
  const getFilteredPlaces = () => {
    if (selectedCategory === 'all') {
      return allPlaces
    }
    return allPlaces.filter(place => place.category === selectedCategory)
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
      dayNumber: selectedDayForAdding
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
    const startDate = dateRange[0].toISOString().split('T')[0]
    const endDate = dateRange[dateRange.length - 1].toISOString().split('T')[0]

    const queryParams = new URLSearchParams({
      places: selectedPlaceIds,
      dayNumbers: dayNumbers,
      startDate,
      endDate,
      days: dateRange.length.toString(),
      baseAttraction: params.attractionId
    })

    router.push(`/map?${queryParams.toString()}`)
  }

  if (!result) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <p className="text-[#94A9C9]">명소를 찾을 수 없습니다</p>
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
      <div className="px-4 space-y-3">
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
                key={place.id}
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
          선택
        </button>
      </div>
    </div>
  )
}

// 카테고리 한국어 변환 함수
function getCategoryName(category: string): string {
  const categoryMap: { [key: string]: string } = {
    tourist: '관광',
    food: '맛집',
    culture: '문화',
    nature: '자연',
    shopping: '쇼핑'
  }
  return categoryMap[category] || category
}