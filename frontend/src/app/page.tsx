'use client'

import React, { useState, FormEvent, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { fetchRecommendedCities, type CitySection } from '../lib/dummyData'

export default function Home() {
  const router = useRouter()
  const { data: session, status } = useSession()
  const [searchQuery, setSearchQuery] = useState('')
  const [citySections, setCitySections] = useState<CitySection[]>([])
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [page, setPage] = useState(0)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const loadingRef = useRef(false)

  // 추천 도시 데이터 로드 함수
  const loadRecommendedCities = useCallback(async (pageNum: number) => {
    if (loadingRef.current) return

    loadingRef.current = true
    setLoading(true)
    try {
      const { data, hasMore: moreData } = await fetchRecommendedCities(pageNum, 30)

      if (pageNum === 0) {
        setCitySections(data)
      } else {
        setCitySections(prev => [...prev, ...data])
      }

      setHasMore(moreData)
      setPage(pageNum)
    } catch (error) {
      console.error('데이터 로드 오류:', error)
    } finally {
      setLoading(false)
      loadingRef.current = false
    }
  }, [])

  // 초기 데이터 로드 (세션이 로드된 후)
  useEffect(() => {
    if (status !== 'loading') {
      loadRecommendedCities(0)
    }
  }, [status])

  // 무한 스크롤 감지
  const lastElementRef = useCallback((node: HTMLDivElement | null) => {
    if (loadingRef.current) return
    if (observerRef.current) observerRef.current.disconnect()

    observerRef.current = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasMore && !loadingRef.current) {
        loadRecommendedCities(page + 1)
      }
    })

    if (node) observerRef.current.observe(node)
  }, [hasMore, page])

  const handleSearch = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=${encodeURIComponent(searchQuery)}`)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const results = await response.json()
      console.log('검색 결과:', results)
      
      // TODO: 검색 결과 페이지로 이동하거나 결과 표시
      // router.push(`/search?q=${encodeURIComponent(searchQuery)}`)
      
    } catch (error) {
      console.error('검색 오류:', error)
    }
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-slate-200 overflow-y-auto no-scrollbar pb-20">
      {/* Logo */}
      <div className="text-center mt-20 mb-8">
        <h1 className="text-6xl font-extrabold text-[#3E68FF] tracking-tight">witple</h1>
      </div>

      {/* Search Bar */}
      <div className="px-4 mb-24 mt-20">
        <form onSubmit={handleSearch} className="relative w-[90%] mx-auto">
          <input
            type="text"
            placeholder="어디로 떠나볼까요?"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="
              w-full px-6 pr-12 py-[1.14rem] text-lg
              rounded-3xl
              bg-[#12345D]/70
              text-slate-200 placeholder-[#6FA0E6]
              ring-1 ring-[#1F3C7A] shadow-xl
              focus:outline-none focus:ring-2 focus:ring-[#3E68FF]/60
            "
          />
          <button
            type="submit"
            className="absolute right-5 top-1/2 -translate-y-1/2 p-1 text-[#6FA0E6] hover:text-white transition"
            aria-label="검색"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
        </form>
      </div>

      {/* 로그인 상태 표시 */}
      {status !== 'loading' && (
        <div className="px-4 mb-4 text-center">
          {session ? (
            <p className="text-[#3E68FF] text-sm bg-[#12345D]/70 px-4 py-2 rounded-full inline-block">
              🎯 {session.user?.name || session.user?.email}님을 위한 맞춤 추천
            </p>
          ) : (
            <p className="text-[#94A9C9] text-sm bg-[#12345D]/70 px-4 py-2 rounded-full inline-block">
              📍 인기 여행지 추천 • 로그인하면 맞춤 추천을 받을 수 있어요
            </p>
          )}
        </div>
      )}

      {/* 추천 도시별 명소 섹션 (무한 스크롤) */}
      <main className="px-4 pb-24 space-y-12">
        {citySections.map((citySection, index) => (
          <div
            key={`${citySection.id}-${index}`}
            ref={index === citySections.length - 1 ? lastElementRef : null}
          >
            <SectionCarousel
              title={`${citySection.description}`}
              cityName={citySection.cityName}
              attractions={citySection.attractions}
              recommendationScore={citySection.recommendationScore}
              onAttractionClick={(attractionId) => router.push(`/attraction/${attractionId}`)}
            />
          </div>
        ))}

        {/* 로딩 인디케이터 */}
        {loading && (
          <div className="flex justify-center items-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF]"></div>
            <span className="ml-2 text-[#94A9C9]">추천 여행지를 불러오는 중...</span>
          </div>
        )}

        {/* 더 이상 데이터가 없을 때 */}
        {!hasMore && citySections.length > 0 && (
          <div className="text-center py-8">
            <p className="text-[#6FA0E6] text-lg">모든 추천 여행지를 확인했습니다 ✨</p>
            <p className="text-[#94A9C9] text-sm mt-2">새로운 여행지가 추가되면 알려드릴게요!</p>
          </div>
        )}

        {/* 데이터가 없을 때 */}
        {!loading && citySections.length === 0 && (
          <div className="text-center py-16">
            <p className="text-[#94A9C9] text-lg">추천할 여행지를 준비 중입니다...</p>
          </div>
        )}
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-[#0F1A31]/95 backdrop-blur-md border-t border-[#1F3C7A]/30">
        <div className="flex items-center justify-around px-4 py-5 max-w-md mx-auto">
          <Link
            href="/"
            className="flex flex-col items-center py-1 px-2 text-[#3E68FF]"
            aria-label="홈"
          >
            <svg className="w-6 h-6 mb-1" fill="currentColor" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </Link>

          <Link
            href="/quest"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="퀘스트"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
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
              // 실제 로그인 상태 확인
              if (session) {
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

/** 추천 도시별 명소 섹션 컴포넌트 */
function SectionCarousel({
  title,
  cityName,
  attractions,
  recommendationScore,
  onAttractionClick,
}: {
  title: string
  cityName: string
  attractions: { id: string; name: string; description: string; imageUrl: string; rating: number; category: string }[]
  recommendationScore: number
  onAttractionClick: (attractionId: string) => void
}) {
  return (
    <section aria-label={`${cityName} ${title}`} className="w-full">
      {/* 도시 제목과 추천 점수 */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-2xl md:text-3xl font-semibold text-[#94A9C9]">
            {title}
          </h2>
          <div className="flex items-center mt-2 space-x-2">
            <span className="text-[#3E68FF] font-bold text-lg">{cityName}</span>
            <div className="flex items-center">
              <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              <span className="text-sm text-[#6FA0E6]">{recommendationScore}% 추천</span>
            </div>
          </div>
        </div>
      </div>

      {/* 가로 캐러셀 트랙 */}
      <div className="relative -mx-4 px-4">
        <div
          className="
            flex items-stretch gap-4
            overflow-x-auto no-scrollbar
            snap-x snap-mandatory scroll-smooth
            pb-2
          "
          style={{ scrollBehavior: 'smooth' }}
        >
          {attractions.map((attraction) => (
            <figure
              key={attraction.id}
              className="
                snap-start shrink-0
                rounded-[28px] overflow-hidden
                bg-[#0F1A31] ring-1 ring-white/5
                w-[78%] xs:w-[70%] sm:w-[320px]
                cursor-pointer hover:ring-[#3E68FF]/50 transition-all duration-300
                group
              "
              onClick={() => onAttractionClick(attraction.id)}
            >
              {/* 이미지 영역 */}
              <div className="aspect-[4/3] relative overflow-hidden">
                {/* 실제 프로덕션에서는 Next.js Image 컴포넌트 사용 권장 */}
                <div className="w-full h-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
                  <span className="text-white text-lg opacity-70">
                    {attraction.name}
                  </span>
                </div>
                <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all duration-300"></div>

                {/* 카테고리 배지 */}
                <div className="absolute top-3 left-3">
                  <span className="px-2 py-1 text-xs bg-black/50 text-white rounded-full backdrop-blur-sm">
                    {getCategoryName(attraction.category?.trim()) || attraction.category}
                  </span>
                </div>

                {/* 평점 */}
                <div className="absolute top-3 right-3 flex items-center bg-black/50 rounded-full px-2 py-1 backdrop-blur-sm">
                  <svg className="w-3 h-3 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  <span className="text-white text-xs font-medium">{attraction.rating}</span>
                </div>
              </div>

              {/* 명소 정보 */}
              <div className="p-4">
                <h3 className="font-semibold text-white text-lg mb-2 group-hover:text-[#3E68FF] transition-colors">
                  {attraction.name}
                </h3>
                <p className="text-[#94A9C9] text-sm line-clamp-2">
                  {attraction.description}
                </p>
              </div>
            </figure>
          ))}
        </div>

        {/* 좌/우 가장자리 페이드 */}
        <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-[#0B1220] to-transparent" />
        <div className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-[#0B1220] to-transparent" />
      </div>
    </section>
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
