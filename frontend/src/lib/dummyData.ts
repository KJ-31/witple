// 이미 추천 알고리즘으로 선별된 데이터라고 가정
export interface Attraction {
  id: string
  name: string
  description: string
  imageUrl: string
  rating: number
  category: 'accommodation' | 'humanities' | 'leisure_sport' | 'nature' | 'restaurants' | 'shopping'
}

export interface CitySection {
  id: string
  cityName: string
  description: string
  region: string
  attractions: Attraction[]
  recommendationScore: number // 추천 점수 (높을수록 상위 노출)
  categorySections?: CategorySection[] // 카테고리별 섹션 (새로운 구조)
}

export interface CategorySection {
  category: string
  categoryName: string
  attractions: Attraction[]
  total: number
}

// 토큰을 가져오는 함수 (Next-auth에서 사용)
const getAuthToken = async (): Promise<string | null> => {
  try {
    if (typeof window === 'undefined') return null // SSR 체크
    
    // Next-auth 세션에서 토큰 가져오기
    const { getSession } = await import('next-auth/react')
    const session = await getSession()
    
    if (session && (session as any).backendToken) {
      return (session as any).backendToken
    }
    
    // fallback: localStorage에서 토큰을 가져오기
    const token = localStorage.getItem('access_token')
    return token
  } catch (error) {
    console.error('토큰 가져오기 오류:', error)
    return null
  }
}

// 실제 백엔드 추천 API에서 데이터 가져오기
export const fetchRecommendations = async (
  limit: number = 30  // 3개 섹션 × 10개 카드
): Promise<{ data: any[], hasMore: boolean }> => {
  try {
    // 직접 localhost:8000으로 호출해보기 (개발환경)
    const API_BASE_URL = 'http://localhost:8000'
    
    // 인증 토큰 가져오기
    const token = await getAuthToken()
    
    // 헤더 설정
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'accept': 'application/json',
    }
    
    // 토큰이 있으면 Authorization 헤더 추가
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    const url = `${API_BASE_URL}/api/v1/recommendations/mixed?limit=${limit}`
    
    const response = await fetch(url, {
      method: 'GET',
      headers
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`)
    }
    
    const recommendations = await response.json()
    
    // 디버깅: 백엔드에서 받은 데이터 확인 (제거)
    // console.log('백엔드 추천 데이터 샘플:', recommendations.slice(0, 3))
    
    // 추천 데이터를 CitySection 형태로 변환
    const transformedData = transformRecommendationsToSections(recommendations)
    
    return {
      data: transformedData,
      hasMore: false // 현재는 페이지네이션 없음
    }
  } catch (error) {
    console.error('추천 API 호출 오류:', error)
    // API 오류 시 fallback으로 기존 API 시도
    return await fetchRecommendedCitiesFallback()
  }
}

// 추천 데이터를 CitySection 형태로 변환하는 함수
const transformRecommendationsToSections = (recommendations: any[]): CitySection[] => {
  if (!recommendations || recommendations.length === 0) {
    return []
  }
  
  const MAX_SECTIONS = 3 // 최대 3개 섹션만 생성
  const MIN_ITEMS_PER_SECTION = 5 // 섹션당 최소 5개 아이템
  
  // 지역별로 그룹핑
  const regionGroups: { [key: string]: any[] } = {}
  recommendations.forEach(place => {
    const region = place.region || '기타'
    if (!regionGroups[region]) {
      regionGroups[region] = []
    }
    regionGroups[region].push(place)
  })
  
  // 지역별 그룹을 섹션으로 변환
  const sections: CitySection[] = []
  const sortedRegions = Object.entries(regionGroups)
    .sort(([,a], [,b]) => b.length - a.length) // 아이템 개수가 많은 지역 순으로 정렬
  
  for (const [region, places] of sortedRegions) {
    if (sections.length >= MAX_SECTIONS) break
    if (places.length < MIN_ITEMS_PER_SECTION) continue // 너무 적은 아이템은 제외
    
    // 최대 10개까지만 가져오기
    const sectionPlaces = places.slice(0, 10)
    
    const attractions: Attraction[] = sectionPlaces.map(place => ({
      id: place.place_id?.toString() || `${place.name}-${Math.random()}`,
      name: place.name || '이름 없음',
      description: place.description || '설명 없음',
      imageUrl: '', // 이미지는 현재 없음
      rating: 4.5, // 기본 평점
      category: getCategoryFromTableName(place.table_name)
    }))
    
    const firstPlace = sectionPlaces[0]
    const sectionIndex = sections.length
    
    sections.push({
      id: `section-${sectionIndex}`,
      cityName: region,
      description: firstPlace.recommendation_type === 'personalized' ? '맞춤 추천 여행지' : '인기 여행지',
      region: region,
      attractions,
      recommendationScore: Math.round((firstPlace.similarity_score || 0.8) * 100)
    })
  }
  
  // 섹션이 부족한 경우 남은 장소들로 혼합 섹션 생성
  if (sections.length < MAX_SECTIONS) {
    const usedPlaces = new Set()
    sections.forEach(section => {
      section.attractions.forEach(attraction => {
        usedPlaces.add(attraction.id)
      })
    })
    
    const remainingPlaces = recommendations.filter(place => 
      !usedPlaces.has(place.place_id?.toString() || `${place.name}-${Math.random()}`)
    )
    
    if (remainingPlaces.length > 0) {
      const mixedPlaces = remainingPlaces.slice(0, 10)
      const attractions: Attraction[] = mixedPlaces.map(place => ({
        id: place.place_id?.toString() || `${place.name}-${Math.random()}`,
        name: place.name || '이름 없음',
        description: place.description || '설명 없음',
        imageUrl: '', // 이미지는 현재 없음
        rating: 4.5, // 기본 평점
        category: getCategoryFromTableName(place.table_name)
      }))
      
      sections.push({
        id: `section-mixed`,
        cityName: '추천 여행지',
        description: '다양한 지역 추천',
        region: '전국',
        attractions,
        recommendationScore: 80
      })
    }
  }
  
  return sections
}

// 테이블명을 카테고리로 변환
const getCategoryFromTableName = (tableName: string): 'accommodation' | 'humanities' | 'leisure_sport' | 'nature' | 'restaurants' | 'shopping' => {
  const categoryMap: { [key: string]: 'accommodation' | 'humanities' | 'leisure_sport' | 'nature' | 'restaurants' | 'shopping' } = {
    accommodation: 'accommodation',
    humanities: 'humanities',
    leisure_sports: 'leisure_sport',
    nature: 'nature',
    restaurants: 'restaurants',
    shopping: 'shopping'
  }
  return categoryMap[tableName] || 'nature'
}

// 기존 API (fallback용)
const fetchRecommendedCitiesFallback = async (
  page: number = 0,
  limit: number = 3
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
    const response = await fetch(`${API_BASE_URL}/api/v1/attractions/cities?page=${page}&limit=${limit}`)
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const result = await response.json()
    
    return {
      data: result.data,
      hasMore: result.hasMore
    }
  } catch (error) {
    console.error('Fallback API 호출 오류:', error)
    return { data: [], hasMore: false }
  }
}

// 지역별 카테고리별 구분된 데이터 가져오기
export const fetchCitiesByCategory = async (
  page: number = 0,
  limit: number = 3
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
    const response = await fetch(`${API_BASE_URL}/api/v1/attractions/cities-by-category?page=${page}&limit=${limit}`)
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const result = await response.json()
    
    return {
      data: result.data,
      hasMore: result.hasMore
    }
  } catch (error) {
    console.error('API 호출 오류:', error)
    return { data: [], hasMore: false }
  }
}