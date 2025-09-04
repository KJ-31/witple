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
    const API_BASE_URL = 'http://localhost:8000'
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