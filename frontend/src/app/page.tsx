'use client'

import React, { useState, FormEvent, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { fetchPersonalizedRegionCategories, fetchCitiesByCategory, type CitySection } from '../lib/dummyData'
import { BottomNavigation } from '../components'
import { actionTracker } from '../lib/actionTracker'

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

  // 필터링 상태
  const [selectedRegion, setSelectedRegion] = useState<string>('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [regions, setRegions] = useState<string[]>([])
  const [categories, setCategories] = useState<Array<{ id: string, name: string, description: string }>>([])
  const [showFilters, setShowFilters] = useState(false)

  // 검색 결과 상태
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showSearchResults, setShowSearchResults] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  // 챗봇 상태
  const [showChatbot, setShowChatbot] = useState(false)
  const [chatMessage, setChatMessage] = useState('')
  const [chatMessages, setChatMessages] = useState([
    {
      id: 1,
      type: 'bot',
      message: '쉽게 여행 계획을 작성해볼래?',
      timestamp: new Date()
    }
  ])

  // 추천 도시 데이터 로드 함수 (로그인 상태에 따라 다른 데이터 로드)
  const loadRecommendedCities = useCallback(async (pageNum: number) => {
    if (loadingRef.current) return

    loadingRef.current = true
    setLoading(true)
    try {
      let data: CitySection[], hasMore: boolean

      // 로그인 상태에 따라 다른 API 사용
      if (session) {
        const result = await fetchPersonalizedRegionCategories(5) // 5개 지역
        data = result.data
        hasMore = result.hasMore
      } else {
        const result = await fetchCitiesByCategory(pageNum, 5) // 기존 고정 데이터
        data = result.data
        hasMore = result.hasMore
      }

      if (pageNum === 0) {
        setCitySections(data)
      } else {
        setCitySections(prev => [...prev, ...data])
      }

      setHasMore(hasMore)
      setPage(pageNum)
    } catch (error) {
      console.error('데이터 로드 오류:', error)
    } finally {
      setLoading(false)
      loadingRef.current = false
    }
  }, [session])

  // 필터 데이터 로드 함수
  const loadFilterData = useCallback(async () => {
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

      // 지역 목록 로드
      const regionsResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/regions`)
      if (regionsResponse.ok) {
        const regionsData = await regionsResponse.json()
        setRegions(regionsData.regions)
      }

      // 카테고리 목록 로드
      const categoriesResponse = await fetch(`${API_BASE_URL}/api/v1/attractions/categories`)
      if (categoriesResponse.ok) {
        const categoriesData = await categoriesResponse.json()
        setCategories(categoriesData.categories)
      }
    } catch (error) {
      console.error('필터 데이터 로드 오류:', error)
    }
  }, [])

  // 필터링된 관광지 로드 함수
  const loadFilteredAttractions = useCallback(async (pageNum: number) => {
    if (loadingRef.current) return

    loadingRef.current = true
    setLoading(true)
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

      let filteredCitySections: CitySection[] = []

      // 지역만 선택된 경우: 카테고리별로 구분된 섹션 표시
      if (selectedRegion && !selectedCategory) {
        const params = new URLSearchParams({
          region: selectedRegion,
          page: pageNum.toString(),
          limit: '8'
        })

        const url = `${API_BASE_URL}/api/v1/attractions/filtered-by-category?${params}`
        console.log('Filtered by category URL:', url)

        const response = await fetch(url)

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const result = await response.json()

        // 카테고리별 섹션을 CitySection 형식으로 변환
        result.categorySections.forEach((categorySection: any, index: number) => {
          filteredCitySections.push({
            id: `category-${selectedRegion}-${categorySection.category}-${index}`,
            cityName: selectedRegion,
            description: `${selectedRegion}의 ${categorySection.categoryName}`,
            region: selectedRegion,
            attractions: categorySection.attractions,
            recommendationScore: 90 - index * 5
          })
        })

        setHasMore(result.hasMore)
      }
      // 지역과 카테고리 모두 선택된 경우: 기존 방식 사용
      else if (selectedRegion && selectedCategory) {
        const params = new URLSearchParams({
          page: pageNum.toString(),
          limit: '3'
        })

        params.append('region', selectedRegion)
        params.append('category', selectedCategory)

        const url = `${API_BASE_URL}/api/v1/attractions/filtered?${params}`
        console.log('Filtered attractions URL:', url)

        const response = await fetch(url)

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const result = await response.json()

        // 지역별로 그룹화
        const groupedByRegion: { [key: string]: any[] } = {}

        result.attractions.forEach((attraction: any) => {
          const region = attraction.region || '기타'
          if (!groupedByRegion[region]) {
            groupedByRegion[region] = []
          }
          groupedByRegion[region].push(attraction)
        })

        // 각 지역별로 CitySection 생성
        Object.entries(groupedByRegion).forEach(([region, attractions], index) => {
          const cityName = attractions[0]?.city?.name || region
          filteredCitySections.push({
            id: `filtered-${region}-${index}`,
            cityName: cityName,
            description: `${region}의 ${categories.find(c => c.id === selectedCategory)?.name || selectedCategory}`,
            region: region,
            attractions: attractions.slice(0, 8),
            recommendationScore: 85 - index * 5
          })
        })

        setHasMore(result.hasMore)
      }

      if (pageNum === 0) {
        setCitySections(filteredCitySections)
      } else {
        setCitySections(prev => [...prev, ...filteredCitySections])
      }

      setPage(pageNum)
    } catch (error) {
      console.error('필터링된 데이터 로드 오류:', error)
    } finally {
      setLoading(false)
      loadingRef.current = false
    }
  }, [selectedRegion, selectedCategory, categories])

  // 초기 데이터 로드 및 세션 상태 변경 시 데이터 재로드
  useEffect(() => {
    loadRecommendedCities(0)
    loadFilterData()
    
    // 세션이 있으면 actionTracker에 사용자 ID 설정
    if (session?.user?.id) {
      actionTracker.setUserId(session.user.id)
    }
  }, [loadRecommendedCities, loadFilterData, session])

  // 필터 변경 시 데이터 다시 로드
  useEffect(() => {
    if (selectedRegion || selectedCategory) {
      loadFilteredAttractions(0)
    } else {
      // 필터가 없을 때는 로그인 상태에 따라 적절한 데이터 로드
      loadRecommendedCities(0)
    }
  }, [selectedRegion, selectedCategory, loadFilteredAttractions, loadRecommendedCities])

  // 필터 패널 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element
      if (showFilters &&
        !target.closest('.filter-panel') &&
        !target.closest('input[placeholder="어디로 떠나볼까요?"]')) {
        setShowFilters(false)
      }
    }

    if (showFilters) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showFilters])

  // 무한 스크롤 감지
  const lastElementRef = useCallback((node: HTMLDivElement | null) => {
    if (loadingRef.current) return
    if (observerRef.current) observerRef.current.disconnect()

    observerRef.current = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasMore && !loadingRef.current) {
        // 필터가 적용된 상태가 아닐 때만 무한 스크롤 동작
        if (!selectedRegion && !selectedCategory) {
          loadRecommendedCities(page + 1)
        }
      }
    })

    if (node) observerRef.current.observe(node)
  }, [hasMore, page, selectedRegion, selectedCategory, loadRecommendedCities])

  const handleSearch = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!searchQuery.trim()) return

    setIsSearching(true)
    setSearchError(null)

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/attractions/search?q=${encodeURIComponent(searchQuery)}`)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const results = await response.json()

      // 중복 제거: 같은 이름과 주소를 가진 항목들을 제거
      const uniqueResults = (results.results || []).filter((item: any, index: number, array: any[]) => {
        return array.findIndex((other: any) =>
          other.name === item.name &&
          other.address === item.address
        ) === index
      })

      setSearchResults(uniqueResults)
      setShowSearchResults(true)

      // 검색 트래킹
      actionTracker.trackSearch(searchQuery, 'general', uniqueResults.length)

    } catch (error) {
      console.error('검색 오류:', error)
      setSearchError('검색 중 오류가 발생했습니다. 다시 시도해주세요.')
    } finally {
      setIsSearching(false)
    }
  }

  // 검색 결과 숨기기 함수
  const handleClearSearch = () => {
    setSearchQuery('')
    setSearchResults([])
    setShowSearchResults(false)
    setSearchError(null)
  }

  // 챗봇 관련 함수
  const handleChatSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!chatMessage.trim()) return

    // 사용자 메시지 추가
    const userMessage = {
      id: Date.now(),
      type: 'user',
      message: chatMessage,
      timestamp: new Date()
    }

    setChatMessages(prev => [...prev, userMessage])
    setChatMessage('')

    // 간단한 봇 응답 (실제로는 API 호출)
    setTimeout(() => {
      const botResponse = {
        id: Date.now() + 1,
        type: 'bot',
        message: '여행 계획 작성을 도와드릴게요! 어떤 지역으로 여행을 계획하고 계신가요?',
        timestamp: new Date()
      }
      setChatMessages(prev => [...prev, botResponse])
    }, 1000)
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-slate-200 overflow-y-auto no-scrollbar pb-20">
      {/* Logo */}
      <div className="text-center mt-20 mb-8">
        <h1 className="text-6xl font-extrabold text-[#3E68FF] tracking-tight">witple</h1>
      </div>

      {/* Search Bar */}
      <div className="px-4 mb-16 mt-20">
        <form onSubmit={handleSearch} className="relative w-[90%] mx-auto">
          <input
            type="text"
            placeholder="어디로 떠나볼까요?"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setShowFilters(true)}
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
            disabled={isSearching}
            className="absolute right-5 top-1/2 -translate-y-1/2 p-1 text-[#6FA0E6] hover:text-white transition disabled:opacity-50"
            aria-label="검색"
          >
            {isSearching ? (
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#6FA0E6]"></div>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            )}
          </button>
        </form>
      </div>

      {/* Search Results */}
      {showSearchResults && (
        <div className="px-4 mb-8">
          <div className="w-[90%] mx-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-white">
                &apos;{searchQuery}&apos; 검색 결과 ({searchResults.length}개)
              </h2>
              <button
                onClick={handleClearSearch}
                className="text-[#6FA0E6] hover:text-white transition-colors text-sm"
              >
                ✕ 닫기
              </button>
            </div>

            {/* 스크롤 가능한 검색 결과 컨테이너 - 화면의 절반 높이로 제한 */}
            <div
              className="overflow-y-auto bg-[#0F1A31]/30 rounded-2xl p-4 scrollbar-thin scrollbar-thumb-[#3E68FF] scrollbar-track-transparent"
              style={{
                height: '50vh',
                maxHeight: '400px',
                scrollbarWidth: 'thin',
                scrollbarColor: '#3E68FF transparent'
              }}
            >
              {searchError && (
                <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-4 mb-4">
                  <p className="text-red-300">{searchError}</p>
                </div>
              )}

              {searchResults.length === 0 && !isSearching && !searchError ? (
                <div className="text-center py-8">
                  <div className="text-6xl mb-4">🔍</div>
                  <p className="text-gray-400 text-lg mb-2">검색 결과가 없습니다</p>
                  <p className="text-gray-500 text-sm">다른 키워드로 검색해보세요</p>
                </div>
              ) : (
                <div className="space-y-4 pr-2">
                  {searchResults.map((result, index) => (
                    <div
                      key={`${result.name}-${result.address}-${index}`}
                      onClick={() => {
                        // 클릭 트래킹
                        actionTracker.trackCardClick(result.id, result.category || 'general', index + 1)
                        router.push(`/attraction/${result.id}`)
                      }}
                      className="bg-gray-800/50 hover:bg-gray-700/50 p-4 rounded-2xl cursor-pointer transition-colors border border-gray-700/50"
                    >
                      <div className="flex items-start space-x-4">
                        {/* 카테고리 아이콘 */}
                        <div className="flex-shrink-0 w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center">
                          <span className="text-2xl">
                            {result.category === 'nature' && '🌲'}
                            {result.category === 'restaurants' && '🍽️'}
                            {result.category === 'shopping' && '🛍️'}
                            {result.category === 'accommodation' && '🏨'}
                            {result.category === 'humanities' && '🏛️'}
                            {result.category === 'leisure_sports' && '⚽'}
                          </span>
                        </div>

                        {/* 정보 */}
                        <div className="flex-1 min-w-0">
                          <h3 className="text-white font-semibold text-lg mb-1 truncate">
                            {result.name}
                          </h3>
                          <p className="text-gray-300 text-sm mb-2 line-clamp-2">
                            {result.overview}
                          </p>
                          <div className="flex items-center space-x-4 text-xs text-gray-400">
                            <div className="flex items-center space-x-1">
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                              <span>{result.address}</span>
                            </div>
                            <div className="flex items-center space-x-1">
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                              </svg>
                              <span className="capitalize">{result.category}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Filter Section - 검색창 포커스 시에만 표시 */}
      {showFilters && !showSearchResults && (
        <div className="px-4 mb-16">
          <div className="w-[90%] mx-auto">
            {/* Filter Panel */}
            <div className="bg-[#0F1A31]/50 rounded-2xl p-4 space-y-4 filter-panel">
              {/* Clear Filters Button */}
              {(selectedRegion || selectedCategory) && (
                <div className="flex justify-end mb-2">
                  <button
                    onClick={() => {
                      setSelectedRegion('')
                      setSelectedCategory('')
                      // 필터 초기화 후 로그인 상태에 따라 적절한 데이터 로드
                      setTimeout(() => {
                        loadRecommendedCities(0)
                      }, 100)
                    }}
                    className="text-[#6FA0E6] hover:text-white text-sm transition-colors"
                  >
                    필터 초기화
                  </button>
                </div>
              )}
              {/* Region Filter */}
              <div>
                <label className="block text-[#94A9C9] text-sm font-medium mb-2">지역</label>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setSelectedRegion('')}
                    className={`px-3 py-1 rounded-full text-sm transition-colors ${!selectedRegion
                      ? 'bg-[#3E68FF] text-white'
                      : 'bg-[#1F3C7A]/30 text-[#6FA0E6] hover:bg-[#1F3C7A]/50'
                      }`}
                  >
                    전체
                  </button>
                  {regions.map((region) => (
                    <button
                      key={region}
                      onClick={() => setSelectedRegion(region)}
                      className={`px-3 py-1 rounded-full text-sm transition-colors ${selectedRegion === region
                        ? 'bg-[#3E68FF] text-white'
                        : 'bg-[#1F3C7A]/30 text-[#6FA0E6] hover:bg-[#1F3C7A]/50'
                        }`}
                    >
                      {region}
                    </button>
                  ))}
                </div>
              </div>

              {/* Category Filter */}
              <div>
                <label className="block text-[#94A9C9] text-sm font-medium mb-2">카테고리</label>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setSelectedCategory('')}
                    className={`px-3 py-1 rounded-full text-sm transition-colors ${!selectedCategory
                      ? 'bg-[#3E68FF] text-white'
                      : 'bg-[#1F3C7A]/30 text-[#6FA0E6] hover:bg-[#1F3C7A]/50'
                      }`}
                  >
                    전체
                  </button>
                  {categories.map((category) => (
                    <button
                      key={category.id}
                      onClick={() => setSelectedCategory(category.id)}
                      className={`px-3 py-1 rounded-full text-sm transition-colors ${selectedCategory === category.id
                        ? 'bg-[#3E68FF] text-white'
                        : 'bg-[#1F3C7A]/30 text-[#6FA0E6] hover:bg-[#1F3C7A]/50'
                        }`}
                    >
                      {category.name}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 추천 도시별 명소 섹션 (무한 스크롤) - 검색 결과가 표시될 때는 숨김 */}
      {!showSearchResults && (
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
                categorySections={citySection.categorySections}
                onAttractionClick={(attractionId, attraction, position) => {
                  // 카드 클릭 트래킹
                  if (attraction) {
                    actionTracker.trackCardClick(attractionId, attraction.category || 'general', position)
                  }
                  router.push(`/attraction/${attractionId}`)
                }}
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
              {session ? (
                <>
                  <p className="text-[#94A9C9] text-lg mb-4">맞춤 추천을 준비하고 있어요!</p>
                  <p className="text-[#6FA0E6] text-sm">선호도 설정이나 여행지 탐색 후 다시 확인해보세요 ✨</p>
                </>
              ) : (
                <p className="text-[#94A9C9] text-lg">추천할 여행지를 준비 중입니다...</p>
              )}
            </div>
          )}
        </main>
      )}

      {/* Chatbot Icon - Fixed Position */}
      <button
        onClick={() => setShowChatbot(true)}
        className="fixed bottom-24 right-6 z-50 w-16 h-16 bg-[#3E68FF] hover:bg-[#4C7DFF] rounded-full flex items-center justify-center shadow-lg transition-all duration-200 hover:scale-110"
      >
        <img
          src="/images/chat_icon.svg"
          alt="챗봇"
          className="w-12 h-12"
        />
      </button>

      {/* Chatbot Modal */}
      {showChatbot && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-md h-[600px] flex flex-col overflow-hidden shadow-2xl">
            {/* Header */}
            <div className="bg-[#3E68FF] p-4 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <img
                  src="/images/chat_icon.svg"
                  alt="챗봇"
                  className="w-12 h-12 bg-white rounded-full p-2"
                />
                <div>
                  <h3 className="text-white font-semibold">쿼카</h3>
                  <p className="text-blue-100 text-sm">여행 마스터</p>
                </div>
              </div>
              <button
                onClick={() => setShowChatbot(false)}
                className="text-white hover:text-blue-200 text-xl font-bold w-8 h-8 flex items-center justify-center"
              >
                ×
              </button>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
              {chatMessages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] ${msg.type === 'user'
                    ? 'bg-[#3E68FF] text-white'
                    : 'bg-white border border-gray-200'
                    } rounded-2xl px-4 py-2 shadow-sm`}>
                    <p className={`text-sm ${msg.type === 'user' ? 'text-white' : 'text-gray-800'}`}>
                      {msg.message}
                    </p>
                  </div>
                </div>
              ))}
            </div>


            {/* Input */}
            <div className="p-4 border-t border-gray-200 bg-white">
              <form onSubmit={handleChatSubmit} className="flex items-center space-x-2">
                <input
                  type="text"
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  placeholder="메시지를 입력하세요..."
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-[#3E68FF] focus:border-transparent text-gray-800"
                />
                <button
                  type="submit"
                  disabled={!chatMessage.trim()}
                  className="w-10 h-10 bg-[#3E68FF] hover:bg-[#4C7DFF] disabled:bg-gray-300 rounded-full flex items-center justify-center transition-colors"
                >
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      <BottomNavigation />
    </div>
  )
}

/** 추천 도시별 명소 섹션 컴포넌트 */
function SectionCarousel({
  title,
  cityName,
  attractions,
  categorySections,
  onAttractionClick,
}: {
  title: string
  cityName: string
  attractions: { id: string; name: string; description: string; imageUrl: string; rating: number; category: string }[]
  categorySections?: Array<{ category: string; categoryName: string; attractions: any[]; total: number }>
  onAttractionClick: (attractionId: string, attraction?: any, position?: number) => void
}) {
  return (
    <section aria-label={`${cityName} ${title}`} className="w-full">
      {/* 도시 제목과 추천 점수 */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-2xl md:text-3xl font-semibold text-[#94A9C9]">
            {title}
          </h2>
          {/* <div className="flex items-center mt-2 space-x-2">
            <span className="text-[#3E68FF] font-bold text-lg">{cityName}</span>
          </div> */}
        </div>
      </div>

      {/* 카테고리별 섹션이 있는 경우 */}
      {categorySections && categorySections.length > 0 ? (
        <div className="space-y-8">
          {categorySections.map((categorySection, categoryIndex) => (
            <div key={`${categorySection.category}-${categoryIndex}`}>
              {/* 카테고리 제목 */}
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold text-[#3E68FF]">
                  {categorySection.categoryName}
                </h3>
                <span className="text-sm text-[#6FA0E6]">
                  {categorySection.total}개 장소
                </span>
              </div>

              {/* 카테고리별 장소 캐러셀 */}
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
                  {categorySection.attractions.map((attraction, index) => (
                    <AttractionCard
                      key={attraction.id}
                      attraction={attraction}
                      position={index + 1}
                      onAttractionClick={onAttractionClick}
                    />
                  ))}
                </div>

                {/* 좌/우 가장자리 페이드 */}
                <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-[#0B1220] to-transparent" />
                <div className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-[#0B1220] to-transparent" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* 기존 방식: 모든 장소를 하나의 캐러셀로 표시 */
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
            {attractions.map((attraction, index) => (
              <AttractionCard
                key={attraction.id}
                attraction={attraction}
                position={index + 1}
                onAttractionClick={onAttractionClick}
              />
            ))}
          </div>

          {/* 좌/우 가장자리 페이드 */}
          <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-[#0B1220] to-transparent" />
          <div className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-[#0B1220] to-transparent" />
        </div>
      )}
    </section>
  )
}

/** 관광지 카드 컴포넌트 */
function AttractionCard({
  attraction,
  position,
  onAttractionClick,
}: {
  attraction: { id: string; name: string; description: string; imageUrl: string; rating: number; category: string }
  position?: number
  onAttractionClick: (attractionId: string, attraction?: any, position?: number) => void
}) {
  return (
    <figure
      className="
        snap-start shrink-0
        rounded-[28px] overflow-hidden
        bg-[#0F1A31] ring-1 ring-white/5
        w-[78%] xs:w-[70%] sm:w-[320px]
        cursor-pointer hover:ring-[#3E68FF]/50 transition-all duration-300
        group
      "
      onClick={() => onAttractionClick(attraction.id, attraction, position)}
    >
      {/* 이미지 영역 */}
      <div className="aspect-[4/3] relative overflow-hidden">
        {attraction.imageUrl && attraction.imageUrl !== "/images/default.jpg" && attraction.imageUrl !== null ? (
          <>
            {/* 이미지 로딩 인디케이터 */}
            <div className="absolute inset-0 bg-gray-800 flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF]"></div>
            </div>

            <img
              src={attraction.imageUrl}
              alt={attraction.name}
              className="w-full h-full object-cover opacity-0 transition-opacity duration-300"
              onLoad={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.opacity = '1';
                const loadingIndicator = target.previousElementSibling as HTMLElement;
                if (loadingIndicator) loadingIndicator.style.display = 'none';
              }}
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                const loadingIndicator = target.previousElementSibling as HTMLElement;
                if (loadingIndicator) loadingIndicator.style.display = 'none';
                const fallback = target.nextElementSibling as HTMLElement;
                if (fallback) fallback.style.display = 'flex';
              }}
            />

            {/* 이미지 로드 실패 시 대체 UI */}
            <div
              className="w-full h-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center"
              style={{ display: 'none' }}
            >
              <span className="text-white text-lg opacity-70 text-center px-2">
                {attraction.name}
              </span>
            </div>
          </>
        ) : (
          /* 이미지가 없는 경우 기본 UI */
          <div className="w-full h-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
            <span className="text-white text-lg opacity-70 text-center px-2">
              {attraction.name}
            </span>
          </div>
        )}
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
