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
}

// 실제 백엔드 API에서 데이터 가져오기
export const fetchRecommendedCities = async (
  page: number = 0,
  limit: number = 3
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    // 환경 변수에서 API URL을 가져오거나 기본값 사용
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
    // NextAuth 세션 확인
    let isLoggedIn = false
    let token = null
    
    if (typeof window !== 'undefined') {
      try {
        const { getSession } = await import('next-auth/react')
        const session = await getSession()
        isLoggedIn = !!session?.user
      } catch (e) {
        // NextAuth 실패 시 localStorage 토큰 확인
        token = localStorage.getItem('token')
        isLoggedIn = !!token
      }
    }
    
    // 로그인 상태에 따라 다른 엔드포인트 호출
    const endpoint = isLoggedIn ? 
      `${API_BASE_URL}/api/v1/recommendations/mixed?limit=${limit * 4}` :
      'dummy'  // 로그인 전에는 더미 데이터 사용
    
    if (endpoint === 'dummy') {
      // 로그인 전: 더미 데이터 사용
      const startIndex = page * limit
      const endIndex = startIndex + limit
      const dummyData = RECOMMENDED_CITY_SECTIONS.slice(startIndex, endIndex)
      return { 
        data: dummyData, 
        hasMore: endIndex < RECOMMENDED_CITY_SECTIONS.length 
      }
    }
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    }
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    const response = await fetch(endpoint, { headers })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const places = await response.json()
    
    // 추천 API 응답을 CitySection 형태로 변환
    const citySections = transformPlacesToCitySections(places, page, limit)
    
    return {
      data: citySections,
      hasMore: citySections.length === limit
    }
  } catch (error) {
    console.error('추천 API 호출 오류:', error)
    // API 오류 시 더미 데이터 반환
    const startIndex = page * limit
    const endIndex = startIndex + limit
    const dummyData = RECOMMENDED_CITY_SECTIONS.slice(startIndex, endIndex)
    
    return { 
      data: dummyData, 
      hasMore: endIndex < RECOMMENDED_CITY_SECTIONS.length 
    }
  }
}

// 백엔드 추천 API 응답을 프론트엔드 CitySection 형태로 변환
const transformPlacesToCitySections = (places: any[], page: number, limit: number): CitySection[] => {
  if (!places || places.length === 0) {
    return []
  }

  // 지역별로 그룹화
  const regionGroups: { [key: string]: any[] } = {}
  
  places.forEach((place) => {
    const region = place.region || '기타'
    if (!regionGroups[region]) {
      regionGroups[region] = []
    }
    regionGroups[region].push(place)
  })
  
  // 각 지역을 CitySection으로 변환
  const citySections: CitySection[] = []
  
  Object.entries(regionGroups).forEach(([region, regionPlaces]) => {
    if (regionPlaces.length > 0) {
      const attractions: Attraction[] = regionPlaces.slice(0, 6).map((place) => {
        // 실제 이미지 URL 가져오기
        let imageUrl = '/images/default-attraction.jpg'
        if (place.image_urls && Array.isArray(place.image_urls) && place.image_urls.length > 0) {
          imageUrl = place.image_urls[0]
        }
        
        return {
          id: `${place.table_name}-${place.place_id}`,
          name: place.name || place.real_name || '이름 없음',
          description: place.description || place.overview || '추천 여행지',
          imageUrl: imageUrl,
          rating: Math.min(4.0 + (place.similarity_score || place.popularity_score || 0) * 1.0, 5.0),
          category: mapTableToCategory(place.table_name)
        }
      })
      
      // 추천 타입에 따른 설명
      const hasPersonalized = regionPlaces.some(p => p.recommendation_type === 'personalized')
      const description = hasPersonalized ? 
        '당신을 위한 맞춤 추천' : '인기 여행지'
      
      const avgScore = regionPlaces.reduce((acc, p) => 
        acc + (p.similarity_score || p.popularity_score || 0), 0) / regionPlaces.length
      
      citySections.push({
        id: `${region.toLowerCase().replace(/\s+/g, '-')}-${Date.now()}`,
        cityName: region,
        description: description,
        region: region,
        attractions: attractions,
        recommendationScore: Math.round(avgScore * 100)
      })
    }
  })
  
  // 점수 순으로 정렬
  citySections.sort((a, b) => b.recommendationScore - a.recommendationScore)
  
  // 페이지네이션 적용
  const startIndex = page * limit
  return citySections.slice(startIndex, startIndex + limit)
}

// 테이블명을 카테고리로 매핑
const mapTableToCategory = (tableName: string): 'tourist' | 'food' | 'culture' | 'nature' | 'shopping' => {
  switch (tableName) {
    case 'restaurants': return 'food'
    case 'accommodation': return 'tourist'
    case 'humanities': return 'culture'
    case 'nature': return 'nature'
    case 'shopping': return 'shopping'
    case 'leisure_sports': return 'nature'
    default: return 'tourist'
  }
}