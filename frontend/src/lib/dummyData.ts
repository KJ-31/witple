// 이미 추천 알고리즘으로 선별된 데이터라고 가정
export interface Attraction {
  id: string
  name: string
  description: string
  imageUrl: string
  rating: number
  category: 'tourist' | 'food' | 'culture' | 'nature' | 'shopping'
}

export interface CitySection {
  id: string
  cityName: string
  description: string
  region: string
  attractions: Attraction[]
  recommendationScore: number // 추천 점수 (높을수록 상위 노출)
}

// 추천 알고리즘으로 선별된 도시별 명소 데이터
export const RECOMMENDED_CITY_SECTIONS: CitySection[] = [
  {
    id: 'seoul',
    cityName: '서울',
    description: '과거와 현재가 공존하는',
    region: 'capital',
    recommendationScore: 95,
    attractions: [
      {
        id: 'gyeongbokgung',
        name: '경복궁',
        description: '조선왕조의 정궁',
        imageUrl: '/images/gyeongbokgung.jpg',
        rating: 4.5,
        category: 'culture'
      },
      {
        id: 'myeongdong',
        name: '명동',
        description: '쇼핑과 맛집의 메카',
        imageUrl: '/images/myeongdong.jpg',
        rating: 4.2,
        category: 'shopping'
      },
      {
        id: 'namsan-tower',
        name: '남산타워',
        description: '서울의 야경 명소',
        imageUrl: '/images/namsan-tower.jpg',
        rating: 4.3,
        category: 'tourist'
      },
      {
        id: 'hongdae',
        name: '홍대',
        description: '젊음과 예술의 거리',
        imageUrl: '/images/hongdae.jpg',
        rating: 4.4,
        category: 'culture'
      }
    ]
  },
  {
    id: 'jeju',
    cityName: '제주도',
    description: '자연이 선사하는 힐링',
    region: 'jeju',
    recommendationScore: 92,
    attractions: [
      {
        id: 'hallasan',
        name: '한라산',
        description: '제주도의 상징',
        imageUrl: '/images/hallasan.jpg',
        rating: 4.7,
        category: 'nature'
      },
      {
        id: 'seongsan-ilchulbong',
        name: '성산일출봉',
        description: '일출의 명소',
        imageUrl: '/images/seongsan-ilchulbong.jpg',
        rating: 4.6,
        category: 'nature'
      },
      {
        id: 'jeju-black-pork',
        name: '제주 흑돼지',
        description: '제주도만의 특별한 맛',
        imageUrl: '/images/jeju-black-pork.jpg',
        rating: 4.8,
        category: 'food'
      }
    ]
  },
  {
    id: 'busan',
    cityName: '부산',
    description: '바다와 산이 어우러진 영화의 도시',
    region: 'southeast',
    recommendationScore: 88,
    attractions: [
      {
        id: 'haeundae-beach',
        name: '해운대 해수욕장',
        description: '한국 최고의 해수욕장',
        imageUrl: '/images/haeundae-beach.jpg',
        rating: 4.6,
        category: 'nature'
      },
      {
        id: 'jagalchi-market',
        name: '자갈치시장',
        description: '신선한 해산물 전통시장',
        imageUrl: '/images/jagalchi-market.jpg',
        rating: 4.4,
        category: 'food'
      },
      {
        id: 'gamcheon-village',
        name: '감천문화마을',
        description: '한국의 마추픽추',
        imageUrl: '/images/gamcheon-village.jpg',
        rating: 4.5,
        category: 'culture'
      }
    ]
  },
  {
    id: 'jeonju',
    cityName: '전주',
    description: '한국의 맛과 전통문화의 중심지',
    region: 'southwest',
    recommendationScore: 82,
    attractions: [
      {
        id: 'jeonju-hanok-village',
        name: '전주 한옥마을',
        description: '전통 한옥 문화관광지',
        imageUrl: '/images/jeonju-hanok-village.jpg',
        rating: 4.5,
        category: 'culture'
      },
      {
        id: 'jeonju-bibimbap',
        name: '전주 비빔밥',
        description: '전주 대표 향토음식',
        imageUrl: '/images/jeonju-bibimbap.jpg',
        rating: 4.7,
        category: 'food'
      }
    ]
  },
  {
    id: 'gangneung',
    cityName: '강릉',
    description: '동해안의 보석',
    region: 'northeast',
    recommendationScore: 78,
    attractions: [
      {
        id: 'anmok-beach',
        name: '안목해변',
        description: '커피거리로 유명한 해변',
        imageUrl: '/images/anmok-beach.jpg',
        rating: 4.3,
        category: 'nature'
      },
      {
        id: 'gyeongpo-beach',
        name: '경포해변',
        description: '넓은 백사장의 아름다운 해변',
        imageUrl: '/images/gyeongpo-beach.jpg',
        rating: 4.4,
        category: 'nature'
      }
    ]
  },
  {
    id: 'gyeongju',
    cityName: '경주',
    description: '천년고도, 살아있는 역사의 도시',
    region: 'southeast',
    recommendationScore: 75,
    attractions: [
      {
        id: 'bulguksa',
        name: '불국사',
        description: '세계문화유산 불교사찰',
        imageUrl: '/images/bulguksa.jpg',
        rating: 4.6,
        category: 'culture'
      },
      {
        id: 'seokguram',
        name: '석굴암',
        description: '동양 조각 예술의 걸작',
        imageUrl: '/images/seokguram.jpg',
        rating: 4.5,
        category: 'culture'
      }
    ]
  },
  {
    id: 'incheon',
    cityName: '인천',
    description: '역사와 현대가 만나는 항구도시',
    region: 'capital',
    recommendationScore: 70,
    attractions: [
      {
        id: 'incheon-chinatown',
        name: '인천 차이나타운',
        description: '한국 최초의 차이나타운',
        imageUrl: '/images/incheon-chinatown.jpg',
        rating: 4.2,
        category: 'culture'
      },
      {
        id: 'songdo-central-park',
        name: '송도 센트럴파크',
        description: '미래도시 송도의 명소',
        imageUrl: '/images/songdo-central-park.jpg',
        rating: 4.1,
        category: 'nature'
      }
    ]
  },
  {
    id: 'andong',
    cityName: '안동',
    description: '한국 정신문화의 수도',
    region: 'southeast',
    recommendationScore: 65,
    attractions: [
      {
        id: 'hahoe-village',
        name: '하회마을',
        description: '세계문화유산 전통마을',
        imageUrl: '/images/hahoe-village.jpg',
        rating: 4.5,
        category: 'culture'
      },
      {
        id: 'andong-jjimdak',
        name: '안동찜닭',
        description: '안동 대표 향토음식',
        imageUrl: '/images/andong-jjimdak.jpg',
        rating: 4.6,
        category: 'food'
      }
    ]
  }
]

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