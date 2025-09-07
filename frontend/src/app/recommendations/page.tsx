'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'

interface RecommendationItem {
  id: string
  title: string
  author: string
  genre: string
  rating: number
  imageUrl: string
  isNew?: boolean
  isUpdated?: boolean
  episodeCount?: number
  views?: number
  tags?: string[]
}

export default function RecommendationsPage() {
  const router = useRouter()
  const { data: session, status } = useSession()
  const [loading, setLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState('레저')
  const [leftColumnItems, setLeftColumnItems] = useState<RecommendationItem[]>([])
  const [rightColumnItems, setRightColumnItems] = useState<RecommendationItem[]>([])
  const [discoveryItems, setDiscoveryItems] = useState<RecommendationItem[]>([])
  const [newItems, setNewItems] = useState<RecommendationItem[]>([])

  const categories = ['레저', '숙박', '쇼핑', '자연', '맛집', '인문']

  // DB에서 데이터 가져오기
  useEffect(() => {
    const fetchCategoryData = async () => {
      try {
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
        
        // 메인 추천 데이터 (15개)
        const response = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=${encodeURIComponent(selectedCategory)}&limit=15`)
        if (response.ok) {
          const data = await response.json()
          const attractions = data.attractions || []
          
          const formattedItems = attractions.map((attraction: any, index: number) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '여행지',
            genre: selectedCategory,
            rating: attraction.rating || (4.9 - index * 0.1),
            views: Math.floor(Math.random() * 5000) + 1000,
            imageUrl: attraction.imageUrl || `https://images.unsplash.com/photo-${1506905925346 + index}?w=100&h=100&fit=crop`
          }))
          
          setLeftColumnItems(formattedItems.slice(0, 8))
          setRightColumnItems(formattedItems.slice(8, 15))
        } else {
          // 응답이 실패하면 더미 데이터 사용
          generateDummyData()
        }
      } catch (error) {
        console.error('데이터 가져오기 실패:', error)
        generateDummyData()
      }
      
      setLoading(false)
    }
    
    const generateDummyData = () => {
      const baseItems = [
        {
          id: `${selectedCategory}-1`,
          title: `${selectedCategory} 스팟 1`,
          author: selectedCategory === '레저' ? '스포츠 액티비티' : selectedCategory === '숙박' ? '프리미엄 호텔' : selectedCategory === '쇼핑' ? '인기 쇼핑몰' : selectedCategory === '자연' ? '자연 경관' : selectedCategory === '맛집' ? '로컬 맛집' : '역사 문화',
          genre: selectedCategory,
          rating: 4.9,
          imageUrl: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-2`,
          title: `${selectedCategory} 스팟 2`,
          author: selectedCategory === '레저' ? '익스트림 스포츠' : selectedCategory === '숙박' ? '부티크 호텔' : selectedCategory === '쇼핑' ? '아울렛몰' : selectedCategory === '자연' ? '국립공원' : selectedCategory === '맛집' ? '전통 요리' : '박물관',
          genre: selectedCategory,
          rating: 4.8,
          imageUrl: 'https://images.unsplash.com/photo-1539650116574-75c0c6d73ab7?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-3`,
          title: `${selectedCategory} 스팟 3`,
          author: selectedCategory === '레저' ? '수상 스포츠' : selectedCategory === '숙박' ? '펜션' : selectedCategory === '쇼핑' ? '전통시장' : selectedCategory === '자연' ? '해변' : selectedCategory === '맛집' ? '디저트 카페' : '유적지',
          genre: selectedCategory,
          rating: 4.7,
          imageUrl: 'https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-4`,
          title: `${selectedCategory} 스팟 4`,
          author: selectedCategory === '레저' ? '실내 액티비티' : selectedCategory === '숙박' ? '게스트하우스' : selectedCategory === '쇼핑' ? '브랜드 매장' : selectedCategory === '자연' ? '산림' : selectedCategory === '맛집' ? '퓨전 레스토랑' : '갤러리',
          genre: selectedCategory,
          rating: 4.6,
          imageUrl: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-5`,
          title: `${selectedCategory} 스팟 5`,
          author: selectedCategory === '레저' ? '어드벤처 투어' : selectedCategory === '숙박' ? '리조트' : selectedCategory === '쇼핑' ? '명품 매장' : selectedCategory === '자연' ? '폭포' : selectedCategory === '맛집' ? '바 & 펜' : '전시관',
          genre: selectedCategory,
          rating: 4.5,
          imageUrl: 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-6`,
          title: `${selectedCategory} 스팟 6`,
          author: selectedCategory === '레저' ? '테마파크' : selectedCategory === '숙박' ? '캠핑장' : selectedCategory === '쇼핑' ? '플리마켓' : selectedCategory === '자연' ? '호수' : selectedCategory === '맛집' ? '길거리 음식' : '도서관',
          genre: selectedCategory,
          rating: 4.4,
          imageUrl: 'https://images.unsplash.com/photo-1551516595-834406bf4178?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-7`,
          title: `${selectedCategory} 스팟 7`,
          author: selectedCategory === '레저' ? '워터파크' : selectedCategory === '숙박' ? '한옥 스테이' : selectedCategory === '쇼핑' ? '백화점' : selectedCategory === '자연' ? '계곡' : selectedCategory === '맛집' ? '브런치 카페' : '문화센터',
          genre: selectedCategory,
          rating: 4.3,
          imageUrl: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-8`,
          title: `${selectedCategory} 스팟 8`,
          author: selectedCategory === '레저' ? '볼링장' : selectedCategory === '숙박' ? '글램핑' : selectedCategory === '쇼핑' ? '홈플러스' : selectedCategory === '자연' ? '섬' : selectedCategory === '맛집' ? '이자카야' : '아트센터',
          genre: selectedCategory,
          rating: 4.2,
          imageUrl: 'https://images.unsplash.com/photo-1539650116574-75c0c6d73ab7?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-9`,
          title: `${selectedCategory} 스팟 9`,
          author: selectedCategory === '레저' ? 'VR 체험관' : selectedCategory === '숙박' ? '유스호스텔' : selectedCategory === '쇼핑' ? '지하상가' : selectedCategory === '자연' ? '동굴' : selectedCategory === '맛집' ? '피자집' : '과학관',
          genre: selectedCategory,
          rating: 4.1,
          imageUrl: 'https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-10`,
          title: `${selectedCategory} 스팟 10`,
          author: selectedCategory === '레저' ? '노래방' : selectedCategory === '숙박' ? '모텔' : selectedCategory === '쇼핑' ? '편의점' : selectedCategory === '자연' ? '습지' : selectedCategory === '맛집' ? '치킨집' : '도서관',
          genre: selectedCategory,
          rating: 4.0,
          imageUrl: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-11`,
          title: `${selectedCategory} 스팟 11`,
          author: selectedCategory === '레저' ? '게임센터' : selectedCategory === '숙박' ? '펜션' : selectedCategory === '쇼핑' ? '마트' : selectedCategory === '자연' ? '강' : selectedCategory === '맛집' ? '햄버거집' : '음악당',
          genre: selectedCategory,
          rating: 3.9,
          imageUrl: 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-12`,
          title: `${selectedCategory} 스팟 12`,
          author: selectedCategory === '레저' ? 'PC방' : selectedCategory === '숙박' ? '호스텔' : selectedCategory === '쇼핑' ? '면세점' : selectedCategory === '자연' ? '공원' : selectedCategory === '맛집' ? '분식점' : '연극장',
          genre: selectedCategory,
          rating: 3.8,
          imageUrl: 'https://images.unsplash.com/photo-1551516595-834406bf4178?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-13`,
          title: `${selectedCategory} 스팟 13`,
          author: selectedCategory === '레저' ? '당구장' : selectedCategory === '숙박' ? '콘도' : selectedCategory === '쇼핑' ? '로드샵' : selectedCategory === '자연' ? '들판' : selectedCategory === '맛집' ? '술집' : '컨벤션센터',
          genre: selectedCategory,
          rating: 3.7,
          imageUrl: 'https://images.unsplash.com/photo-1522383225653-ed111181a951?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-14`,
          title: `${selectedCategory} 스팟 14`,
          author: selectedCategory === '레저' ? '헬스장' : selectedCategory === '숙박' ? '팬션' : selectedCategory === '쇼핑' ? '온라인몰' : selectedCategory === '자연' ? '꽃밭' : selectedCategory === '맛집' ? '카페' : '공연장',
          genre: selectedCategory,
          rating: 3.6,
          imageUrl: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${selectedCategory}-15`,
          title: `${selectedCategory} 스팟 15`,
          author: selectedCategory === '레저' ? '요가스튜디오' : selectedCategory === '숙박' ? '에어비앤비' : selectedCategory === '쇼핑' ? '아웃렛' : selectedCategory === '자연' ? '절벽' : selectedCategory === '맛집' ? '베이커리' : '시민회관',
          genre: selectedCategory,
          rating: 3.5,
          imageUrl: 'https://images.unsplash.com/photo-1445346366695-5bf62de05412?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        }
      ]
      setLeftColumnItems(baseItems.slice(0, 8))
      setRightColumnItems(baseItems.slice(8, 15))
    }
    
    fetchCategoryData()
  }, [selectedCategory])
  
  // 추가 섹션 데이터 가져오기
  useEffect(() => {
    const fetchAdditionalSections = async () => {
      try {
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
        
        // "오늘의 발견" 섹션 데이터 (다양한 카테고리에서 인기 장소들)
        const discoveryResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/search?limit=4`)
        if (discoveryResponse.ok) {
          const discoveryData = await discoveryResponse.json()
          const discoveryAttractions = discoveryData.attractions || []
          
          const formattedDiscoveryItems = discoveryAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.description || `${attraction.city?.name || attraction.region}의 숨은 보물`,
            genre: getCategoryInKorean(attraction.category),
            rating: attraction.rating || 4.7,
            views: Math.floor(Math.random() * 3000) + 1000,
            imageUrl: attraction.imageUrl || `https://images.unsplash.com/photo-${Math.floor(Math.random() * 1000000000)}?w=200&h=280&fit=crop`,
            tags: ['추천', '인기', '특별']
          }))
          
          setDiscoveryItems(formattedDiscoveryItems)
        }
        
        // "새로 나온 코스" 섹션 데이터 (최근 추가된 장소들)
        const newResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/search?limit=3`)
        if (newResponse.ok) {
          const newData = await newResponse.json()
          const newAttractions = newData.attractions || []
          
          const formattedNewItems = newAttractions.map((attraction: any) => ({
            id: attraction.id,
            title: attraction.name,
            author: attraction.city?.name || attraction.region || '새로운 여행지',
            genre: getCategoryInKorean(attraction.category),
            rating: attraction.rating || 4.5,
            views: Math.floor(Math.random() * 2000) + 500,
            imageUrl: attraction.imageUrl || `https://images.unsplash.com/photo-${Math.floor(Math.random() * 1000000000)}?w=200&h=280&fit=crop`
          }))
          
          setNewItems(formattedNewItems)
        }
      } catch (error) {
        console.error('추가 섹션 데이터 가져오기 실패:', error)
        // 실패시 기본 더미 데이터 유지
      }
    }
    
    fetchAdditionalSections()
  }, [])
  
  // 카테고리 한국어 변환 함수
  const getCategoryInKorean = (category: string): string => {
    const categoryMap: { [key: string]: string } = {
      'leisure_sports': '레저',
      'accommodation': '숙박',
      'shopping': '쇼핑',
      'nature': '자연',
      'restaurants': '맛집',
      'humanities': '인문'
    }
    return categoryMap[category] || '여행'
  }

  const handleItemClick = (item: RecommendationItem) => {
    // 실제로는 여행 상세 페이지로 이동
    console.log('Clicked item:', item.title)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
          <p className="text-[#94A9C9]">추천을 불러오는 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-white pb-20">
      {/* Header */}
      <div className="sticky top-0 bg-[#0B1220]/95 backdrop-blur-md z-40 border-b border-[#1F3C7A]/30">
        <div className="px-4 py-4">
          <h1 className="text-2xl font-bold text-[#3E68FF]">추천</h1>
          <p className="text-[#94A9C9] text-sm mt-1">당신을 위한 맞춤 여행 추천</p>
        </div>
        
        {/* Category Tabs */}
        <div className="px-4 pb-4">
          <div className="flex space-x-4 overflow-x-auto no-scrollbar">
            {categories.map((category) => (
              <button
                key={category}
                onClick={() => setSelectedCategory(category)}
                className={`flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  selectedCategory === category
                    ? 'bg-[#3E68FF] text-white'
                    : 'bg-[#1F3C7A]/30 text-[#6FA0E6] hover:bg-[#1F3C7A]/50'
                }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-6">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-white">지금 많이 찾고 있는 {selectedCategory}</h2>
        </div>
        
        {/* Horizontal Slide Layout */}
        <div className="overflow-x-auto no-scrollbar">
          <div className="flex gap-12 pb-4" style={{ width: 'max-content' }}>
            {/* Group items into pages of 6 (3 rows x 2 columns each) */}
            {(() => {
              const allItems = [...leftColumnItems, ...rightColumnItems]
              const pages = []
              for (let i = 0; i < allItems.length; i += 6) {
                pages.push(allItems.slice(i, i + 6))
              }
              
              return pages.map((pageItems, pageIndex) => (
                <div key={`page-${pageIndex}`} className="flex-shrink-0 w-80">
                  <div className="flex gap-6">
                    {/* Left Column of this page */}
                    <div className="flex-1 space-y-6">
                      {pageItems.slice(0, 3).map((item, index) => {
                        const globalIndex = pageIndex * 6 + index
                        return (
                          <div
                            key={item.id}
                            className="flex items-center space-x-3 cursor-pointer hover:bg-[#1F3C7A]/20 rounded-lg p-2 transition-colors"
                            onClick={() => handleItemClick(item)}
                          >
                            <div className="flex-shrink-0 relative">
                              <img
                                src={item.imageUrl}
                                alt={item.title}
                                className="w-16 h-16 object-cover rounded-lg"
                              />
                              <div className="absolute top-1 left-1 bg-[#3E68FF] text-white text-xs px-1 py-0.5 rounded font-bold">
                                {globalIndex + 1}
                              </div>
                            </div>
                            <div className="flex-1 min-w-0">
                              <h3 className="font-semibold text-white text-sm mb-1 truncate">{item.title}</h3>
                              <p className="text-[#94A9C9] text-xs mb-1">{item.author}</p>
                              <div className="flex items-center">
                                <svg className="w-3 h-3 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                <span className="text-[#6FA0E6] text-xs mr-2">{item.rating}</span>
                                <span className="text-[#94A9C9] text-xs">({item.views?.toLocaleString()})</span>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                    
                    {/* Right Column of this page */}
                    <div className="flex-1 space-y-6">
                      {pageItems.slice(3, 6).map((item, index) => {
                        const globalIndex = pageIndex * 6 + index + 3
                        return (
                          <div
                            key={item.id}
                            className="flex items-center space-x-3 cursor-pointer hover:bg-[#1F3C7A]/20 rounded-lg p-2 transition-colors"
                            onClick={() => handleItemClick(item)}
                          >
                            <div className="flex-shrink-0 relative">
                              <img
                                src={item.imageUrl}
                                alt={item.title}
                                className="w-16 h-16 object-cover rounded-lg"
                              />
                              <div className="absolute top-1 left-1 bg-[#3E68FF] text-white text-xs px-1 py-0.5 rounded font-bold">
                                {globalIndex + 1}
                              </div>
                            </div>
                            <div className="flex-1 min-w-0">
                              <h3 className="font-semibold text-white text-sm mb-1 truncate">{item.title}</h3>
                              <p className="text-[#94A9C9] text-xs mb-1">{item.author}</p>
                              <div className="flex items-center">
                                <svg className="w-3 h-3 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                <span className="text-[#6FA0E6] text-xs mr-2">{item.rating}</span>
                                <span className="text-[#94A9C9] text-xs">({item.views?.toLocaleString()})</span>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              ))
            })()}
          </div>
        </div>
        
        {/* 오늘의 발견 섹션 */}
        <div className="mt-12 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">오늘의 발견</h2>
            <button className="text-[#6FA0E6] text-sm hover:text-[#3E68FF] transition-colors">
              더보기
            </button>
          </div>
          
          <div className="overflow-x-auto no-scrollbar">
            <div className="flex gap-4 pb-4" style={{ width: 'max-content' }}>
              {(discoveryItems.length > 0 ? discoveryItems : [
                {
                  id: 'discovery-1',
                  title: '제주도의 숨은 보물',
                  author: '현지인만 아는 비밀 장소들',
                  genre: '자연',
                  rating: 4.8,
                  views: 1543,
                  imageUrl: 'https://images.unsplash.com/photo-1539650116574-75c0c6d73ab7?w=200&h=280&fit=crop',
                  tags: ['숨은명소', '사진', '힐링']
                },
                {
                  id: 'discovery-2',
                  title: '서울 골목 탐험',
                  author: '어른의 원석 시간여행',
                  genre: '문화',
                  rating: 4.6,
                  views: 2341,
                  imageUrl: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=200&h=280&fit=crop',
                  tags: ['골목길', '레트로', '카페']
                },
                {
                  id: 'discovery-3',
                  title: '부산 야경 명소',
                  author: '마치 스위치를 켠 듯한 밤',
                  genre: '야경',
                  rating: 4.7,
                  views: 1876,
                  imageUrl: 'https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=200&h=280&fit=crop',
                  tags: ['야경', '데이트', '포토존']
                },
                {
                  id: 'discovery-4',
                  title: '경주 역사 탐방',
                  author: '천년의 시간을 걷다',
                  genre: '역사',
                  rating: 4.5,
                  views: 1234,
                  imageUrl: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=200&h=280&fit=crop',
                  tags: ['역사', '문화재', '교육']
                }
              ]).map((item) => (
                <div
                  key={item.id}
                  className="flex-shrink-0 w-48 cursor-pointer hover:scale-105 transition-transform"
                  onClick={() => handleItemClick(item)}
                >
                  <div className="bg-[#1F3C7A]/20 rounded-2xl overflow-hidden hover:bg-[#1F3C7A]/30 transition-colors">
                    <div className="relative">
                      <img
                        src={item.imageUrl}
                        alt={item.title}
                        className="w-full h-58 object-cover"
                      />
                      <div className="absolute top-2 left-2 bg-[#3E68FF] text-white text-xs px-2 py-1 rounded-full">
                        {item.genre}
                      </div>
                    </div>
                    <div className="p-4">
                      <h3 className="font-semibold text-white text-sm mb-1">{item.title}</h3>
                      <p className="text-[#94A9C9] text-xs mb-2">{item.author}</p>
                      <div className="flex items-center mb-2">
                        <svg className="w-3 h-3 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-[#6FA0E6] text-xs mr-2">{item.rating}</span>
                        <span className="text-[#94A9C9] text-xs">({item.views})</span>
                      </div>
                      {item.tags && (
                        <div className="flex flex-wrap gap-1">
                          {item.tags.map((tag, index) => (
                            <span
                              key={index}
                              className="bg-[#3E68FF]/20 text-[#6FA0E6] text-xs px-2 py-0.5 rounded-full"
                            >
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 새로 나온 코스 섹션 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">새로 나온 코스</h2>
            <button className="text-[#6FA0E6] text-sm hover:text-[#3E68FF] transition-colors">
              더보기
            </button>
          </div>
          
          <div className="overflow-x-auto no-scrollbar">
            <div className="flex gap-4 pb-4" style={{ width: 'max-content' }}>
              {(newItems.length > 0 ? newItems : [
                {
                  id: 'new-1',
                  title: '미지의 장호국의 시화',
                  author: '키타야 쿠로, 크레인',
                  genre: '인문',
                  rating: 3.8,
                  views: 4,
                  imageUrl: 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=200&h=280&fit=crop'
                },
                {
                  id: 'new-2',
                  title: '악역 영애 전생 아가씨',
                  author: '우에야마 미지로',
                  genre: '맛집',
                  rating: 4.8,
                  views: 1361,
                  imageUrl: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=200&h=280&fit=crop'
                },
                {
                  id: 'new-3',
                  title: '귀영다는 말 들은 없어!!',
                  author: '하루후지 나라바',
                  genre: '자연',
                  rating: 4.8,
                  views: 1222,
                  imageUrl: 'https://images.unsplash.com/photo-1522383225653-ed111181a951?w=200&h=280&fit=crop'
                }
              ]).map((item) => (
                <div
                  key={item.id}
                  className="flex-shrink-0 w-48 cursor-pointer hover:scale-105 transition-transform"
                  onClick={() => handleItemClick(item)}
                >
                  <div className="bg-[#1F3C7A]/20 rounded-2xl overflow-hidden hover:bg-[#1F3C7A]/30 transition-colors">
                    <div className="relative">
                      <img
                        src={item.imageUrl}
                        alt={item.title}
                        className="w-full h-58 object-cover"
                      />
                      <div className="absolute top-2 left-2 bg-[#3E68FF] text-white text-xs px-2 py-1 rounded-full">
                        {item.genre}
                      </div>
                    </div>
                    <div className="p-4">
                      <h3 className="font-semibold text-white text-sm mb-1">{item.title}</h3>
                      <p className="text-[#94A9C9] text-xs mb-2">{item.author}</p>
                      <div className="flex items-center">
                        <svg className="w-3 h-3 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-[#6FA0E6] text-xs mr-2">{item.rating}</span>
                        <span className="text-[#94A9C9] text-xs">({item.views})</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-[#0F1A31]/95 backdrop-blur-md border-t border-[#1F3C7A]/30">
        <div className="flex items-center justify-around px-4 py-5 max-w-md mx-auto">
          <Link
            href="/"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="홈"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </Link>

          <Link
            href="/recommendations"
            className="flex flex-col items-center py-1 px-2 text-[#3E68FF]"
            aria-label="추천"
          >
            <svg className="w-6 h-6 mb-1" fill="currentColor" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
          </Link>

          <Link
            href="/treasure"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="보물찾기"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </Link>

          <Link
            href="/feed"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="피드"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
            </svg>
          </Link>

          <button
            onClick={() => {
              // NextAuth 세션 상태를 확인하여 로그인 여부 판단
              if (status === 'authenticated' && session) {
                router.push('/profile')
              } else {
                router.push('/auth/login')
              }
            }}
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="마이페이지"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </button>
        </div>
      </nav>
    </div>
  )
}