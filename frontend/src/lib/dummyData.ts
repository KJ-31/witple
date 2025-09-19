// 이미 추천 알고리즘으로 선별된 데이터라고 가정
export interface Attraction {
  id: string
  name: string
  description: string
  imageUrl: string
  rating: number
  category: 'accommodation' | 'humanities' | 'leisure_sports' | 'nature' | 'restaurants' | 'shopping'
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

// 백엔드에서 추천 설정을 가져오는 함수
const getRecommendationConfig = async (): Promise<any> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
    const response = await fetch(`${API_BASE_URL}/api/v2/recommendations/config`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })

    if (response.ok) {
      const config = await response.json()
      // console.log('백엔드 추천 설정 로드:', config)
      return config
    }
  } catch (error) {
    console.warn('백엔드 설정 로드 실패:', error)
  }

  // 기본값 반환
  return {
    mainPage: { sectionCount: 3, itemsPerSection: 8, totalRecommendations: 24 },
    userBased: {
      newUser: { sectionCount: 2, itemsPerSection: 6 },
      activeUser: { sectionCount: 3, itemsPerSection: 8 },
      premiumUser: { sectionCount: 4, itemsPerSection: 10 }
    }
  }
}

// 사용자 타입 분류
export const getUserType = (userInfo?: any, session?: any): 'newUser' | 'activeUser' | 'premiumUser' | 'guest' => {
  if (!session) return 'guest'

  if (userInfo?.isNewUser || (userInfo?.bookmarkCount !== undefined && userInfo.bookmarkCount <= 3)) {
    return 'newUser'
  }

  if (userInfo?.isPremium || userInfo?.subscription === 'premium') {
    return 'premiumUser'
  }

  return 'activeUser'
}

// 추천 설정 계산 (백엔드 config 구조에 맞게 수정)
const calculateRecommendationSettings = (userType: string, config: any) => {
  try {
    // 백엔드 config가 없거나 잘못된 경우 기본값 반환
    if (!config) {
      console.warn('백엔드 config가 없음, 기본값 사용')
      return userType === 'guest'
        ? { sectionCount: 2, itemsPerSection: 6, totalRecommendations: 12 }
        : { sectionCount: 3, itemsPerSection: 8, totalRecommendations: 24 }
    }

    // 백엔드 config 구조 분석
    // console.log('백엔드 config 분석:', {
    //   regions: config.explore_regions?.length || 0,
    //   categories: config.explore_categories?.length || 0,
    //   maxRequests: config.max_parallel_requests || 0,
    //   weights: config.weights
    // })

    // 백엔드 성능 설정을 고려한 동적 계산
    const maxRegions = Math.min(config.explore_regions?.length || 17, config.max_parallel_requests || 8)
    const maxCategories = Math.min(config.explore_categories?.length || 6, 4)

  if (userType === 'guest') {
    // 비로그인: 성능을 고려한 적당한 추천
    const sectionCount = Math.min(2, Math.floor(maxRegions / 2))
    return {
      sectionCount: Math.max(1, sectionCount),
      itemsPerSection: 6,
      totalRecommendations: Math.max(6, sectionCount * 6)
    }
  }

  if (userType === 'newUser') {
    // 신규 사용자: 적당한 추천으로 시작
    const sectionCount = Math.min(2, Math.floor(maxRegions / 3))
    return {
      sectionCount: Math.max(1, sectionCount),
      itemsPerSection: 6,
      totalRecommendations: Math.max(6, sectionCount * 6)
    }
  }

  if (userType === 'premiumUser') {
    // 프리미엄: 백엔드 성능 한계 내에서 최대 추천
    const sectionCount = Math.min(4, Math.floor(maxRegions * 0.8))
    const itemsPerSection = Math.min(10, maxCategories + 4)
    return {
      sectionCount: Math.max(2, sectionCount),
      itemsPerSection,
      totalRecommendations: sectionCount * itemsPerSection
    }
  }

  // 일반 사용자 (activeUser): 카드 수 증가
  const sectionCount = Math.min(4, Math.floor(maxRegions * 0.6))  // 3 → 4섹션으로 증가
  const itemsPerSection = Math.min(10, maxCategories + 4)  // 8 → 10개로 증가
  return {
    sectionCount: Math.max(3, sectionCount),  // 최소 3섹션 보장
    itemsPerSection,
    totalRecommendations: sectionCount * itemsPerSection  // 40개로 증가 (기존 24개에서)
  }
  } catch (error) {
    console.error('설정 계산 중 오류:', error)
    // 에러 발생 시 안전한 기본값 반환
    return userType === 'guest'
      ? { sectionCount: 2, itemsPerSection: 6, totalRecommendations: 12 }
      : { sectionCount: 3, itemsPerSection: 8, totalRecommendations: 24 }
  }
}

