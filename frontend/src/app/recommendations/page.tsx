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

interface RecommendationSection {
  id: string
  title: string
  items: RecommendationItem[]
  sectionType: 'featured' | 'grid' | 'horizontal'
}

export default function RecommendationsPage() {
  const router = useRouter()
  const { data: session, status } = useSession()
  const [sections, setSections] = useState<RecommendationSection[]>([])
  const [loading, setLoading] = useState(true)

  const [selectedCategory, setSelectedCategory] = useState('레저')
  const [leftColumnItems, setLeftColumnItems] = useState<RecommendationItem[]>([])
  const [rightColumnItems, setRightColumnItems] = useState<RecommendationItem[]>([])

  const categories = ['레저', '숙박', '쇼핑', '자연', '맛집', '인문']

  // 더미 데이터 생성
  useEffect(() => {
    const generateItemsForCategory = (category: string): RecommendationItem[] => {
      const baseItems = [
        {
          id: `${category}-1`,
          title: `${category} 스팟 1`,
          author: category === '레저' ? '스포츠 액티비티' : category === '숙박' ? '프리미엄 호텔' : category === '쇼핑' ? '인기 쇼핑몰' : category === '자연' ? '자연 경관' : category === '맛집' ? '로컬 맛집' : '역사 문화',
          genre: category,
          rating: 4.9,
          imageUrl: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${category}-2`,
          title: `${category} 스팟 2`,
          author: category === '레저' ? '익스트림 스포츠' : category === '숙박' ? '부티크 호텔' : category === '쇼핑' ? '아울렛몰' : category === '자연' ? '국립공원' : category === '맛집' ? '전통 요리' : '박물관',
          genre: category,
          rating: 4.8,
          imageUrl: 'https://images.unsplash.com/photo-1539650116574-75c0c6d73ab7?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${category}-3`,
          title: `${category} 스팟 3`,
          author: category === '레저' ? '수상 스포츠' : category === '숙박' ? '펜션' : category === '쇼핑' ? '전통시장' : category === '자연' ? '해변' : category === '맛집' ? '디저트 카페' : '유적지',
          genre: category,
          rating: 4.7,
          imageUrl: 'https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${category}-4`,
          title: `${category} 스팟 4`,
          author: category === '레저' ? '실내 액티비티' : category === '숙박' ? '게스트하우스' : category === '쇼핑' ? '브랜드 매장' : category === '자연' ? '산림' : category === '맛집' ? '퓨전 레스토랑' : '갤러리',
          genre: category,
          rating: 4.6,
          imageUrl: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${category}-5`,
          title: `${category} 스팟 5`,
          author: category === '레저' ? '어드벤처 투어' : category === '숙박' ? '리조트' : category === '쇼핑' ? '명품 매장' : category === '자연' ? '폭포' : category === '맛집' ? '바 & 펜' : '전시관',
          genre: category,
          rating: 4.5,
          imageUrl: 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        },
        {
          id: `${category}-6`,
          title: `${category} 스팟 6`,
          author: category === '레저' ? '테마파크' : category === '숙박' ? '캠핑장' : category === '쇼핑' ? '플리마켓' : category === '자연' ? '호수' : category === '맛집' ? '길거리 음식' : '도서관',
          genre: category,
          rating: 4.4,
          imageUrl: 'https://images.unsplash.com/photo-1551516595-834406bf4178?w=100&h=100&fit=crop',
          views: Math.floor(Math.random() * 5000) + 1000
        }
      ]
      return baseItems
    }

    const items = generateItemsForCategory(selectedCategory)
    setLeftColumnItems(items.slice(0, 3))
    setRightColumnItems(items.slice(3, 6))
    setLoading(false)
  }, [selectedCategory])

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
        
        {/* Two Column Layout */}
        <div className="flex gap-4">
          {/* Left Column */}
          <div className="flex-1 space-y-4">
            {leftColumnItems.map((item, index) => (
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
                    {index + 1}
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
            ))}
          </div>
          
          {/* Right Column */}
          <div className="flex-1 space-y-4">
            {rightColumnItems.map((item, index) => (
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
                    {index + 4}
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
            ))}
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