// 이미 추천 알고리즘으로 선별된 데이터라고 가정
export interface Attraction {
  id: string
  name: string
  description: string
  imageUrl: string
  rating: number
  category: 'accommodation' | 'huanities' | 'leisure_sport' | 'nature' | 'restaurants' | 'shopping'
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
    console.error('API 호출 오류:', error)
    // API 오류 시 빈 데이터 반환
    return { data: [], hasMore: false }
  }
}