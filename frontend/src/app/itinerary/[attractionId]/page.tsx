'use client'

import React, { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { BottomNavigation } from '../../../components'

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

type CategoryKey = 'all' | 'accommodation' | 'humanities' | 'leisure_sports' | 'nature' | 'restaurants' | 'shopping' | 'bookmarked'

export default function ItineraryBuilder({ params }: ItineraryBuilderProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { data: session } = useSession()

  // URL에서 선택된 날짜들 파싱
  const startDateParam = searchParams.get('startDate')
  const daysParam = searchParams.get('days')

  // 상태 관리
  const [attraction, setAttraction] = useState<AttractionData | null>(null)
  const [relatedAttractions, setRelatedAttractions] = useState<any[]>([])
  const [allCategoryPlaces, setAllCategoryPlaces] = useState<any[]>([]) // 전체 카테고리 장소들 저장
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [noMoreResults, setNoMoreResults] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey>('all')
  const [selectedDayForAdding, setSelectedDayForAdding] = useState<number>(1) // 현재 선택된 날짜 탭
  const [placesByDay, setPlacesByDay] = useState<{ [dayNumber: number]: SelectedPlace[] }>({}) // 날짜별로 장소 저장
  const [bookmarkedPlaces, setBookmarkedPlaces] = useState<Set<string>>(new Set()) // 북마크된 장소들
  const [savedLocations, setSavedLocations] = useState<any[]>([]) // 저장된 장소 목록
  const [loadingSavedLocations, setLoadingSavedLocations] = useState(false)
  const [categoryCache, setCategoryCache] = useState<{ [key in CategoryKey]?: any[] }>({}) // 카테고리별 데이터 캐시
  const [loadedCategories, setLoadedCategories] = useState<Set<CategoryKey>>(new Set()) // 로드된 카테고리 추적

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

  // 추천 알고리즘 기반 관광지 로드 함수
  const loadFilteredAttractions = async (region: string, category: CategoryKey = 'all', isFirstLoad: boolean = false) => {
    // 캐시 확인 - 이미 로드된 카테고리면 캐시된 데이터 사용
    if (loadedCategories.has(category) && categoryCache[category]) {
      console.log(`캐시된 데이터 사용: ${category}`)
      if (isFirstLoad) {
        setRelatedAttractions(categoryCache[category] || [])
      }
      return
    }

    if (isFirstLoad) {
      setLoading(true)
    } else {
      setLoadingMore(true)
    }

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      
      // /filtered API 사용 - 추천 알고리즘 적용
      const categoryParam = category === 'all' ? '' : `&category=${category}`
      const filteredResponse = await fetch(
        `${API_BASE_URL}/api/v1/attractions/filtered?region=${encodeURIComponent(region)}&limit=50${categoryParam}`
      )
      
      if (filteredResponse.ok) {
        const filteredData = await filteredResponse.json()
        // 현재 관광지 제외
        const filtered = filteredData.attractions.filter((item: any) => item.id !== params.attractionId)
        
        if (isFirstLoad) {
          // 데이터가 없거나 부족할 경우 fallback으로 더 많은 데이터 가져오기
          if (filtered.length < 10) {
            await loadCategoryFallback(region, category, isFirstLoad)
            return
          }
          
          // 전체 카테고리 개수 계산을 위해 모든 장소 저장
          setAllCategoryPlaces(filtered)
          setRelatedAttractions(filtered)
          setCurrentPage(0)
          setNoMoreResults(false)
          // 추천 API에서 50개 받았으면 더 많은 데이터를 위해 hasMore = true로 설정
          setHasMore(filtered.length >= 50)
          
          // 캐시에 저장
          if (isFirstLoad) {
            setCategoryCache(prev => ({
              ...prev,
              [category]: filtered
            }))
            setLoadedCategories(prev => {
              const newSet = new Set(prev)
              newSet.add(category)
              return newSet
            })
            console.log(`카테고리 캐시 저장 완료: ${category}`)
          }
        } else {
          // 추천 알고리즘에서는 페이지네이션 없이 한 번에 모든 결과 반환
          setNoMoreResults(true)
          setHasMore(false)
        }
      }
    } catch (error) {
      console.error('추천 관광지 로드 오류:', error)
      // 추천 API 실패시 기존 search API로 fallback
      await loadCategoryFallback(region, category, isFirstLoad)
    } finally {
      if (isFirstLoad) {
        setLoading(false)
      } else {
        setLoadingMore(false)
      }
    }
  }

  // 카테고리별 fallback 로드 함수 (해당 지역의 인기 장소들)
  const loadCategoryFallback = async (region: string, category: CategoryKey = 'all', isFirstLoad: boolean = false) => {
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      
      // 1차: 해당 지역 + 카테고리로 검색
      const categoryQuery = category === 'all' ? region : `${region} ${getCategoryName(category)}`
      const searchResponse = await fetch(
        `${API_BASE_URL}/api/v1/attractions/search?q=${encodeURIComponent(categoryQuery)}&region=${encodeURIComponent(region)}&limit=50`
      )
      
      let filtered: any[] = []
      
      if (searchResponse.ok) {
        const searchData = await searchResponse.json()
        // 현재 관광지 제외
        filtered = searchData.results.filter((item: any) => item.id !== params.attractionId)
        
        // 카테고리 필터링 (search API 결과에서)
        if (category !== 'all') {
          filtered = filtered.filter((place: any) => {
            if (place.sourceTable) {
              return place.sourceTable === category
            }
            const categoryMap: { [key: string]: string } = {
              '자연': 'nature',
              '맛집': 'restaurants', 
              '쇼핑': 'shopping',
              '숙박': 'accommodation',
              '인문': 'humanities',
              '레저': 'leisure_sports'
            }
            return categoryMap[place.category] === category || place.category === category
          })
        }
      }
      
      // 2차: 데이터가 부족하면 전국 단위에서 더 가져오기
      if (filtered.length < 20) {
        try {
          const fallbackQuery = category === 'all' ? '관광지' : getCategoryName(category)
          const fallbackResponse = await fetch(
            `${API_BASE_URL}/api/v1/attractions/search?q=${encodeURIComponent(fallbackQuery)}&limit=50`
          )
          
          if (fallbackResponse.ok) {
            const fallbackData = await fallbackResponse.json()
            const additionalPlaces = fallbackData.results
              .filter((item: any) => item.id !== params.attractionId)
              .filter((item: any) => !filtered.some((existing: any) => existing.id === item.id))
            
            // 카테고리 필터링
            let categoryFiltered = additionalPlaces
            if (category !== 'all') {
              categoryFiltered = additionalPlaces.filter((place: any) => {
                if (place.sourceTable) {
                  return place.sourceTable === category
                }
                const categoryMap: { [key: string]: string } = {
                  '자연': 'nature',
                  '맛집': 'restaurants', 
                  '쇼핑': 'shopping',
                  '숙박': 'accommodation',
                  '인문': 'humanities',
                  '레저': 'leisure_sports'
                }
                return categoryMap[place.category] === category || place.category === category
              })
            }
            
            // 부족한 만큼만 추가
            const needCount = Math.max(0, 20 - filtered.length)
            filtered = [...filtered, ...categoryFiltered.slice(0, needCount)]
          }
        } catch (fallbackError) {
          console.error('전국 fallback 로드 오류:', fallbackError)
        }
      }
        
      if (isFirstLoad) {
        // fallback에서도 allCategoryPlaces 업데이트 (카테고리 카운트를 위해)
        setAllCategoryPlaces(filtered)
        setRelatedAttractions(filtered)
        setCurrentPage(0)
        setNoMoreResults(filtered.length === 0)
        setHasMore(false) // fallback에서는 추가 로드 없음
      } else {
        if (filtered.length === 0) {
          setNoMoreResults(true)
          setHasMore(false)
        } else {
          setRelatedAttractions(prev => [...prev, ...filtered])
          setCurrentPage(0)
        }
      }
    } catch (error) {
      console.error('Fallback 로드 오류:', error)
      // 마지막 fallback으로 기본 더미 데이터라도 제공
      if (isFirstLoad) {
        setAllCategoryPlaces([])
        setRelatedAttractions([])
        setNoMoreResults(true)
        setHasMore(false)
      }
    }
  }

  // 기존 search API (fallback용)
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
      console.error('관광지 로드 오류:', error)
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
        
        // attractionId가 유효한지 확인
        if (!params.attractionId || params.attractionId === 'undefined') {
          throw new Error('유효하지 않은 관광지 ID입니다.')
        }
        
        // 'general'인 경우 특정 attraction 정보 없이 전국 데이터 로드
        if (params.attractionId === 'general') {
          if (isCancelled) return
          
          // attraction 정보 없이 전국 데이터 로드
          setAttraction(null)
          await loadAllCategoriesForCount('전국')
          await loadFilteredAttractions('전국', 'all', true)
          return
        }
        
        // 선택된 관광지 정보 가져오기
        const attractionResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/${params.attractionId}`)
        if (!attractionResponse.ok) {
          throw new Error(`HTTP error! status: ${attractionResponse.status}`)
        }
        const attractionData = await attractionResponse.json()
        
        if (isCancelled) return // 이미 취소된 경우 중단
        
        setAttraction(attractionData)

        // 같은 지역의 추천 관광지들 가져오기 (추천 알고리즘 적용)
        // 전체 카테고리의 데이터를 로드하여 카테고리별 카운트 계산
        await loadAllCategoriesForCount(attractionData.region)
        await loadFilteredAttractions(attractionData.region, 'all', true)
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

  // 세션이 있을 때 저장된 장소들 초기 로드
  useEffect(() => {
    if (session) {
      loadSavedLocations()
    }
  }, [session])

  // 전체 카테고리의 데이터를 미리 로드하여 카운트 계산
  const loadAllCategoriesForCount = async (region: string) => {
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      
      // 전체 카테고리의 데이터를 한 번에 가져오기
      const allResponse = await fetch(
        `${API_BASE_URL}/api/v1/attractions/filtered?region=${encodeURIComponent(region)}&limit=100`
      )
      
      if (allResponse.ok) {
        const allData = await allResponse.json()
        const filtered = allData.attractions.filter((item: any) => item.id !== params.attractionId)
        setAllCategoryPlaces(filtered)
      } else {
        // API 실패시 search API로 fallback하여 모든 카테고리 데이터 수집
        const searchResponse = await fetch(
          `${API_BASE_URL}/api/v1/attractions/search?q=${encodeURIComponent(region)}&region=${encodeURIComponent(region)}&limit=100`
        )
        
        if (searchResponse.ok) {
          const searchData = await searchResponse.json()
          const filtered = searchData.results.filter((item: any) => item.id !== params.attractionId)
          setAllCategoryPlaces(filtered)
        }
      }
    } catch (error) {
      console.error('전체 카테고리 로드 오류:', error)
    }
  }

  // 카테고리 변경 시 추천 관광지 다시 로드
  useEffect(() => {
    if (selectedCategory) {
      if (selectedCategory === 'bookmarked') {
        // 북마크 카테고리인 경우 저장된 장소들 로드
        loadSavedLocations()
      } else {
        // 다른 카테고리인 경우 추천 관광지 로드
        const loadCategoryPlaces = async () => {
          const region = attraction?.region || '전국'
          await loadFilteredAttractions(region, selectedCategory, true)
        }
        loadCategoryPlaces()
      }
    }
  }, [selectedCategory, attraction])

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
    { key: 'bookmarked' as CategoryKey, name: '북마크', icon: '🔖' },
    { key: 'accommodation' as CategoryKey, name: '숙박', icon: '🏨' },
    { key: 'humanities' as CategoryKey, name: '인문', icon: '🏛️' },
    { key: 'leisure_sports' as CategoryKey, name: '레포츠', icon: '⚽' },
    { key: 'nature' as CategoryKey, name: '자연', icon: '🌿' },
    { key: 'restaurants' as CategoryKey, name: '맛집', icon: '🍽️' },
    { key: 'shopping' as CategoryKey, name: '쇼핑', icon: '🛍️' }
  ]

  // 모든 장소 가져오기 (캐시 우선 사용)
  const getAllPlaces = () => {
    // 현재 선택된 카테고리의 캐시된 데이터가 있으면 사용
    if (selectedCategory !== 'bookmarked' && categoryCache[selectedCategory]) {
      return categoryCache[selectedCategory] || []
    }
    
    // allCategoryPlaces가 비어있지 않으면 그것을 사용, 아니면 relatedAttractions 사용
    return allCategoryPlaces.length > 0 ? allCategoryPlaces : relatedAttractions
  }

  const allPlaces = getAllPlaces()

  // 선택된 카테고리에 따른 장소 필터링
  const getFilteredPlaces = () => {
    if (selectedCategory === 'all') {
      return allPlaces
    }
    
    // 북마크 카테고리인 경우 저장된 장소들을 반환
    if (selectedCategory === 'bookmarked') {
      return savedLocations.map(location => ({
        id: location.id,
        name: location.name,
        address: location.address,
        description: location.address,
        image: location.image || '',
        latitude: location.latitude ? parseFloat(location.latitude) : undefined,
        longitude: location.longitude ? parseFloat(location.longitude) : undefined,
        category: location.category || '저장된 장소',
        sourceTable: 'saved'
      }))
    }
    
    // sourceTable 기준으로 필터링 + 키워드 기반 매칭
    const filtered = allPlaces.filter(place => {
      // sourceTable이 있으면 그것을 우선 사용
      if (place.sourceTable) {
        return place.sourceTable === selectedCategory
      }
      
      // category를 영어로 변환해서 비교
      const categoryMap: { [key: string]: string } = {
        '자연': 'nature',
        '맛집': 'restaurants',
        '쇼핑': 'shopping',
        '숙박': 'accommodation',
        '인문': 'humanities',
        '레저': 'leisure_sports'
      }
      
      if (categoryMap[place.category] === selectedCategory || place.category === selectedCategory) {
        return true
      }
      
      // 키워드 기반 추가 매칭 (특히 인문 카테고리에서 유용)
      const categoryKeywords = {
        'humanities': ['인문', '문화', '박물관', '미술관', '역사', '전시관', '기념관', '향교', '서원', '궁', '성당', '절', '사찰', '교회'],
        'nature': ['자연', '공원', '산', '해변', '바다', '강', '호수', '계곡', '폭포', '숲'],
        'restaurants': ['맛집', '음식', '카페', '식당', '레스토랑'],
        'shopping': ['쇼핑', '시장', '백화점', '마트', '상점'],
        'accommodation': ['숙박', '호텔', '펜션', '리조트', '모텔'],
        'leisure_sports': ['레저', '스포츠', '체험', '놀이', '액티비티', '테마파크']
      }
      
      const keywords = categoryKeywords[selectedCategory as keyof typeof categoryKeywords] || []
      const placeText = `${place.name} ${place.description || ''} ${place.category || ''}`.toLowerCase()
      
      return keywords.some(keyword => placeText.includes(keyword))
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

  // 토큰 가져오기 함수
  const getToken = () => {
    // 먼저 세션에서 토큰 확인
    if ((session as any)?.backendToken) {
      return (session as any).backendToken
    }
    // 세션에 없으면 localStorage에서 확인
    return localStorage.getItem('access_token')
  }

  // 북마크 토글 함수
  const handleBookmarkToggle = async (place: any) => {
    if (!session) {
      alert('로그인이 필요합니다.')
      router.push('/auth/login')
      return
    }

    try {
      const token = getToken()
      if (!token) {
        alert('로그인이 필요합니다.')
        router.push('/auth/login')
        return
      }

      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const isBookmarked = bookmarkedPlaces.has(place.id)

      if (isBookmarked) {
        // 북마크 해제
        const checkResponse = await fetch(`${API_BASE_URL}/api/v1/saved-locations/check`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            name: place.name,
            address: place.address,
            latitude: place.latitude?.toString(),
            longitude: place.longitude?.toString()
          })
        })

        if (checkResponse.ok) {
          const checkData = await checkResponse.json()
          if (checkData.location_id) {
            const deleteResponse = await fetch(`${API_BASE_URL}/api/v1/saved-locations/${checkData.location_id}`, {
              method: 'DELETE',
              headers: {
                'Authorization': `Bearer ${token}`
              }
            })

            if (deleteResponse.ok) {
              setBookmarkedPlaces(prev => {
                const newSet = new Set(prev)
                newSet.delete(place.id)
                return newSet
              })
            }
          }
        }
      } else {
        // 북마크 추가
        const response = await fetch(`${API_BASE_URL}/api/v1/saved-locations/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            name: place.name,
            address: place.address,
            latitude: place.latitude?.toString(),
            longitude: place.longitude?.toString()
          })
        })

        if (response.ok) {
          setBookmarkedPlaces(prev => {
            const newSet = new Set(prev)
            newSet.add(place.id)
            return newSet
          })
        }
      }
    } catch (error) {
      console.error('북마크 처리 오류:', error)
    }
  }

  // 저장된 장소들을 가져오는 함수
  const loadSavedLocations = async () => {
    if (!session) return
    
    // 북마크 카테고리가 이미 캐시에 있으면 재사용
    if (loadedCategories.has('bookmarked') && categoryCache.bookmarked) {
      console.log('캐시된 북마크 데이터 사용')
      setSavedLocations(categoryCache.bookmarked)
      return
    }
    
    try {
      setLoadingSavedLocations(true)
      const token = getToken()
      
      if (!token) {
        console.log('토큰 없음 - 저장된 장소 로딩 건너뛰기')
        return
      }
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/saved-locations/`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        console.log('=== 저장된 장소 API 응답 디버깅 ===')
        console.log('전체 응답:', data)
        console.log('locations:', data.locations)
        console.log('saved_locations:', data.saved_locations)
        console.log('============================')
        
        // 프로필 페이지와 동일하게 data.locations 사용
        const locations = data.locations || data.saved_locations || []
        setSavedLocations(locations)
        
        // 북마크된 장소 ID들도 함께 업데이트
        const bookmarkedIds = new Set<string>(locations.map((loc: any) => String(loc.id)) || [])
        setBookmarkedPlaces(bookmarkedIds)
        
        // 북마크 데이터를 캐시에 저장
        setCategoryCache(prev => ({
          ...prev,
          bookmarked: locations
        }))
        
        setLoadedCategories(prev => {
          const newSet = new Set(prev)
          newSet.add('bookmarked')
          return newSet
        })
        console.log('북마크 캐시 저장 완료')
      } else {
        console.error('저장된 장소 로딩 실패:', response.status)
        setSavedLocations([])
      }
    } catch (error) {
      console.error('저장된 장소 로딩 중 오류:', error)
      setSavedLocations([])
    } finally {
      setLoadingSavedLocations(false)
    }
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

  if (error || (!attraction && params.attractionId !== 'general')) {
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
    <div className="min-h-screen bg-[#0B1220] text-white relative">
      {/* Scrollable Content */}
      <div className="overflow-y-auto no-scrollbar" style={{ height: 'calc(100vh - 120px)' }}>
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
            {params.attractionId === 'general' ? '여행 일정 만들기' : '여행 기간이 어떻게 되시나요?'}
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
            </button>
          ))}
        </div>
      </div>

      {/* Places List */}
      <div className="px-4 space-y-3 transition-all duration-300 ease-in-out">
        {/* 북마크 카테고리 로딩 상태 */}
        {selectedCategory === 'bookmarked' && loadingSavedLocations ? (
          <div className="bg-[#0F1A31]/30 rounded-xl p-8 text-center">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
            <p className="text-[#6FA0E6] text-lg mb-2">저장된 장소를 불러오는 중...</p>
            <p className="text-[#94A9C9] text-sm">잠시만 기다려주세요</p>
          </div>
        ) : 
        /* 북마크 카테고리 빈 상태 */
        selectedCategory === 'bookmarked' && filteredPlaces.length === 0 && !loadingSavedLocations ? (
          <div className="bg-[#0F1A31]/30 rounded-xl p-8 text-center">
            <div className="text-6xl mb-4">🔖</div>
            <p className="text-[#6FA0E6] text-lg mb-2">저장된 장소가 없습니다</p>
            <p className="text-[#94A9C9] text-sm mb-4">마음에 드는 장소를 북마크해보세요!</p>
            <div className="flex justify-center">
              <div className="bg-[#3E68FF]/20 px-4 py-2 rounded-full text-[#6FA0E6] text-sm">
                다른 카테고리에서 장소를 둘러보세요
              </div>
            </div>
          </div>
        ) :
        /* 일반 카테고리 빈 상태 */
        filteredPlaces.length === 0 && !loading && !loadingMore ? (
          <div className="bg-[#0F1A31]/30 rounded-xl p-8 text-center">
            <p className="text-[#6FA0E6] text-lg mb-2">🔍 더 많은 장소를 찾아보고 있어요!</p>
            <p className="text-[#94A9C9] text-sm mb-4">잠시 후 다른 카테고리의 인기 장소들이 표시됩니다</p>
            <div className="flex justify-center">
              <div className="animate-pulse bg-[#3E68FF]/20 px-4 py-2 rounded-full text-[#6FA0E6] text-sm">
                전국 인기 장소 검색 중...
              </div>
            </div>
          </div>
        ) : filteredPlaces.length === 0 ? (
          <div className="bg-[#0F1A31]/30 rounded-xl p-8 text-center">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
            <p className="text-[#6FA0E6] text-lg mb-2">맞춤 추천 장소를 찾는 중...</p>
            <p className="text-[#94A9C9] text-sm">잠시만 기다려주세요</p>
          </div>
        ) : (
          filteredPlaces.map(place => {
            const isSelectedOnCurrentDay = isPlaceSelectedOnDay(place.id, selectedDayForAdding)
            const isSelectedOnAnyOtherDay = isPlaceSelectedOnAnyDay(place.id) && !isSelectedOnCurrentDay
            return (
              <div
                key={`place-${place.id}-${place.sourceTable || 'default'}`}
                className={`
                  bg-[#0F1A31]/50 rounded-xl p-4 transition-all duration-200
                  ${isSelectedOnCurrentDay ? 'ring-2 ring-[#3E68FF] bg-[#3E68FF]/10' :
                    isSelectedOnAnyOtherDay ? 'ring-2 ring-[#6FA0E6] bg-[#6FA0E6]/10' : 'hover:bg-[#12345D]/50'}
                `}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-white text-lg mb-2">{place.name}</h3>

                    <p className="text-[#94A9C9] text-sm mb-3 line-clamp-2">
                      {place.description}
                    </p>

                    <div className="flex items-center space-x-2">
                      <span className="text-[#6FA0E6] text-xs bg-[#1F3C7A]/50 px-2 py-1 rounded-full">
                        {getCategoryName(place.category)}
                      </span>
                      <div className="flex items-center">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-[#6FA0E6] text-sm font-medium">{place.rating}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 ml-4 flex-shrink-0">
                    {/* 북마크 버튼 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleBookmarkToggle(place)
                      }}
                      className={`
                        p-2 rounded-lg transition-all duration-200
                        ${bookmarkedPlaces.has(place.id)
                          ? 'bg-[#3E68FF] text-white hover:bg-[#4C7DFF]'
                          : 'bg-[#1F3C7A]/50 text-[#6FA0E6] hover:bg-[#3E68FF] hover:text-white'
                        }
                      `}
                      title={bookmarkedPlaces.has(place.id) ? '북마크 해제' : '북마크 추가'}
                    >
                      <svg className="w-4 h-4" fill={bookmarkedPlaces.has(place.id) ? "currentColor" : "none"} stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                      </svg>
                    </button>

                    {/* 일정 추가 버튼 */}
                    <button
                      onClick={() => handleAddToItinerary(place)}
                      className={`
                        px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
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
                if (!loadingMore) {
                  const cityName = attraction?.city?.name || '전국'
                  const region = attraction?.region || '전국'
                  loadMoreAttractions(cityName, region, currentPage + 1, false)
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
          ) : (
            <div className="bg-[#0F1A31]/30 rounded-xl p-4 text-center">
              <div className="text-[#3E68FF] text-sm mb-1">✨</div>
              <p className="text-[#94A9C9] text-sm">개인화 추천 알고리즘이 적용된 장소들입니다</p>
              <p className="text-[#6FA0E6] text-xs mt-1">취향에 맞는 {filteredPlaces.length}개 장소를 추천해드려요!</p>
            </div>
          )}
        </div>
      )}

        {/* Selected Places Summary */}
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
      </div>

      {/* Fixed Bottom Button - Create Itinerary */}
      <div className="absolute bottom-16 left-0 right-0 bg-[#0B1220] p-4 z-10">
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

      <BottomNavigation />
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