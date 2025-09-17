'use client'

import React, { useState, useEffect, useCallback, FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { fetchPersonalizedRegionCategories, fetchAllRegionsAllCategories, type CitySection } from '../lib/dummyData'
import { BottomNavigation } from '../components'
import { trackClick } from '../utils/actionTracker'
import { useActionTrackerSession } from '../hooks/useActionTrackerSession'
import { useChatbot } from '../components/ChatbotProvider'

export default function Home() {
  const router = useRouter()
  const { session, status } = useActionTrackerSession()
  const { setIsAppLoading } = useChatbot()
  const [searchQuery, setSearchQuery] = useState('')
  const [citySections, setCitySections] = useState<CitySection[]>([])
  const [popularSections, setPopularSections] = useState<CitySection[]>([])
  const [availableRegions, setAvailableRegions] = useState<string[]>([])
  const [selectedRegion, setSelectedRegion] = useState<string>('서울')
  const [showRegionModal, setShowRegionModal] = useState<boolean>(false)
  const [loading, setLoading] = useState(false)
  const [userInfo, setUserInfo] = useState<{ name: string, preferences: any } | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)

  // 검색 관련 상태
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showSearchResults, setShowSearchResults] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  // 지역 필터 상태
  const [selectedRegionFilter, setSelectedRegionFilter] = useState<string>('all')

  // 선택된 지역에 따라 인기 섹션 필터링
  const filteredPopularSections = selectedRegionFilter === 'all'
    ? popularSections
    : popularSections.filter(section =>
        section.region === selectedRegionFilter || section.cityName === selectedRegionFilter
      )


  // 사용자 정보 및 여행 취향 로드 함수
  const loadUserInfo = useCallback(async () => {
    if (!session || !(session as any).backendToken) {
      setUserInfo(null)
      return null
    }

    // 기본 사용자 정보 설정 (세션 기반)
    const defaultUserInfo = {
      name: session.user?.name || '사용자',
      preferences: null,
      bookmarkCount: 0  // 기본값 0
    }
    setUserInfo(defaultUserInfo)

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

      // 2초 타임아웃으로 빠른 실패 처리
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('API 요청 타임아웃')), 2000)
      )

      // 사용자 기본 정보 가져오기
      const userResponsePromise = fetch(`${API_BASE_URL}/api/v1/profile/me`, {
        headers: {
          'Authorization': `Bearer ${(session as any).backendToken}`
        }
      })

      const userResponse = await Promise.race([userResponsePromise, timeoutPromise]) as Response

      if (userResponse.ok) {
        try {
          const userData = await userResponse.json()

          // Profile API에서 이미 preferences 정보를 포함하므로 별도 호출 불필요
          // userData에 이미 persona, priority, accommodation, exploration이 포함되어 있음
          const preferences = {
            persona: userData.persona,
            priority: userData.priority,
            accommodation: userData.accommodation,
            exploration: userData.exploration
          }

          // 북마크 수를 별도로 가져오기 (프로필 API에 포함되지 않음)
          let bookmarkCount = 0
          try {
            const bookmarkResponse = await fetch(`${API_BASE_URL}/api/v1/saved-locations?page=0&limit=1`, {
              headers: {
                'Authorization': `Bearer ${(session as any).backendToken}`
              }
            })

            if (bookmarkResponse.ok) {
              const bookmarkData = await bookmarkResponse.json()
              bookmarkCount = bookmarkData.total || 0
              // console.log('사용자 북마크 수:', bookmarkCount)
            }
          } catch (bookmarkError) {
            console.warn('북마크 수 확인 오류:', bookmarkError)
          }

          const newUserInfo = {
            name: userData.name || defaultUserInfo.name,
            preferences: preferences,
            bookmarkCount: bookmarkCount  // 북마크 수 추가
          }

          setUserInfo(newUserInfo)

          // 사용자 정보 설정 후 바로 선호도 체크 (추가 렌더링 방지)
          setTimeout(() => checkUserPreferences(preferences), 0)

          return newUserInfo  // 새로 로드된 사용자 정보 반환
        } catch (jsonError) {
          console.warn('사용자 프로필 JSON 파싱 오류:', jsonError)
          // JSON 파싱 실패 시 기본 정보 유지
          return defaultUserInfo
        }
      } else {
        console.warn(`사용자 프로필 정보 로드 실패 (${userResponse.status}): API 서버 오류 또는 권한 없음`)
        // API 오류 시에도 기본 정보는 유지됨 (이미 설정함)
        return defaultUserInfo
      }
    } catch (error) {
      console.warn('사용자 정보 로드 전체 오류:', error instanceof Error ? error.message : String(error))
      // 전체 오류 시에도 기본 정보는 유지됨 (이미 설정함)
      return defaultUserInfo
    }
  }, [session])

  // 추천 도시 데이터 로드 함수
  const loadRecommendedCities = useCallback(async (currentUserInfo?: { name: string, preferences: any } | null, region?: string) => {
    if (loading) {
      console.log('이미 로딩 중이므로 중복 요청 방지')
      return
    }


      // console.log('추천 데이터 로드 시작 - 세션:', !!session, ', 지역:', region)
    setLoading(true)

    // 10초 타임아웃 설정 (개인화 추천 벡터 계산 시간 고려)
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('API 요청 타임아웃')), 10000)
    )

    try {
      // 백엔드 설정을 사용하여 API 호출 (모든 사용자 v2 API 사용)
      const dataPromise = fetchPersonalizedRegionCategories(undefined, currentUserInfo || userInfo, session, region)

      const result = await Promise.race([dataPromise, timeoutPromise]) as { data: CitySection[] }

      // 데이터 처리 - 지역 필터 적용 및 백엔드 설정 반영
      let filteredData = result.data

      // 지역 필터가 설정되어 있으면 해당 지역 데이터만 필터링
      if (region && region !== '전체') {
        // console.log('지역 필터링 전 데이터:', result.data.length, '개 섹션')
        // console.log('전체 지역 목록:', result.data.map(s => `${s.cityName}(${s.region})`))
        // console.log('필터 대상 지역:', region)

        filteredData = result.data.filter(section => {
          // 더 유연한 지역 매칭
          const regionMatches = section.region === region ||
                               section.cityName === region ||
                               section.region?.includes(region) ||
                               section.cityName?.includes(region) ||
                               region.includes(section.region || '') ||
                               region.includes(section.cityName || '')

          // console.log(`섹션 ${section.cityName}(${section.region}): ${regionMatches ? '포함' : '제외'}`)
          return regionMatches
        })

        // console.log('지역 필터링 후 데이터:', filteredData.length, '개 섹션')

        // 필터링 후 데이터가 없으면 전체 데이터 사용 (백엔드가 지역 필터를 지원하지 않을 경우)
        if (filteredData.length === 0) {
          console.warn('지역 필터링 결과가 비어있음. 백엔드 API가 지역 필터를 지원하지 않는 것 같습니다. 전체 데이터 사용.')
          filteredData = result.data
        }
      } else {
        console.log('지역 필터 없음, 전체 데이터 사용:', result.data.length, '개 섹션')
      }

      const processedData = filteredData.map(section => {
        // categorySections가 있으면 그대로 사용 (백엔드에서 이미 처리됨)
        if (section.categorySections && section.categorySections.length > 0) {
          console.log(`섹션 ${section.cityName}: 카테고리별 ${section.categorySections.length}개 카테고리`)

          // 각 카테고리의 attractions 수 로깅
          section.categorySections.forEach(cat => {
            console.log(`  - ${cat.categoryName}: ${cat.attractions?.length || 0}개`)
            // 🔥 각 attraction의 카테고리 정보도 로깅
            cat.attractions?.slice(0, 3).forEach(attraction => {
              console.log(`    • ${attraction.name} (${attraction.category})`)
            })
          })

          return {
            ...section,
            attractions: [], // categorySections를 사용하므로 비워둠
            categorySections: section.categorySections
          }
        }

        // attractions만 있는 경우의 fallback 처리
        let attractions = section.attractions || []

        // 백엔드에서 이미 제한된 데이터이므로 그대로 사용
        let filteredAttractions = attractions

        // console.log(`섹션 ${section.cityName}: 일반 형태 ${attractions.length}개 (백엔드에서 이미 제한됨)`)

        return {
          ...section,
          attractions: filteredAttractions,
          categorySections: undefined
        }
      })

      // console.log('추천 데이터 로드 완료:', processedData.length, '개 섹션')

      // 모든 섹션이 비어있는지 체크 (categorySections 포함)
      const totalAttractions = processedData.reduce((sum, section) => {
        if (section.categorySections && section.categorySections.length > 0) {
          // categorySections가 있으면 해당 attractions 수 계산
          return sum + section.categorySections.reduce((catSum, cat) =>
            catSum + (cat.attractions?.length || 0), 0)
        }
        return sum + (section.attractions?.length || 0)
      }, 0)

      // console.log('총 추천 장소 수:', totalAttractions)

      const finalData = totalAttractions === 0 ? result.data : processedData

      if (totalAttractions === 0) {
        console.warn('필터링 후 모든 데이터가 사라짐, 원본 데이터로 대체')
        // console.log('🔄 원본 데이터로 setCitySections 호출:', result.data.length, '개 섹션')
      } else {
        // console.log('🔄 처리된 데이터로 setCitySections 호출:', processedData.length, '개 섹션')
      }

      setCitySections(finalData)

      // 사용 가능한 지역 추출 및 업데이트
      const regions = Array.from(new Set(finalData.map(section => section.region || section.cityName || '')))
      .filter(region => region) // 빈 문자열 제거
      .sort()

      setAvailableRegions(regions)
    } catch (error) {
      console.warn('데이터 로드 오류:', error instanceof Error ? error.message : String(error))
      setCitySections([])
    } finally {
      setLoading(false)
    }
  }, [session]) // userInfo 의존성 제거

  // 모든 지역 모든 카테고리 섹션 로드 함수 (개별 API 호출 방식, 우선순위 태그 필터링 포함)
  const loadAllRegionsAllCategories = useCallback(async () => {
    console.log('모든 지역 모든 카테고리 섹션 로드 시작')

    try {
      // 🔑 세션을 전달하여 우선순위 태그 필터링 적용
      const result = await fetchAllRegionsAllCategories(10, 6, session)
      setPopularSections(result.data)
      setAvailableRegions(result.availableRegions)

      console.log(`모든 지역 모든 카테고리 섹션 로드 완료: ${result.data.length}개 지역`)
    } catch (error) {
      console.warn('모든 지역 모든 카테고리 섹션 로드 오류:', error)
      setPopularSections([])
    }
  }, [])



  // 지역 변경 핸들러 (맛집 섹션은 모든 지역을 보여주므로 불필요하지만 호환성 유지)
  const handleRegionChange = useCallback(async (region: string) => {
    console.log('🏷️ 지역 변경 요청:', region)
    setSelectedRegion(region)
    setShowRegionModal(false) // 모달 닫기

    console.log('🔄 추천 데이터 다시 로드 시작...')

    // 추천 데이터만 다시 로드 (맛집 섹션은 모든 지역을 표시하므로 지역별 로드 불필요)
    try {
      await loadRecommendedCities(userInfo, region)
      console.log('✅ 추천 데이터 다시 로드 완료')
    } catch (error) {
      console.error('❌ 데이터 다시 로드 실패:', error)
    }
  }, [loadRecommendedCities, userInfo])

  // 사용자 선호도 체크 (profile API 데이터 기반)
  const checkUserPreferences = useCallback(async (userPreferences?: any) => {
    if (!session || !(session as any).backendToken) {
      return
    }

    try {
      // 개발용: URL에 reset_preferences=true가 있으면 플래그 초기화
      if (typeof window !== 'undefined' && window.location.search.includes('reset_preferences=true')) {
        localStorage.removeItem('preferences_completed')
      }

      // profile API에서 받은 preferences 데이터로 확인
      const hasPreferences = userPreferences && (
        userPreferences.persona ||
        userPreferences.priority ||
        userPreferences.accommodation ||
        userPreferences.exploration
      )

      if (!hasPreferences) {
        // 선호도가 없으면 설정 페이지로 이동
        console.log('사용자 선호도 설정 필요, 설정 페이지로 이동')
        router.push('/preferences')
        return
      } else {
        // 선호도가 있으면 완료 플래그 저장
        localStorage.setItem('preferences_completed', 'true')
        // console.log('사용자 선호도 설정 완료 확인')
      }
    } catch (error) {
      console.warn('선호도 체크 오류:', error instanceof Error ? error.message : String(error))
      // 에러 시에도 메인 페이지는 정상 작동
    }
  }, [session, router])


  // 로딩 상태를 전역 상태와 동기화
  useEffect(() => {
    setIsAppLoading(loading)
  }, [loading, setIsAppLoading])

  // 세션 상태 변경 시 초기화 플래그 리셋 (실제 사용자 변경시에만)
  useEffect(() => {
    // 로그인/로그아웃 시에만 리셋 (이메일이 실제로 변경되는 경우만)
    if (status !== 'loading') {
      const currentEmail = session?.user?.email
      const previousEmail = sessionStorage.getItem('previous_user_email')

      if (previousEmail && previousEmail !== currentEmail) {
        // 실제로 다른 사용자로 로그인한 경우에만 리셋
        setIsInitialized(false)
        sessionStorage.setItem('previous_user_email', currentEmail || '')
      } else if (!previousEmail && currentEmail) {
        // 첫 로그인인 경우 이메일만 저장하고 리셋하지 않음
        sessionStorage.setItem('previous_user_email', currentEmail)
      } else if (!currentEmail) {
        // 로그아웃한 경우
        sessionStorage.removeItem('previous_user_email')
        setIsInitialized(false)
      }
    }
  }, [session?.user?.email, status])

  // 사용자 정보 로드 및 추천 데이터 로드 (순차 처리) - 한 번만 실행
  useEffect(() => {
    if (status !== 'loading' && !isInitialized) {
      setIsInitialized(true)
      // console.log('초기화 시작 - 세션:', !!session)

      if (session) {
        // 로그인 상태: 사용자 정보 먼저 로드 후 추천 데이터 로드
        const initializeUser = async () => {
          try {
            // 먼저 사용자 정보를 로드하고, 그 정보를 기반으로 선호도 체크
            const loadedUserInfo = await loadUserInfo()

            // 사용자 정보 로드 후에 추천 데이터 로드 (병렬 처리 대신 순차 처리로 안정성 확보)
            await loadRecommendedCities(loadedUserInfo, selectedRegion)

            // 모든 지역 모든 카테고리 섹션 로드 (모든 로그인 사용자)
            await loadAllRegionsAllCategories()

            // console.log('로그인 사용자 초기화 완료')
          } catch (error) {
            console.warn('로그인 사용자 초기화 오류:', error)
          }
        }

        initializeUser()
      } else {
        // 비로그인 상태: 추천 데이터와 모든 지역 모든 카테고리 섹션 로드
        Promise.all([
          loadRecommendedCities(null, selectedRegion),
          loadAllRegionsAllCategories()
        ]).then(() => {
          // console.log('비로그인 사용자 초기화 완료')
        }).catch(error => {
          console.warn('비로그인 사용자 초기화 오류:', error)
        })
      }
    }
  }, [status, isInitialized])

  // 검색 처리 함수
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

  return (
    <div className="min-h-screen bg-[#0B1220] text-slate-200 pb-20">
      {/* Header with Logo and Search */}
      <div className="sticky top-0 z-40 bg-[#0B1220] flex items-center gap-4 pr-4 pl-6 py-4 mb-10">
        <h1 className="text-[2.75rem] font-logo text-[#3E68FF] tracking-wide">WITPLE</h1>

        {/* 검색창 */}
        <div className="flex-1 max-w-md search-container">
          <form onSubmit={handleSearch} className="relative">
            <input
              type="text"
              placeholder="여행지를 검색해보세요"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full py-2 pr-8 pl-4 bg-transparent border-0 border-b border-[#252F42] text-slate-200 placeholder-slate-200/20 focus:outline-none focus:border-[#3E68FF] transition-colors"
            />

            {/* 검색 아이콘/버튼 */}
            <button
              type="submit"
              disabled={isSearching}
              className="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 text-[#94A9C9] hover:text-white transition disabled:opacity-50"
              aria-label="검색"
            >
              {isSearching ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[#94A9C9]"></div>
              ) : (
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              )}
            </button>
          </form>
        </div>
      </div>

      {/* 검색 결과 */}
      {showSearchResults && (
        <div className="px-5 mb-4">
          <div className="max-w-4xl mx-auto">
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

            {/* 스크롤 가능한 검색 결과 컨테이너 */}
            <div
              className="overflow-y-auto bg-[#0F1A31]/30 rounded-2xl scrollbar-thin scrollbar-thumb-[#3E68FF] scrollbar-track-transparent"
              style={{
                height: '70vh',
                maxHeight: '700px',
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
                      onClick={() => router.push(`/attraction/${result.id}`)}
                      className="bg-gray-800/50 hover:bg-gray-700/50 p-4 rounded-2xl cursor-pointer transition-colors border border-gray-700/50"
                    >
                      <div className="flex items-start space-x-4">
                        {/* 정보 */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between mb-1">
                            <h3 className="text-white font-semibold text-lg truncate flex-1 mr-2">
                              {result.name}
                            </h3>
                            <span className="bg-blue-500/20 text-blue-300 px-2 py-1 rounded-full text-xs font-medium shrink-0">
                              {getCategoryName(result.category?.trim()) || result.category}
                            </span>
                          </div>
                          <p className="text-gray-300 text-sm mb-2 line-clamp-2">
                            {result.overview}
                          </p>
                          <div className="flex items-center text-xs text-gray-400">
                            <div className="flex items-center space-x-1">
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                              <span>{result.address}</span>
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

      {/* Main Card 섹션 - 로그인/비로그인 모두 표시 (검색 결과가 표시될 때는 숨김) */}
      {!showSearchResults && (citySections.length > 0 || popularSections.length > 0) && (
        <div className="px-5 mb-12">
          <MainCard
            attraction={
              citySections[0]?.categorySections?.[0]?.attractions?.[0] ||
              citySections[0]?.attractions?.[0] ||
              popularSections[0]?.attractions?.[0]
            }
            onAttractionClick={(attractionId) => router.push(`/attraction/${attractionId}`)}
          />
        </div>
      )}

      {/* 추천 명소 섹션 (검색 결과가 표시될 때는 숨김) */}
      {!showSearchResults && (
        <main className="pl-[20px] pr-0 pb-24 space-y-12">
          {/* 추천 섹션 - 로그인/비로그인에 따라 다르게 표시 */}
          {citySections.length > 0 && (
          <div>
            {session ? (
              // 로그인 사용자: 개인화 추천 섹션
              <UnifiedRecommendationSection
                citySections={citySections}
                userName={userInfo?.name || (session.user?.name) || '사용자'}
                onAttractionClick={(attractionId) => {
                  // 🎯 추천 카드 클릭 추적
                  const attraction = citySections.flatMap(section =>
                    section.attractions ||
                    section.categorySections?.flatMap(cs => cs.attractions || []) || []
                  ).find(a => a.id === attractionId)

                  trackClick(attractionId, {
                    attraction_name: attraction?.name || 'Unknown',
                    category: attraction?.category || 'Unknown',
                    region: 'Unknown',
                    source: 'home_recommendations_unified',
                    recommendation_type: 'personalized'
                  })
                  router.push(`/attraction/${attractionId}`)
                }}
              />
            ) : (
              // 비로그인 사용자: 북마크 기반 인기 추천 섹션
              <PopularRecommendationSection
                citySections={citySections}
                onAttractionClick={(attractionId) => {
                  // 🎯 인기 추천 카드 클릭 추적
                  const attraction = citySections.flatMap(section =>
                    section.attractions ||
                    section.categorySections?.flatMap(cs => cs.attractions || []) || []
                  ).find(a => a.id === attractionId)

                  trackClick(attractionId, {
                    attraction_name: attraction?.name || 'Unknown',
                    category: attraction?.category || 'Unknown',
                    region: 'Unknown',
                    source: 'home_recommendations_popular',
                    recommendation_type: 'popular_by_bookmarks'
                  })
                  router.push(`/attraction/${attractionId}`)
                }}
              />
            )}
          </div>
        )}

          {/* 모든 지역 카테고리별 섹션 */}
          {popularSections.length > 0 && (
          <div className="space-y-6">
            {/* 제목과 카테고리 필터 버튼 */}
            <div className="pl-[10px] pr-5 flex items-center justify-between">
              <h2 className="text-[20px] font-semibold text-[#9CA8FF]">
                지역별 추천
              </h2>

              {/* 지역 필터 버튼 */}
              <button
                onClick={() => setShowRegionModal(true)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#1A2332] text-[#94A9C9] hover:bg-[#252F42] hover:text-[#9CA8FF] transition-all duration-200"
              >
                <span className="text-sm font-medium">
                  {selectedRegionFilter === 'all' ? '전체' : selectedRegionFilter}
                </span>
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-current"
                >
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </button>
            </div>


            {/* 필터링된 지역 섹션들 */}
            <div className="space-y-8">
              {filteredPopularSections.length > 0 ? (
                filteredPopularSections.map((section) => (
                <div key={section.id}>
                  {/* 지역명 */}
                  <div className="pl-[10px] pr-5 mb-4">
                    <h3 className="text-[18px] font-medium text-[#9CA8FF]">
                      {section.cityName}
                    </h3>
                  </div>

                  {/* 카테고리별 캐러셀 */}
                  <div className="relative -ml-[21px] pl-[21px] pr-0">
                    <div
                      className="
                        flex items-stretch gap-4
                        overflow-x-auto no-scrollbar
                        snap-x snap-mandatory scroll-smooth
                        pb-2
                      "
                      style={{ scrollBehavior: 'smooth' }}
                    >
                      {section.attractions.map((attraction) => (
                        <AttractionCard
                          key={attraction.id}
                          attraction={attraction}
                          onAttractionClick={(attractionId) => {
                            // 🎯 지역별 필터링 카드 클릭 추적
                            trackClick(attractionId, {
                              attraction_name: attraction.name || 'Unknown',
                              category: attraction.category,
                              region: section.region,
                              source: 'home_regional_filter',
                              city_section: section.cityName,
                              recommendation_type: 'regional_filter',
                              selected_region_filter: selectedRegionFilter
                            })
                            router.push(`/attraction/${attractionId}`)
                          }}
                        />
                      ))}
                    </div>

                    {/* 좌쪽 가장자리 페이드 */}
                    <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-[#0B1220] to-transparent" />
                  </div>
                </div>
                ))
              ) : (
                <div className="text-center py-12">
                  <div className="text-4xl mb-4">🏙️</div>
                  <p className="text-[#94A9C9] text-lg mb-2">
                    {selectedRegionFilter !== 'all'
                      ? `${selectedRegionFilter} 지역의 장소가 없습니다`
                      : '장소가 없습니다'
                    }
                  </p>
                  <p className="text-[#6FA0E6] text-sm">다른 지역을 선택해보세요</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 지역 선택 모달 */}
        {showRegionModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-[#0B1220] rounded-2xl max-w-md w-full max-h-[80vh] overflow-hidden">
              {/* 모달 헤더 */}
              <div className="px-6 py-4 border-b border-[#1A2332] flex items-center justify-between">
                <h3 className="text-lg font-semibold text-[#9CA8FF]">지역 선택</h3>
                <button
                  onClick={() => setShowRegionModal(false)}
                  className="p-2 hover:bg-[#1A2332] rounded-full transition-colors"
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-[#94A9C9]"
                  >
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>

              {/* 지역 목록 */}
              <div className="px-6 py-4 max-h-[60vh] overflow-y-auto">
                <div className="grid grid-cols-2 gap-3">
                  <button
                    key="all"
                    onClick={() => {
                      setSelectedRegionFilter('all')
                      setShowRegionModal(false)
                    }}
                    className={`
                      p-4 rounded-xl text-center font-medium transition-all duration-200
                      ${selectedRegionFilter === 'all'
                        ? 'bg-[#3E68FF] text-white'
                        : 'bg-[#1A2332] text-[#94A9C9] hover:bg-[#252F42] hover:text-[#9CA8FF]'
                      }
                    `}
                  >
                    전체
                  </button>
                  {availableRegions.map((region) => (
                    <button
                      key={region}
                      onClick={() => {
                        setSelectedRegionFilter(region)
                        setShowRegionModal(false)
                      }}
                      className={`
                        p-4 rounded-xl text-center font-medium transition-all duration-200
                        ${selectedRegionFilter === region
                          ? 'bg-[#3E68FF] text-white'
                          : 'bg-[#1A2332] text-[#94A9C9] hover:bg-[#252F42] hover:text-[#9CA8FF]'
                        }
                      `}
                    >
                      {region}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}



          {/* 로딩 인디케이터 */}
          {loading && (
            <div className="flex justify-center items-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF]"></div>
              <span className="ml-2 text-[#94A9C9]">추천 여행지를 불러오는 중...</span>
            </div>
          )}

          {/* 데이터가 없을 때 */}
          {!loading && citySections.length === 0 && popularSections.length === 0 && (
            <div className="text-center py-16">
              {session ? (
                <>
                  <p className="text-[#94A9C9] text-lg mb-4">
                    {userInfo?.name ? `${userInfo.name}님을 위한 맞춤 추천을 준비하고 있어요!` : '맞춤 추천을 준비하고 있어요!'}
                  </p>
                  <p className="text-[#6FA0E6] text-sm">선호도 설정이나 여행지 탐색 후 다시 확인해보세요 ✨</p>
                </>
              ) : (
                <p className="text-[#94A9C9] text-lg">추천할 여행지를 준비 중입니다...</p>
              )}
            </div>
          )}
        </main>
      )}

      <BottomNavigation />
    </div>
  )
}


/** 관광지 카드 컴포넌트 */
function AttractionCard({
  attraction,
  onAttractionClick,
}: {
  attraction: { id: string; name: string; description: string; imageUrl: string; category: string }
  onAttractionClick: (attractionId: string) => void
}) {
  const categoryColor = getCategoryColor(attraction.category?.trim())

  // 이미지 URL 및 카테고리 디버깅
  console.log(`🖼️ AttractionCard - ${attraction.name}:`, {
    imageUrl: attraction.imageUrl,
    imageUrlType: typeof attraction.imageUrl,
    imageUrlLength: attraction.imageUrl?.length,
    category: attraction.category,
    fullData: attraction
  })

  return (
    <figure
      className="
        snap-start shrink-0
        rounded-lg overflow-hidden
        shadow-lg
        w-[200px] h-[200px]
        cursor-pointer transition-all duration-300
        group relative
      "
      onClick={() => onAttractionClick(attraction.id)}
    >
      {/* 이미지 영역 */}
      <div className="relative w-full h-full overflow-hidden">
        {attraction.imageUrl && attraction.imageUrl !== "/images/default.jpg" && attraction.imageUrl !== null ? (
          <>
            {/* 이미지 로딩 인디케이터 */}
            <div className="absolute inset-0 bg-gray-200 flex items-center justify-center">
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
                console.log(`✅ 이미지 로드 성공: ${attraction.name} - ${attraction.imageUrl}`);
              }}
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                const loadingIndicator = target.previousElementSibling as HTMLElement;
                if (loadingIndicator) loadingIndicator.style.display = 'none';
                const fallback = target.nextElementSibling as HTMLElement;
                if (fallback) fallback.style.display = 'flex';
                console.error(`❌ 이미지 로드 실패: ${attraction.name} - ${attraction.imageUrl}`);
              }}
            />

            {/* 이미지 로드 실패 시 대체 UI */}
            <div
              className="w-full h-full bg-gradient-to-br from-gray-300 to-gray-400 flex items-center justify-center"
              style={{ display: 'none' }}
            >
              <span className="text-gray-600 text-lg text-center px-2">
                {attraction.name}
              </span>
            </div>
          </>
        ) : (
          /* 이미지가 없는 경우 기본 UI */
          <div className="w-full h-full bg-gradient-to-br from-gray-300 to-gray-400 flex items-center justify-center">
            <span className="text-gray-600 text-lg text-center px-2">
              {attraction.name}
            </span>
          </div>
        )}

        {/* 카테고리 배지 - 좌상단 */}
        <div className="absolute top-3 left-3">
          <span
            className="px-3 py-1 text-xs rounded-full font-medium border"
            style={{
              backgroundColor: 'rgba(0, 0, 0, 0.45)',
              color: 'white',
              borderColor: categoryColor
            }}
          >
            {getCategoryName(attraction.category?.trim()) || attraction.category}
          </span>
        </div>

      </div>

      {/* 하단 제목 영역 - 카테고리 색상과 동일한 배경 */}
      <div className="absolute bottom-0 left-0 right-0">
        <div
          className="px-4 py-3 flex items-center justify-center"
          style={{
            backgroundColor: '#0F1A31'
          }}
        >
          <h3 className="font-bold text-base text-center leading-tight truncate" style={{ color: "#9CA8FF" }}>
            {attraction.name}
          </h3>
        </div>
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

// 카테고리별 색상 반환 함수
function getCategoryColor(category: string): string {
  const colorMap: { [key: string]: string } = {
    nature: '#3FC9FF',
    humanities: '#3FC9FF',
    leisure_sports: '#3FC9FF',
    restaurants: '#FF3D00',
    shopping: '#753FFF',
    accommodation: '#FFD53F'
  }
  return colorMap[category] || '#3E68FF'
}

/** 통합 추천 섹션 컴포넌트 (로그인 사용자용) */
function UnifiedRecommendationSection({
  citySections,
  userName,
  onAttractionClick,
}: {
  citySections: CitySection[]
  userName: string
  onAttractionClick: (attractionId: string) => void
}) {
  // 모든 섹션의 attractions를 하나로 통합
  const allAttractions = citySections.flatMap(section => {
    if (section.categorySections && section.categorySections.length > 0) {
      return section.categorySections.flatMap(cs => cs.attractions || [])
    }
    return section.attractions || []
  })

  return (
    <section aria-label={`${userName}님을 위한 추천`} className="w-full">
      {/* 제목 */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-[20px] font-semibold text-[#9CA8FF]">
            {userName}님을 위한 장소를 추천드려요.
          </h2>
        </div>
      </div>

      {/* 통합된 추천 캐러셀 */}
      <div className="relative -ml-[21px] pl-[21px] pr-0">
        <div
          className="
            flex items-stretch gap-4
            overflow-x-auto no-scrollbar
            snap-x snap-mandatory scroll-smooth
            pb-2
          "
          style={{ scrollBehavior: 'smooth' }}
        >
          {allAttractions.map((attraction) => (
            <AttractionCard
              key={attraction.id}
              attraction={attraction}
              onAttractionClick={onAttractionClick}
            />
          ))}
        </div>

        {/* 좌쪽 가장자리 페이드 */}
        <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-[#0B1220] to-transparent" />
      </div>
    </section>
  )
}

/** 인기 추천 섹션 컴포넌트 (비로그인 사용자용) */
function PopularRecommendationSection({
  citySections,
  onAttractionClick,
}: {
  citySections: CitySection[]
  onAttractionClick: (attractionId: string) => void
}) {
  // 모든 섹션의 attractions를 하나로 통합
  const allAttractions = citySections.flatMap(section => {
    if (section.categorySections && section.categorySections.length > 0) {
      return section.categorySections.flatMap(cs => cs.attractions || [])
    }
    return section.attractions || []
  })

  return (
    <section aria-label="인기 추천" className="w-full">
      {/* 제목 */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-[20px] font-semibold text-[#9CA8FF]">
            지금 가장 인기있는 장소를 추천드려요.
          </h2>
        </div>
      </div>

      {/* 인기 추천 캐러셀 */}
      <div className="relative -ml-[21px] pl-[21px] pr-0">
        <div
          className="
            flex items-stretch gap-4
            overflow-x-auto no-scrollbar
            snap-x snap-mandatory scroll-smooth
            pb-2
          "
          style={{ scrollBehavior: 'smooth' }}
        >
          {allAttractions.map((attraction) => (
            <AttractionCard
              key={attraction.id}
              attraction={attraction}
              onAttractionClick={onAttractionClick}
            />
          ))}
        </div>

        {/* 좌쪽 가장자리 페이드 */}
        <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-[#0B1220] to-transparent" />
      </div>
    </section>
  )
}

/** 메인 카드 컴포넌트 */
function MainCard({
  attraction,
  onAttractionClick,
}: {
  attraction: { id: string; name: string; description: string; imageUrl: string; category: string }
  onAttractionClick: (attractionId: string) => void
}) {
  if (!attraction) return null

  const categoryColor = getCategoryColor(attraction.category?.trim())

  return (
    <figure
      className="
        snap-start shrink-0
        rounded-lg overflow-hidden
        shadow-lg
        w-full max-w-lg h-[200px]
        cursor-pointer transition-all duration-300
        group relative
      "
      onClick={() => onAttractionClick(attraction.id)}
    >
      {/* 이미지 영역 */}
      <div className="relative w-full h-full overflow-hidden">
        {attraction.imageUrl && attraction.imageUrl !== "/images/default.jpg" && attraction.imageUrl !== null ? (
          <>
            {/* 이미지 로딩 인디케이터 */}
            <div className="absolute inset-0 bg-gray-200 flex items-center justify-center">
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
                console.log(`✅ 이미지 로드 성공: ${attraction.name} - ${attraction.imageUrl}`);
              }}
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                const loadingIndicator = target.previousElementSibling as HTMLElement;
                if (loadingIndicator) loadingIndicator.style.display = 'none';
                const fallback = target.nextElementSibling as HTMLElement;
                if (fallback) fallback.style.display = 'flex';
                console.error(`❌ 이미지 로드 실패: ${attraction.name} - ${attraction.imageUrl}`);
              }}
            />

            {/* 이미지 로드 실패 시 대체 UI */}
            <div
              className="w-full h-full bg-gradient-to-br from-gray-300 to-gray-400 flex items-center justify-center"
              style={{ display: 'none' }}
            >
              <span className="text-gray-600 text-lg text-center px-2">
                {attraction.name}
              </span>
            </div>
          </>
        ) : (
          /* 이미지가 없는 경우 기본 UI */
          <div className="w-full h-full bg-gradient-to-br from-gray-300 to-gray-400 flex items-center justify-center">
            <span className="text-gray-600 text-lg text-center px-2">
              {attraction.name}
            </span>
          </div>
        )}

        {/* 카테고리 배지 - 좌상단 */}
        <div className="absolute top-3 left-3">
          <span
            className="px-3 py-1 text-xs rounded-full font-medium border"
            style={{
              backgroundColor: 'rgba(0, 0, 0, 0.45)',
              color: 'white',
              borderColor: categoryColor
            }}
          >
            {getCategoryName(attraction.category?.trim()) || attraction.category}
          </span>
        </div>

      </div>

      {/* 하단 제목 영역 - 카테고리 색상과 동일한 배경 */}
      <div className="absolute bottom-0 left-0 right-0">
        <div
          className="px-4 py-3 flex items-center justify-center"
          style={{
            backgroundColor: '#0F1A31'
          }}
        >
          <h3 className="font-bold text-base text-center leading-tight truncate" style={{ color: "#9CA8FF" }}>
            {attraction.name}
          </h3>
        </div>
      </div>
    </figure>
  )
}
