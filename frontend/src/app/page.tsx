'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { fetchPersonalizedRegionCategories, fetchPopularSectionByRegion, getUserType, type CitySection } from '../lib/dummyData'
import BubbleAnimation from '../components/BubbleAnimation'
import { BottomNavigation } from '../components'
import { trackClick } from '../utils/actionTracker'
import { useActionTrackerSession } from '../hooks/useActionTrackerSession'

export default function Home() {
  const router = useRouter()
  const { session, status } = useActionTrackerSession()
  const [searchQuery, setSearchQuery] = useState('')
  const [citySections, setCitySections] = useState<CitySection[]>([])
  const [popularSection, setPopularSection] = useState<CitySection | null>(null)
  const [availableRegions, setAvailableRegions] = useState<string[]>([])
  const [selectedRegion, setSelectedRegion] = useState<string>('서울')
  const [showRegionModal, setShowRegionModal] = useState<boolean>(false)
  const [loading, setLoading] = useState(false)
  const [userInfo, setUserInfo] = useState<{ name: string, preferences: any } | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)

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
              console.log('사용자 북마크 수:', bookmarkCount)
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

  // 추천 도시 데이터 로드 함수 (동적 설정 적용)
  const loadRecommendedCities = useCallback(async (currentUserInfo?: { name: string, preferences: any } | null) => {
    if (loading) {
      console.log('이미 로딩 중이므로 중복 요청 방지')
      return
    }

    console.log('추천 데이터 로드 시작 - 세션:', !!session)
    setLoading(true)

    // 10초 타임아웃 설정 (개인화 추천 벡터 계산 시간 고려)
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('API 요청 타임아웃')), 10000)
    )

    try {
      // 백엔드 설정을 사용하여 API 호출 (모든 사용자 v2 API 사용)
      const dataPromise = fetchPersonalizedRegionCategories(undefined, currentUserInfo || userInfo, session)

      const result = await Promise.race([dataPromise, timeoutPromise]) as { data: CitySection[] }

      // 데이터 처리 - 백엔드에서 이미 동적 설정이 적용된 상태
      const processedData = result.data.map(section => {
        // categorySections가 있으면 그대로 사용 (백엔드에서 이미 처리됨)
        if (section.categorySections && section.categorySections.length > 0) {
          console.log(`섹션 ${section.cityName}: 카테고리별 ${section.categorySections.length}개 카테고리`)

          // 각 카테고리의 attractions 수 로깅
          section.categorySections.forEach(cat => {
            console.log(`  - ${cat.categoryName}: ${cat.attractions?.length || 0}개`)
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

        console.log(`섹션 ${section.cityName}: 일반 형태 ${attractions.length}개 (백엔드에서 이미 제한됨)`)

        return {
          ...section,
          attractions: filteredAttractions,
          categorySections: undefined
        }
      })

      console.log('추천 데이터 로드 완료:', processedData.length, '개 섹션')

      // 모든 섹션이 비어있는지 체크 (categorySections 포함)
      const totalAttractions = processedData.reduce((sum, section) => {
        if (section.categorySections && section.categorySections.length > 0) {
          // categorySections가 있으면 해당 attractions 수 계산
          return sum + section.categorySections.reduce((catSum, cat) =>
            catSum + (cat.attractions?.length || 0), 0)
        }
        return sum + (section.attractions?.length || 0)
      }, 0)

      console.log('총 추천 장소 수:', totalAttractions)

      if (totalAttractions === 0) {
        console.warn('필터링 후 모든 데이터가 사라짐, 원본 데이터로 대체')
        // 원본 데이터를 그대로 사용 (백엔드에서 이미 처리됨)
        setCitySections(result.data)
      } else {
        setCitySections(processedData)
      }
    } catch (error) {
      console.warn('데이터 로드 오류:', error instanceof Error ? error.message : String(error))
      setCitySections([])
    } finally {
      setLoading(false)
    }
  }, [session]) // userInfo 의존성 제거

  // 지역별 인기순 섹션 로드 함수 (모든 사용자용)
  const loadPopularSection = useCallback(async (region: string = selectedRegion) => {
    console.log(`인기순 섹션 로드 시작: 지역=${region}`)

    try {
      const result = await fetchPopularSectionByRegion(region, 6, 6)
      setPopularSection(result.data)
      setAvailableRegions(result.availableRegions)
      console.log(`인기순 섹션 로드 완료: ${region}, 카테고리=${result.data?.categorySections?.length || 0}개`)
    } catch (error) {
      console.warn('인기순 섹션 로드 오류:', error)
      setPopularSection(null)
    }
  }, [selectedRegion])

  // 지역 변경 핸들러
  const handleRegionChange = useCallback((region: string) => {
    setSelectedRegion(region)
    setShowRegionModal(false) // 모달 닫기
    loadPopularSection(region)
  }, [loadPopularSection])

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
        console.log('사용자 선호도 설정 완료 확인')
      }
    } catch (error) {
      console.warn('선호도 체크 오류:', error instanceof Error ? error.message : String(error))
      // 에러 시에도 메인 페이지는 정상 작동
    }
  }, [session, router])

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
      console.log('초기화 시작 - 세션:', !!session)

      if (session) {
        // 로그인 상태: 사용자 정보 먼저 로드 후 추천 데이터 로드
        const initializeUser = async () => {
          try {
            // 먼저 사용자 정보를 로드하고, 그 정보를 기반으로 선호도 체크
            const loadedUserInfo = await loadUserInfo()

            // 사용자 정보 로드 후에 추천 데이터 로드 (병렬 처리 대신 순차 처리로 안정성 확보)
            await loadRecommendedCities()

            // 인기순 섹션 로드 (모든 로그인 사용자)
            await loadPopularSection()

            console.log('로그인 사용자 초기화 완료')
          } catch (error) {
            console.warn('로그인 사용자 초기화 오류:', error)
          }
        }

        initializeUser()
      } else {
        // 비로그인 상태: 추천 데이터와 인기순 섹션 로드
        Promise.all([
          loadRecommendedCities(),
          loadPopularSection()
        ]).then(() => {
          console.log('비로그인 사용자 초기화 완료')
        }).catch(error => {
          console.warn('비로그인 사용자 초기화 오류:', error)
        })
      }
    }
  }, [status, isInitialized])


  return (
    <div className="min-h-screen bg-[#0B1220] text-slate-200 pb-20">
      {/* Header with Logo and Chatbot */}
      <div className="sticky top-0 z-40 bg-[#0B1220] flex items-center justify-between pr-4 pl-6 py-4 mb-10">
        <h1 className="text-[2.75rem] font-logo text-[#3E68FF] tracking-wide">WITPLE</h1>
        {/* <button
          onClick={() => {
            const chatbotEvent = new CustomEvent('openChatbot');
            window.dispatchEvent(chatbotEvent);
          }}
          className="w-12 h-12 bg-[#3E68FF] hover:bg-[#4C7DFF] rounded-full flex items-center justify-center shadow-lg transition-all duration-200 hover:scale-110"
        >
          <img
            src="/images/chat_icon.svg"
            alt="챗봇"
            className="w-8 h-8"
          />
        </button> */}
      </div>

      {/* Main Card 섹션 - 로그인/비로그인 모두 표시 */}
      {(citySections.length > 0 || popularSection) && (
        <div className="px-5 mb-12">
          <MainCard
            attraction={
              citySections[0]?.categorySections?.[0]?.attractions?.[0] ||
              citySections[0]?.attractions?.[0] ||
              popularSection?.categorySections?.[0]?.attractions?.[0] ||
              popularSection?.attractions?.[0]
            }
            onAttractionClick={(attractionId) => router.push(`/attraction/${attractionId}`)}
          />
        </div>
      )}

      {/* 추천 명소 섹션 */}
      <main className="pl-[20px] pr-0 pb-24 space-y-12">
        {session && citySections.length > 0 && (
          // 로그인 사용자: 통합된 개인화 추천 섹션
          <div>
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
          </div>
        )}

        {/* 지역별 인기순 섹션 (필터 기능 포함) */}
        {popularSection && (
          <div className="space-y-6">
            {/* 제목과 필터 버튼 */}
            <div className="px-5 flex items-center justify-between">
              <h2 className="text-[20px] font-semibold text-[#9CA8FF]">
                {selectedRegion} 인기 추천
              </h2>

              {/* 필터 버튼 */}
              <button
                onClick={() => setShowRegionModal(true)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#1A2332] text-[#94A9C9] hover:bg-[#252F42] hover:text-[#9CA8FF] transition-all duration-200"
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-current"
                >
                  <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/>
                </svg>
                <span className="text-sm font-medium">필터</span>
              </button>
            </div>

            {/* 카테고리별 인기순 섹션 */}
            <SectionCarousel
              title={popularSection.description}
              cityName={popularSection.cityName}
              attractions={popularSection.attractions}
              categorySections={popularSection.categorySections}
              onAttractionClick={(attractionId) => {
                // 🎯 인기순 카드 클릭 추적
                const attraction = popularSection.attractions?.find(a => a.id === attractionId) ||
                  popularSection.categorySections?.flatMap(cs => cs.attractions || [])
                    .find(a => a.id === attractionId)

                trackClick(attractionId, {
                  attraction_name: attraction?.name || 'Unknown',
                  category: attraction?.category || popularSection.cityName,
                  region: popularSection.region || popularSection.cityName,
                  source: 'home_popular_filtered',
                  city_section: popularSection.cityName,
                  recommendation_type: 'popular',
                  selected_region: selectedRegion
                })
                router.push(`/attraction/${attractionId}`)
              }}
            />
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
                  {availableRegions.map((region) => (
                    <button
                      key={region}
                      onClick={() => handleRegionChange(region)}
                      className={`
                        p-4 rounded-xl text-center font-medium transition-all duration-200
                        ${selectedRegion === region
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
        {!loading && citySections.length === 0 && (
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

      <BottomNavigation />
      <BubbleAnimation />
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
  attractions: { id: string; name: string; description: string; imageUrl: string; category: string }[]
  categorySections?: Array<{ category: string; categoryName: string; attractions: any[]; total: number }>
  onAttractionClick: (attractionId: string) => void
}) {
  return (
    <section aria-label={`${cityName} ${title}`} className="w-full">
      {/* 도시 제목과 추천 점수 */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-[20px] font-semibold text-[#9CA8FF]">
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
              {/* <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold text-[#3E68FF]">
                  {categorySection.categoryName}
                </h3>
                <span className="text-sm text-[#6FA0E6]">
                  {categorySection.total}개 장소
                </span>
              </div> */}

              {/* 카테고리별 장소 캐러셀 */}
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
                  {categorySection.attractions.map((attraction) => (
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
            </div>
          ))}
        </div>
      ) : (
        /* 기존 방식: 모든 장소를 하나의 캐러셀로 표시 */
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
            {attractions.map((attraction) => (
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
      )}
    </section>
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

  // 맛집과 쇼핑 카테고리는 밝은 색상, 나머지는 어두운 색상
  const textColor = (attraction.category === 'restaurants' || attraction.category === 'shopping')
    ? '#E8EAFF'
    : '#0D121C'

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
            className="px-3 py-1 text-xs rounded-full font-medium"
            style={{
              backgroundColor: categoryColor,
              color: textColor
            }}
          >
            {getCategoryName(attraction.category?.trim()) || attraction.category}
          </span>
        </div>

      </div>

      {/* 하단 제목 영역 - 카테고리 색상과 동일한 배경 */}
      <div className="absolute bottom-4 left-4 right-4">
        <div
          className="rounded-xl px-4 py-3 flex items-center justify-center"
          style={{
            backgroundColor: categoryColor
          }}
        >
          <h3 className="font-bold text-base text-center leading-tight truncate" style={{ color: textColor }}>
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

  // 맛집과 쇼핑 카테고리는 밝은 색상, 나머지는 어두운 색상
  const textColor = (attraction.category === 'restaurants' || attraction.category === 'shopping')
    ? '#E8EAFF'
    : '#0D121C'
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
            className="px-3 py-1 text-xs rounded-full font-medium"
            style={{
              backgroundColor: categoryColor,
              color: textColor
            }}
          >
            {getCategoryName(attraction.category?.trim()) || attraction.category}
          </span>
        </div>

      </div>

      {/* 하단 제목 영역 - 카테고리 색상과 동일한 배경 */}
      <div className="absolute bottom-4 left-4 right-4">
        <div
          className="rounded-xl px-4 py-3 flex items-center justify-center"
          style={{
            backgroundColor: categoryColor
          }}
        >
          <h3 className="font-bold text-base text-center leading-tight truncate" style={{ color: textColor }}>
            {attraction.name}
          </h3>
        </div>
      </div>
    </figure>
  )
}
