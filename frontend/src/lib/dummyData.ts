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

// 401 Unauthorized 에러 시 자동 로그아웃 처리
const handleAuthError = async (response: Response) => {
  if (response.status === 401) {
    console.warn('토큰 만료 또는 인증 실패, 자동 로그아웃 처리')
    
    try {
      // Next-auth 로그아웃
      const { signOut } = await import('next-auth/react')
      await signOut({ redirect: false })
      
      // 로컬 스토리지 클리어
      localStorage.removeItem('access_token')
      localStorage.removeItem('preferences_completed')
      
      // 로그인 페이지로 리다이렉트
      if (typeof window !== 'undefined') {
        window.location.href = '/auth/signin'
      }
    } catch (error) {
      console.error('로그아웃 처리 중 오류:', error)
    }
  }
}

// 실제 백엔드 추천 API에서 데이터 가져오기 (강화된 에러 처리)
export const fetchRecommendations = async (
  limit: number = 60  // 더 많은 데이터로 안정적인 섹션 생성
): Promise<{ data: any[], hasMore: boolean }> => {
  try {
    // Docker 환경에서는 프록시 사용, 개발환경에서는 localhost 사용
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
    
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
    
    const url = `${API_BASE_URL}/proxy/api/v1/recommendations/mixed?limit=${limit}`
    
    // 3초 타임아웃으로 빠른 실패 처리
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('추천 API 요청 타임아웃')), 3000)
    )

    const fetchPromise = fetch(url, {
      method: 'GET',
      headers
    })
    
    const response = await Promise.race([fetchPromise, timeoutPromise]) as Response
    
    if (!response.ok) {
      let errorMessage = ''
      try {
        const errorText = await response.text()
        errorMessage = errorText
      } catch (textError) {
        errorMessage = `HTTP ${response.status} 오류`
      }
      
      console.warn(`추천 API HTTP 오류 (${response.status}):`, errorMessage)
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorMessage}`)
    }
    
    let recommendations
    try {
      recommendations = await response.json()
    } catch (jsonError) {
      console.error('추천 API 응답 JSON 파싱 오류:', jsonError)
      throw new Error('API 응답 데이터 형식 오류')
    }
    
    // 추천 데이터를 CitySection 형태로 변환
    const transformedData = transformRecommendationsToSections(recommendations)
    
    return {
      data: transformedData,
      hasMore: false // 현재는 페이지네이션 없음
    }
  } catch (error) {
    console.warn('추천 API 호출 전체 오류:', error instanceof Error ? error.message : String(error))
    // API 오류 시 fallback으로 기존 API 시도
    try {
      return await fetchRecommendedCitiesFallback()
    } catch (fallbackError) {
      console.warn('Fallback API도 실패:', fallbackError)
      // 모든 API가 실패한 경우 빈 배열 반환
      return { data: [], hasMore: false }
    }
  }
}

// 추천 데이터를 CitySection 형태로 변환하는 함수
const transformRecommendationsToSections = (recommendations: any[]): CitySection[] => {
  if (!recommendations || recommendations.length === 0) {
    return []
  }
  
  const MAX_SECTIONS = 5 // 최대 5개 섹션으로 증가
  const MIN_ITEMS_PER_SECTION = 1 // 섹션당 최소 1개 아이템으로 완화
  
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
    
    // 최대 6개까지만 가져오기 (더 많은 지역 섹션을 위해)
    const sectionPlaces = places.slice(0, 6)
    
    const attractions: Attraction[] = sectionPlaces.map(place => ({
      id: `${place.table_name}_${place.place_id}`, // 테이블명과 ID를 조합
      name: place.name || '이름 없음',
      description: place.description || '설명 없음',
      imageUrl: getImageUrl(place.image_urls), // 이미지 URL 추출
      rating: Math.round((place.similarity_score + 0.3) * 5 * 10) / 10, // 점수 기반 평점
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
      const mixedPlaces = remainingPlaces.slice(0, 6)
      const attractions: Attraction[] = mixedPlaces.map(place => ({
        id: `${place.table_name}_${place.place_id}`, // 테이블명과 ID를 조합
        name: place.name || '이름 없음',
        description: place.description || '설명 없음',
        imageUrl: getImageUrl(place.image_urls), // 이미지 URL 추출
        rating: Math.round((place.similarity_score + 0.3) * 5 * 10) / 10, // 점수 기반 평점
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
};

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

// 기존 API (fallback용) - 강화된 에러 처리
const fetchRecommendedCitiesFallback = async (
  page: number = 0,
  limit: number = 3
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
    
    // 2초 타임아웃 설정
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Fallback API 타임아웃')), 2000)
    )

    const fetchPromise = fetch(`${API_BASE_URL}/api/v1/attractions/cities?page=${page}&limit=${limit}`)
    const response = await Promise.race([fetchPromise, timeoutPromise]) as Response
    
    if (!response.ok) {
      let errorMessage = ''
      try {
        const errorText = await response.text()
        errorMessage = errorText
      } catch (textError) {
        errorMessage = `HTTP ${response.status} 오류`
      }
      console.warn(`Fallback API HTTP 오류 (${response.status}):`, errorMessage)
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    let result
    try {
      result = await response.json()
    } catch (jsonError) {
      console.error('Fallback API 응답 JSON 파싱 오류:', jsonError)
      throw new Error('Fallback API 응답 데이터 형식 오류')
    }
    
    return {
      data: result.data || [],
      hasMore: result.hasMore || false
    }
  } catch (error) {
    console.warn('Fallback API 호출 오류:', error instanceof Error ? error.message : String(error))
    return { data: [], hasMore: false }
  }
}

// 개인화된 지역별 카테고리 추천 데이터 가져오기 (강화된 에러 처리)
export const fetchPersonalizedRegionCategories = async (
  limit: number = 5
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    // Docker 환경에서는 프록시 사용, 개발환경에서는 localhost 사용
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
    
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
    
    const url = `${API_BASE_URL}/api/v1/recommendations/personalized-regions?limit=${limit}`
    
    console.log('개인화 추천 API 호출:', url)
    
    // 10초 타임아웃으로 충분한 시간 제공 (벡터 계산 시간 고려)
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('개인화 추천 API 타임아웃')), 10000)
    )

    const fetchPromise = fetch(url, {
      method: 'GET',
      headers
    })
    
    const response = await Promise.race([fetchPromise, timeoutPromise]) as Response
    console.log('개인화 추천 API 응답 상태:', response.status)
    
    if (!response.ok) {
      // 401 에러 시 자동 로그아웃 처리
      await handleAuthError(response)
      
      let errorMessage = ''
      try {
        const errorText = await response.text()
        errorMessage = errorText
      } catch (textError) {
        errorMessage = `HTTP ${response.status} 오류`
      }
      
      console.warn(`개인화 추천 API 오류 (${response.status}): 백엔드 서버 문제`, errorMessage)
      console.log('개인화 추천 실패, 기본 추천으로 fallback')
      return await fetchCitiesByCategory(0, limit)
    }
    
    let result
    try {
      result = await response.json()
      console.log('개인화 추천 결과:', result)
    } catch (jsonError) {
      console.warn('개인화 추천 API 응답 JSON 파싱 오류:', jsonError)
      console.log('JSON 파싱 실패, 기본 추천으로 fallback')
      return await fetchCitiesByCategory(0, limit)
    }
    
    // 데이터가 비어있거나 잘못된 형식이면 fallback
    if (!result || !result.data || !Array.isArray(result.data) || result.data.length === 0) {
      console.log('개인화 추천 데이터가 비어있음, 기본 추천으로 fallback')
      return await fetchCitiesByCategory(0, limit)
    }
    
    return {
      data: result.data,
      hasMore: result.hasMore || false
    }
  } catch (error) {
    console.warn('개인화 지역별 카테고리 추천 API 호출 전체 오류:', error instanceof Error ? error.message : String(error))
    
    // 에러 시 fallback으로 기본 추천 사용
    try {
      console.log('에러 fallback으로 기본 추천 API 시도')
      return await fetchCitiesByCategory(0, limit)
    } catch (fallbackError) {
      console.warn('Fallback API도 실패:', fallbackError)
      return {
        data: [],
        hasMore: false
      }
    }
  }
}

// 지역별 카테고리별 구분된 데이터 가져오기 (강화된 에러 처리)
export const fetchCitiesByCategory = async (
  page: number = 0,
  limit: number = 3
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
    
    // 2초 타임아웃 설정
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('기본 추천 API 타임아웃')), 2000)
    )

    const fetchPromise = fetch(`${API_BASE_URL}/api/v1/attractions/cities-by-category?page=${page}&limit=${limit}`)
    const response = await Promise.race([fetchPromise, timeoutPromise]) as Response
    
    if (!response.ok) {
      let errorMessage = ''
      try {
        const errorText = await response.text()
        errorMessage = errorText
      } catch (textError) {
        errorMessage = `HTTP ${response.status} 오류`
      }
      console.warn(`기본 추천 API HTTP 오류 (${response.status}):`, errorMessage)
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    let result
    try {
      result = await response.json()
    } catch (jsonError) {
      console.error('기본 추천 API 응답 JSON 파싱 오류:', jsonError)
      throw new Error('기본 추천 API 응답 데이터 형식 오류')
    }
    
    return {
      data: result.data || [],
      hasMore: result.hasMore || false
    }
  } catch (error) {
    console.warn('기본 추천 API 호출 오류:', error instanceof Error ? error.message : String(error))
    return { data: [], hasMore: false }
  }
}