// 토큰을 가져오는 함수 (Next-auth에서 사용)
const getAuthToken = async (): Promise<string | null> => {
  try {
    if (typeof window === 'undefined') return null // SSR 체크

    // Next-auth 세션에서 토큰 가져오기
    const { getSession } = await import('next-auth/react')
    const session = await getSession()

    console.log('🔍 세션 상태 확인:', {
      hasSession: !!session,
      hasBackendToken: !!(session as any)?.backendToken,
      userEmail: session?.user?.email
    })

    if (session && (session as any).backendToken) {
      console.log('✅ Next-auth에서 백엔드 토큰 획득')
      console.log('🔍 백엔드 토큰 길이:', (session as any).backendToken.length)
      return (session as any).backendToken
    }

    // fallback: localStorage에서 토큰을 가져오기
    const token = localStorage.getItem('access_token')
    if (token) {
      console.log('✅ localStorage에서 토큰 획득')
      return token
    }

    console.warn('❌ 토큰을 찾을 수 없음')
    return null
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

// ✅ v2 추천 시스템 API 사용 (새로운 함수) - 동적 설정 지원
export const fetchRecommendations = async (
  limit: number = 21,  // v2 API는 featured 1개 + feed 20개
  maxSections: number = 5, // 최대 섹션 수
  maxItemsPerSection: number = 6, // 섹션당 최대 아이템 수
  region?: string // 지역 필터
): Promise<{ data: any[], hasMore: boolean }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

    // 인증 토큰 가져오기
    console.log('🔍 토큰 가져오기 시작')
    const token = await getAuthToken()
    console.log('🔍 토큰 가져오기 결과:', !!token)

    // 헤더 설정
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'accept': 'application/json',
    }

    // 토큰이 있으면 Authorization 헤더 추가
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
      console.log('🔐 JWT 토큰 포함하여 API 호출:', token.substring(0, 20) + '...')
      console.log('🔍 실제 토큰 길이:', token.length)
      console.log('🔍 토큰 전체:', token) // 디버깅용 - 나중에 제거
    } else {
      console.warn('⚠️ JWT 토큰이 없어 비로그인 상태로 API 호출')
    }

    // v2 추천 시스템 API 사용
    const params = new URLSearchParams({ limit: limit.toString() })
    if (region) {
      params.append('region', region)
    }

    const url = `${API_BASE_URL}/api/v2/recommendations/main-feed/personalized?${params.toString()}`
    console.log('v2 추천 API 호출:', url)

    // 3초 타임아웃으로 빠른 실패 처리
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('v2 추천 API 요청 타임아웃')), 3000)
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

      console.warn(`v2 추천 API HTTP 오류 (${response.status}):`, errorMessage)
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorMessage}`)
    }

    let recommendations
    try {
      recommendations = await response.json()
      console.log('🎯 v2 API 응답 (우선순위 태그 확인):', {
        featured: recommendations.featured?.table_name,
        feedCategories: recommendations.feed?.map((item: any) => item.table_name).slice(0, 5),
        totalCount: recommendations.total_count
      })
    } catch (jsonError) {
      console.error('v2 추천 API 응답 JSON 파싱 오류:', jsonError)
      throw new Error('v2 API 응답 데이터 형식 오류')
    }

    // v2 API 응답 형식 처리 { featured, feed, total_count }
    let transformedData: CitySection[] = []

    if (recommendations && typeof recommendations === 'object') {
      if (recommendations.featured || recommendations.feed) {
        // v2 personalized feed 응답 처리
        const allItems = []
        if (recommendations.featured) allItems.push(recommendations.featured)
        if (recommendations.feed && Array.isArray(recommendations.feed)) {
          allItems.push(...recommendations.feed)
        }


        console.log('v2 API 응답 아이템 수:', allItems.length)
        transformedData = transformRecommendationsToSections(allItems, maxSections, maxItemsPerSection)
        console.log('변환된 섹션 데이터:', transformedData)
      } else {
        console.warn('v2 API 응답 형식이 예상과 다름:', Object.keys(recommendations))
        return { data: [], hasMore: false }
      }
    } else {
      console.warn('v2 API 응답이 객체가 아님:', typeof recommendations)
      return { data: [], hasMore: false }
    }

    return {
      data: transformedData,
      hasMore: false // v2 API는 페이지네이션 없음
    }
  } catch (error) {
    console.error('v2 추천 API 호출 오류:', error instanceof Error ? error.message : String(error))
    // v2 API 실패 시 탐색 피드로 fallback
    try {
      // console.log('v2 탐색 피드로 fallback 시도')
      return await fetchV2ExploreFeedWithCategories(maxSections, maxItemsPerSection)
    } catch (fallbackError) {
      console.warn('v2 탐색 피드도 실패:', fallbackError)
      return { data: [], hasMore: false }
    }
  }
}

// v2 탐색 피드 API 호출 (비로그인 사용자용 - 카테고리별 구조)
const fetchV2ExploreFeedWithCategories = async (
  maxSections: number = 3,
  maxItemsPerSection: number = 6
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'accept': 'application/json',
    }

    const url = `${API_BASE_URL}/api/v2/recommendations/main-feed/explore`
    // console.log('v2 탐색 피드 API 호출 (카테고리별):', url)

    const response = await fetch(url, { headers })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const result = await response.json()

    // v2 탐색 피드 응답 처리 { data: { region: { category: [items] } } }
    if (result && result.data) {
      const sections: CitySection[] = []
      const regions = Object.keys(result.data).slice(0, maxSections) // 지역 수 제한

      for (const region of regions) {
        const categories = result.data[region]
        const categorySections: CategorySection[] = []

        // 각 카테고리별로 데이터 구성
        Object.entries(categories).forEach(([category, items]: [string, any]) => {
          if (Array.isArray(items) && items.length > 0) {
            const attractions: Attraction[] = items.slice(0, maxItemsPerSection).map(item => ({
              id: item.id || `${item.table_name}_${item.place_id}`,
              name: item.name || '이름 없음',
              description: item.description || '설명 없음',
              imageUrl: getImageUrl(item.image_urls),
              rating: 4.5,
              category: getCategoryFromTableName(item.table_name || category)
            }))

            categorySections.push({
              category: category,
              categoryName: getCategoryDisplayName(category),
              attractions: attractions,
              total: items.length
            })
          }
        })

        // 카테고리별 섹션이 있는 경우만 추가
        if (categorySections.length > 0) {
          sections.push({
            id: `explore-${region}`,
            cityName: region,
            description: `${region} 지역 추천`,
            region: region,
            attractions: [], // categorySections 사용하므로 비워둠
            categorySections: categorySections,
            recommendationScore: 80
          })
        }
      }

      // console.log(`v2 탐색 피드 완료: ${sections.length}개 지역, 카테고리별 구조`)
      return { data: sections, hasMore: false }
    }

    return { data: [], hasMore: false }
  } catch (error) {
    console.error('v2 탐색 피드 호출 오류:', error)
    return { data: [], hasMore: false }
  }
}

// bookmark_cnt 기반 인기 장소 조회 함수 (비로그인 사용자용)
const fetchPopularPlacesByBookmarks = async (
  maxSections: number = 3,
  maxItemsPerSection: number = 8,
  region?: string
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'accept': 'application/json',
    }

    // bookmark_cnt 기준으로 정렬된 인기 장소 조회
    const params = new URLSearchParams({
      limit: (maxSections * maxItemsPerSection).toString()
    })

    if (region) {
      params.append('region', region)
    }

    const url = `${API_BASE_URL}/api/v2/recommendations/main-feed/personalized?${params.toString()}`
    // console.log('인기 장소 API 호출 (bookmark_cnt 기준):', url)

    const response = await fetch(url, { headers })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const result = await response.json()
    // console.log('v2 API 응답 (인기 장소):', result)

    // v2 API 응답 처리 { featured, feed, total_count }
    let allItems = []
    if (result && typeof result === 'object') {
      if (result.featured) allItems.push(result.featured)
      if (result.feed && Array.isArray(result.feed)) {
        allItems.push(...result.feed)
      }
    }

    if (allItems.length > 0) {
      // 지역별로 그룹화
      const regionGroups: { [key: string]: any[] } = {}

      allItems.forEach(item => {
        const region = item.region || '기타'
        if (!regionGroups[region]) {
          regionGroups[region] = []
        }
        regionGroups[region].push(item)
      })

      const sections: CitySection[] = []
      const regions = Object.keys(regionGroups).slice(0, maxSections)

      for (const region of regions) {
        const items = regionGroups[region].slice(0, maxItemsPerSection)

        const attractions: Attraction[] = items.map(item => ({
          id: item.id || `${item.table_name}_${item.place_id}`,
          name: item.name || '이름 없음',
          description: item.description || '설명 없음',
          imageUrl: getImageUrl(item.image_urls),
          rating: 4.5,
          category: getCategoryFromTableName(item.table_name || 'nature')
        }))

        if (attractions.length > 0) {
          sections.push({
            id: `popular-${region}`,
            cityName: region,
            description: `${region} 인기 명소`,
            region: region,
            attractions: attractions,
            recommendationScore: 90 // 인기도 기반이므로 높은 점수
          })
        }
      }

      // console.log(`북마크 기반 인기 장소 완료: ${sections.length}개 지역`)
      return { data: sections, hasMore: false }
    }

    return { data: [], hasMore: false }
  } catch (error) {
    console.error('인기 장소 조회 오류:', error)
    // 실패 시 기존 explore API로 fallback
    return await fetchV2ExploreFeedWithCategories(maxSections, maxItemsPerSection)
  }
}

// v2 탐색 피드 API 호출 (fallback용)
const fetchV2ExploreFeed = async (): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'accept': 'application/json',
    }

    const url = `${API_BASE_URL}/api/v2/recommendations/main-feed/explore`
    // console.log('v2 탐색 피드 API 호출:', url)

    const response = await fetch(url, { headers })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const result = await response.json()

    // v2 탐색 피드 응답 처리 { data: { region: { category: [items] } } }
    if (result && result.data) {
      const sections: CitySection[] = []

      Object.entries(result.data).forEach(([region, categories]: [string, any]) => {
        Object.entries(categories).forEach(([category, items]: [string, any]) => {
          if (Array.isArray(items) && items.length > 0) {
            const attractions: Attraction[] = items.map(item => ({
              id: item.id || `${item.table_name}_${item.place_id}`,
              name: item.name || '이름 없음',
              description: item.description || '설명 없음',
              imageUrl: getImageUrl(item.image_urls),
              rating: 4.5,
              category: getCategoryFromTableName(item.table_name || category)
            }))

            sections.push({
              id: `explore-${region}-${category}`,
              cityName: region,
              description: `${region} ${category}`,
              region: region,
              attractions: attractions.slice(0, 6),
              recommendationScore: 75
            })
          }
        })
      })

      return { data: sections.slice(0, 3), hasMore: false }
    }

    return { data: [], hasMore: false }
  } catch (error) {
    console.error('v2 탐색 피드 호출 오류:', error)
    return { data: [], hasMore: false }
  }
}

// 추천 데이터를 CitySection 형태로 변환하는 함수 (동적 설정 지원)
const transformRecommendationsToSections = (recommendations: any[], maxSections: number = 5, maxItemsPerSection: number = 6): CitySection[] => {
  if (!recommendations || recommendations.length === 0) {
    return []
  }

  console.log('🔄 Transform 시작 - 원본 추천 데이터:', recommendations.length, '개')
  console.log('🔄 원본 데이터 카테고리 분포:', recommendations.map(r => r.category || r.table_name))

  // 개인화 추천의 경우 지역별 그룹핑하지 않고 단일 섹션으로 처리
  const isPersonalized = recommendations.some(place => place.source === 'preference' || place.source === 'hybrid')

  if (isPersonalized) {
    console.log('🎯 개인화 추천 감지 - 지역별 그룹핑 없이 단일 섹션으로 처리')

    // 개인화 추천은 순서를 유지하면서 단일 섹션으로 생성
    const attractions: Attraction[] = recommendations.slice(0, maxItemsPerSection * maxSections).map(place => ({
      id: `${place.table_name}_${place.place_id}`,
      name: place.name || '이름 없음',
      description: place.description || '설명 없음',
      imageUrl: getImageUrl(place.image_urls),
      rating: Math.round((place.similarity_score + 0.3) * 5 * 10) / 10,
      category: normalizeCategoryName(place.category) || getCategoryFromTableName(place.table_name)
    }))

    console.log('🎯 변환된 개인화 추천:', attractions.map(a => `${a.name} (${a.category})`))

    return [{
      id: 'personalized-recommendations',
      cityName: '맞춤 추천',
      description: '당신을 위한 맞춤 추천 여행지',
      region: '전국',
      attractions,
      recommendationScore: 100
    }]
  }

  // 기존 지역별 그룹핑 로직 (비개인화 추천용)
  const regionGroups: { [key: string]: any[] } = {}
  recommendations.forEach(place => {
    const region = place.region || '기타'
    if (!regionGroups[region]) {
      regionGroups[region] = []
    }
    regionGroups[region].push(place)
  })

  const sections: CitySection[] = []
  const sortedRegions = Object.entries(regionGroups)
    .sort(([,a], [,b]) => b.length - a.length)

  for (const [region, places] of sortedRegions) {
    if (sections.length >= maxSections) break
    if (places.length < 1) continue

    const sectionPlaces = places.slice(0, maxItemsPerSection)

    const attractions: Attraction[] = sectionPlaces.map(place => ({
      id: `${place.table_name}_${place.place_id}`,
      name: place.name || '이름 없음',
      description: place.description || '설명 없음',
      imageUrl: getImageUrl(place.image_urls),
      rating: Math.round((place.similarity_score + 0.3) * 5 * 10) / 10,
      category: normalizeCategoryName(place.category) || getCategoryFromTableName(place.table_name)
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
  if (sections.length < maxSections) {
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
        category: normalizeCategoryName(place.category) || getCategoryFromTableName(place.table_name) // 백엔드 category 우선 사용
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
// 백엔드 카테고리 값을 프론트엔드 카테고리로 변환
const normalizeCategoryName = (backendCategory: string | undefined): 'accommodation' | 'humanities' | 'leisure_sports' | 'nature' | 'restaurants' | 'shopping' | undefined => {
  if (!backendCategory) return undefined

  const categoryMap: { [key: string]: 'accommodation' | 'humanities' | 'leisure_sports' | 'nature' | 'restaurants' | 'shopping' } = {
    accommodation: 'accommodation',
    restaurants: 'restaurants',
    shopping: 'shopping',
    nature: 'nature',
    culture: 'humanities',
    leisure: 'leisure_sports',
    humanities: 'humanities'
  }

  return categoryMap[backendCategory]
}

const getCategoryFromTableName = (tableName: string): 'accommodation' | 'humanities' | 'leisure_sports' | 'nature' | 'restaurants' | 'shopping' => {
  const categoryMap: { [key: string]: 'accommodation' | 'humanities' | 'leisure_sports' | 'nature' | 'restaurants' | 'shopping' } = {
    accommodation: 'accommodation',
    humanities: 'humanities',
    leisure_sports: 'leisure_sports',
    nature: 'nature',
    restaurants: 'restaurants',
    shopping: 'shopping'
  }
  return categoryMap[tableName] || 'nature'
}

// 카테고리 한국어 이름 반환
const getCategoryDisplayName = (category: string): string => {
  const categoryDisplayMap: { [key: string]: string } = {
    accommodation: '숙박',
    humanities: '인문',
    leisure_sports: '레저',
    nature: '자연',
    restaurants: '맛집',
    shopping: '쇼핑'
  }
  return categoryDisplayMap[category] || category
}

// 개별 지역/카테고리 섹션 API 호출 함수 (우선순위 태그 필터링 포함)
const fetchRegionCategorySection = async (
  region: string,
  category: string,
  limit: number = 10,
  headers: Record<string, string>
): Promise<Attraction[]> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
    // 🎯 개별 지역 섹션 API 사용 (우선순위 태그 필터링 적용됨)
    const url = `${API_BASE_URL}/api/v2/recommendations/explore/${encodeURIComponent(region)}/${category}?limit=${limit}`

    console.log(`🔧 개별 섹션 API 호출: ${region}/${category}`)

    const response = await fetch(url, { headers })

    if (!response.ok) {
      console.warn(`⚠️ 개별 섹션 API 실패: ${region}/${category} (${response.status})`)
      return []
    }

    const result = await response.json()

    if (result && result.data && Array.isArray(result.data)) {
      return result.data.map((item: any) => ({
        id: item.id || `${item.table_name}_${item.place_id}`,
        name: item.name || '이름 없음',
        description: item.description || '설명 없음',
        imageUrl: getImageUrl(item.image_urls),
        rating: 4.5,
        category: getCategoryFromTableName(item.table_name || category)
      }))
    }

    return []
  } catch (error) {
    console.error(`❌ 개별 섹션 API 오류: ${region}/${category}:`, error)
    return []
  }
}

// 모든 지역의 모든 카테고리 데이터를 가져오는 함수 (개별 API 호출 방식으로 변경)
export const fetchAllRegionsAllCategories = async (
  maxRegions: number = 10,
  maxItemsPerCategory: number = 6,
  session?: any  // 세션 매개변수 추가
): Promise<{ data: CitySection[], availableRegions: string[] }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'accept': 'application/json',
    }

    // 🔑 JWT 토큰 안정적 조회 (우선순위 태그 필터링을 위해 필요)
    const token = await getAuthToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
      console.log('🔐 JWT 토큰으로 개별 섹션 API 호출 (우선순위 태그 필터링 적용)')
    } else {
      console.log('🔓 비로그인 상태로 개별 섹션 API 호출 (일반 추천)')
    }

    // 백엔드 설정에서 사용 가능한 지역과 카테고리 가져오기
    const configResponse = await fetch(`${API_BASE_URL}/api/v2/recommendations/regions`, { headers })
    let availableRegions: string[] = []
    let availableCategories: string[] = []

    if (configResponse.ok) {
      const configData = await configResponse.json()
      availableRegions = configData.regions || []
      availableCategories = configData.categories || []
    }

    // 설정 로드 실패 시 기본값 사용
    if (availableRegions.length === 0) {
      availableRegions = ["서울특별시", "부산광역시", "제주특별자치도", "강원특별자치도", "경기도", "전라남도", "경상남도", "인천광역시"]
    }
    if (availableCategories.length === 0) {
      availableCategories = ["restaurants", "accommodation", "nature", "shopping", "culture", "activity"]
    }

    console.log(`🚀 개별 섹션 API 방식으로 데이터 로드: ${Math.min(maxRegions, availableRegions.length)}개 지역, ${availableCategories.length}개 카테고리`)

    const sections: CitySection[] = []
    const targetRegions = availableRegions.slice(0, maxRegions)

    // 🔄 각 지역별로 우선순위 태그 기반 추천 가져오기 (병렬 처리)
    const regionPromises = targetRegions.map(async (region) => {
      const allAttractions: Attraction[] = []

      // 각 카테고리별로 개별 API 호출 (사용자 우선순위 태그 필터링 적용됨)
      const categoryPromises = availableCategories.map(async (category) => {
        const attractions = await fetchRegionCategorySection(region, category, maxItemsPerCategory, headers)
        return { category, attractions }
      })

      const categoryResults = await Promise.all(categoryPromises)

      // 모든 카테고리의 결과를 합치기
      categoryResults.forEach(({ attractions }) => {
        allAttractions.push(...attractions)
      })

      if (allAttractions.length > 0) {
        return {
          id: `priority-filtered-${region}`,
          cityName: region,
          description: `${region} 우선순위 기반 추천 장소`,
          region: region,
          attractions: allAttractions,
          recommendationScore: 95 // 우선순위 필터링으로 높은 점수
        }
      }

      return null
    })

    const regionResults = await Promise.all(regionPromises)

    // null이 아닌 결과만 필터링
    regionResults.forEach(section => {
      if (section) {
        sections.push(section)
      }
    })

    console.log(`✅ 우선순위 태그 기반 지역 섹션 완료: ${sections.length}개 지역`)
    return { data: sections, availableRegions: targetRegions }

  } catch (error) {
    console.error('❌ 개별 섹션 API 방식 호출 오류:', error)
    return { data: [], availableRegions: [] }
  }
}



// 지역별 카테고리 인기순 섹션 API 호출 (필터 기능용)
export const fetchPopularSectionByRegion = async (
  region: string = '서울',
  maxCategories: number = 6,
  maxItemsPerCategory: number = 6
): Promise<{ data: CitySection | null, availableRegions: string[] }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'accept': 'application/json',
    }

    // v2 탐색 피드 API를 사용해서 인기순 데이터 가져오기
    const url = `${API_BASE_URL}/api/v2/recommendations/main-feed/explore`
    // console.log('지역별 인기순 섹션 API 호출:', url, 'region:', region)

    const response = await fetch(url, { headers })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const result = await response.json()

    if (result && result.data) {
      const availableRegions = Object.keys(result.data)

      // 요청한 지역이 없으면 첫 번째 지역 사용
      const targetRegion = result.data[region] ? region : availableRegions[0]
      const categories = result.data[targetRegion]

      if (!categories) {
        return { data: null, availableRegions }
      }

      // 카테고리를 북마크 수 기준으로 정렬
      const sortedCategories = Object.entries(categories)
        .filter(([, items]) => Array.isArray(items) && items.length > 0)
        .sort(([,a], [,b]) => {
          const aAvgBookmarks = Array.isArray(a) ? a.reduce((sum: number, item: any) => sum + (item.bookmark_cnt || 0), 0) / a.length : 0
          const bAvgBookmarks = Array.isArray(b) ? b.reduce((sum: number, item: any) => sum + (item.bookmark_cnt || 0), 0) / b.length : 0
          return bAvgBookmarks - aAvgBookmarks
        })
        .slice(0, maxCategories)

      // 카테고리별 섹션 생성
      const categorySections = sortedCategories.map(([categoryName, items]) => {
        // 북마크 수 기준으로 정렬해서 상위 아이템들만 선택
        const sortedItems = (items as any[]).sort((a: any, b: any) => (b.bookmark_cnt || 0) - (a.bookmark_cnt || 0))
        const topItems = sortedItems.slice(0, maxItemsPerCategory)

        const attractions: Attraction[] = topItems.map(item => ({
          id: item.id || `${item.table_name}_${item.place_id}`,
          name: item.name || '이름 없음',
          description: item.description || '설명 없음',
          imageUrl: getImageUrl(item.image_urls),
          rating: 4.5,
          category: getCategoryFromTableName(item.table_name || categoryName)
        }))

        return {
          category: categoryName,
          categoryName: getCategoryDisplayName(categoryName),
          attractions: attractions,
          total: attractions.length
        }
      })

      const citySection: CitySection = {
        id: `popular-${targetRegion}`,
        cityName: targetRegion,
        description: `${targetRegion} 인기 명소`,
        region: targetRegion,
        attractions: [],
        categorySections: categorySections,
        recommendationScore: 90
      }

      // console.log(`지역별 인기순 섹션 완료: ${targetRegion}, ${categorySections.length}개 카테고리`)
      return { data: citySection, availableRegions }
    }

    return { data: null, availableRegions: [] }
  } catch (error) {
    console.error('지역별 인기순 섹션 호출 오류:', error)
    return { data: null, availableRegions: [] }
  }
}

// 기존 신규 사용자를 위한 인기순 섹션 API 호출 (호환성 유지)
export const fetchPopularSectionsForNewUsers = async (
  maxSections: number = 2,
  maxItemsPerSection: number = 6
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'accept': 'application/json',
    }

    // v2 탐색 피드 API를 사용해서 인기순 데이터 가져오기
    const url = `${API_BASE_URL}/api/v2/recommendations/main-feed/explore`
    // console.log('신규 사용자 인기순 섹션 API 호출:', url)

    const response = await fetch(url, { headers })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const result = await response.json()

    if (result && result.data) {
      const sections: CitySection[] = []
      const regions = Object.keys(result.data).slice(0, maxSections)

      for (const region of regions) {
        const categories = result.data[region]

        // 각 지역에서 가장 인기 있는 카테고리들만 선택 (북마크 수 기준)
        const sortedCategories = Object.entries(categories).sort(([,a], [,b]) => {
          const aAvgBookmarks = Array.isArray(a) ? a.reduce((sum: number, item: any) => sum + (item.bookmark_cnt || 0), 0) / a.length : 0
          const bAvgBookmarks = Array.isArray(b) ? b.reduce((sum: number, item: any) => sum + (item.bookmark_cnt || 0), 0) / b.length : 0
          return bAvgBookmarks - aAvgBookmarks
        })

        const topCategory = sortedCategories[0]
        if (topCategory && Array.isArray(topCategory[1]) && topCategory[1].length > 0) {
          const [categoryName, items] = topCategory

          // 북마크 수 기준으로 정렬해서 상위 아이템들만 선택
          const sortedItems = items.sort((a: any, b: any) => (b.bookmark_cnt || 0) - (a.bookmark_cnt || 0))
          const topItems = sortedItems.slice(0, maxItemsPerSection)

          const attractions: Attraction[] = topItems.map(item => ({
            id: item.id || `${item.table_name}_${item.place_id}`,
            name: item.name || '이름 없음',
            description: item.description || '설명 없음',
            imageUrl: getImageUrl(item.image_urls),
            rating: 4.5,
            category: getCategoryFromTableName(item.table_name || categoryName)
          }))

          sections.push({
            id: `popular-${region}`,
            cityName: region,
            description: `${region} 인기 ${getCategoryDisplayName(categoryName)}`,
            region: region,
            attractions: attractions,
            categorySections: undefined,
            recommendationScore: 90 // 인기순이므로 높은 점수
          })
        }
      }

      // console.log(`신규 사용자 인기순 섹션 완료: ${sections.length}개 지역`)
      return { data: sections, hasMore: false }
    }

    return { data: [], hasMore: false }
  } catch (error) {
    console.error('신규 사용자 인기순 섹션 호출 오류:', error)
    return { data: [], hasMore: false }
  }
}

// ❌ v1 API 사용 중단 - v2 API로 대체됨
// 기존 API (fallback용) - 강화된 에러 처리
// const fetchRecommendedCitiesFallback = async (
//   page: number = 0,
//   limit: number = 3
// ): Promise<{ data: CitySection[], hasMore: boolean }> => {
//   try {
//     const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
//
//     // 2초 타임아웃 설정
//     const timeoutPromise = new Promise((_, reject) =>
//       setTimeout(() => reject(new Error('Fallback API 타임아웃')), 2000)
//     )
//
//     const fetchPromise = fetch(`${API_BASE_URL}/api/v1/attractions/cities?page=${page}&limit=${limit}`)
//     const response = await Promise.race([fetchPromise, timeoutPromise]) as Response
//
//     if (!response.ok) {
//       let errorMessage = ''
//       try {
//         const errorText = await response.text()
//         errorMessage = errorText
//       } catch (textError) {
//         errorMessage = `HTTP ${response.status} 오류`
//       }
//       console.warn(`Fallback API HTTP 오류 (${response.status}):`, errorMessage)
//       throw new Error(`HTTP error! status: ${response.status}`)
//     }
//
//     let result
//     try {
//       result = await response.json()
//     } catch (jsonError) {
//       console.error('Fallback API 응답 JSON 파싱 오류:', jsonError)
//       throw new Error('Fallback API 응답 데이터 형식 오류')
//     }
//
//     return {
//       data: result.data || [],
//       hasMore: result.hasMore || false
//     }
//   } catch (error) {
//     console.warn('Fallback API 호출 오류:', error instanceof Error ? error.message : String(error))
//     return { data: [], hasMore: false }
//   }
// }

// ✅ v2 개인화 추천 API 사용 (모든 사용자 v2 API) - 백엔드 설정 사용
export const fetchPersonalizedRegionCategories = async (
  requestedLimit?: number,
  userInfo?: any,
  session?: any,
  region?: string
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    // 백엔드에서 설정 가져오기
    const config = await getRecommendationConfig()
    const userType = getUserType(userInfo, session)
    const settings = calculateRecommendationSettings(userType, config)

    // 안전장치: settings가 유효하지 않은 경우 기본값 사용
    if (!settings || typeof settings.sectionCount === 'undefined') {
      console.warn('설정 계산 실패, 기본값 사용:', settings)
      const fallbackSettings = { sectionCount: 3, itemsPerSection: 8, totalRecommendations: 24 }
      return session
        ? await fetchRecommendations(fallbackSettings.totalRecommendations, fallbackSettings.sectionCount, fallbackSettings.itemsPerSection, region)
        : await fetchPopularPlacesByBookmarks(fallbackSettings.sectionCount, fallbackSettings.itemsPerSection, region)
    }

    // console.log(`v2 API 통합 추천: 사용자타입=${userType}, 로그인=${!!session}, 제한=${settings.totalRecommendations}, 섹션=${settings.sectionCount}, 아이템=${settings.itemsPerSection}`)

    // 로그인 사용자: 개인화 추천, 비로그인 사용자: 북마크 기반 인기 장소
    if (session) {
      // ✅ v2 개인화 추천 API 직접 호출 (로그인 사용자)
      return await fetchRecommendations(settings.totalRecommendations, settings.sectionCount, settings.itemsPerSection, region)
    } else {
      // ✅ 북마크 기반 인기 장소 API 호출 (비로그인 사용자)
      return await fetchPopularPlacesByBookmarks(settings.sectionCount, settings.itemsPerSection, region)
    }
  } catch (error) {
    console.error('v2 개인화 추천 API 호출 오류:', error instanceof Error ? error.message : String(error))

    // ❌ v1 fallback 비활성화 (주석처리)
    // try {
    //   console.log('v2 에러 fallback으로 기본 추천 API 시도')
    //   return await fetchCitiesByCategory(0) // 기본값 사용
    // } catch (fallbackError) {
    //   console.warn('Fallback API도 실패:', fallbackError)
    //   return {
    //     data: [],
    //     hasMore: false
    //   }
    // }

    // v2 API 실패 시 빈 결과 반환 (v1 fallback 없음)
    return {
      data: [],
      hasMore: false
    }
  }
}

// ❌ v1 API 비활성화 - 지역별 카테고리별 구분된 데이터 가져오기 (더 이상 사용 안 함)
/*
export const fetchCitiesByCategory = async (
  page: number = 0
): Promise<{ data: CitySection[], hasMore: boolean }> => {
  try {
    // 백엔드에서 설정 가져오기 (비로그인은 guest 설정 사용)
    const config = await getRecommendationConfig()
    const settings = calculateRecommendationSettings('guest', config)

    // console.log(`비로그인 백엔드 설정: 섹션=${settings.sectionCount}, 아이템=${settings.itemsPerSection}`)

    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

    // 2초 타임아웃 설정
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('기본 추천 API 타임아웃')), 2000)
    )

    const fetchPromise = fetch(`${API_BASE_URL}/api/v1/attractions/cities-by-category?page=${page}&limit=${settings.sectionCount}`)
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

    // 백엔드 설정에 따라 데이터 제한
    const limitedData = (result.data || []).slice(0, settings.sectionCount)
    const processedData = limitedData.map((section: any) => ({
      ...section,
      attractions: (section.attractions || []).slice(0, settings.itemsPerSection)
    }))

    // console.log(`비로그인 추천 완료: ${limitedData.length}개 섹션, 섹션당 최대 ${settings.itemsPerSection}개 아이템`)

    return {
      data: processedData,
      hasMore: result.hasMore || false
    }
  } catch (error) {
    console.warn('기본 추천 API 호출 오류:', error instanceof Error ? error.message : String(error))
    return { data: [], hasMore: false }
  }
}
*/

// File end