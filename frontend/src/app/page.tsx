'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { fetchPersonalizedRegionCategories, fetchCitiesByCategory, type CitySection } from '../lib/dummyData'
import { BottomNavigation } from '../components'

export default function Home() {
  const router = useRouter()
  const { data: session, status } = useSession()
  const [citySections, setCitySections] = useState<CitySection[]>([])
  const [loading, setLoading] = useState(false)
  const [userInfo, setUserInfo] = useState<{ name: string, preferences: any } | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)

  // 사용자 정보 및 여행 취향 로드 함수
  const loadUserInfo = useCallback(async () => {
    if (!session || !(session as any).backendToken) {
      setUserInfo(null)
      return
    }

    // 기본 사용자 정보 설정 (세션 기반)
    const defaultUserInfo = {
      name: session.user?.name || '사용자',
      preferences: null
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

          setUserInfo({
            name: userData.name || defaultUserInfo.name,
            preferences: preferences
          })
        } catch (jsonError) {
          console.warn('사용자 프로필 JSON 파싱 오류:', jsonError)
          // JSON 파싱 실패 시 기본 정보 유지
        }
      } else {
        console.warn(`사용자 프로필 정보 로드 실패 (${userResponse.status}): API 서버 오류 또는 권한 없음`)
        // API 오류 시에도 기본 정보는 유지됨 (이미 설정함)
      }
    } catch (error) {
      console.warn('사용자 정보 로드 전체 오류:', error instanceof Error ? error.message : String(error))
      // 전체 오류 시에도 기본 정보는 유지됨 (이미 설정함)
    }
  }, [session])

  // 추천 도시 데이터 로드 함수 (단순화 + 타임아웃)
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
      const dataPromise = session
        ? fetchPersonalizedRegionCategories(2)
        : fetchCitiesByCategory(0, 2)

      const result = await Promise.race([dataPromise, timeoutPromise]) as { data: CitySection[] }

      // 데이터 처리 개선 - categorySections 그대로 사용
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

        // 별점 필터링 제거 - 모든 데이터 표시
        let filteredAttractions = attractions.slice(0, 8) // 상위 8개만 표시

        console.log(`섹션 ${section.cityName}: 일반 형태 ${attractions.length}개 → 필터링 후 ${filteredAttractions.length}개`)

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

  // 세션 상태 변경 시 초기화 플래그 리셋
  useEffect(() => {
    if (status !== 'loading') {
      setIsInitialized(false)
    }
  }, [session?.user?.email, status]) // 사용자 이메일 변경 시에만 리셋

  // 사용자 정보 로드 및 추천 데이터 로드 (순차 처리) - 한 번만 실행
  useEffect(() => {
    if (status !== 'loading' && !isInitialized) {
      setIsInitialized(true)
      console.log('초기화 시작 - 세션:', !!session)

      if (session) {
        // 로그인 상태: 사용자 정보 먼저 로드한 후 추천 데이터 로드
        const initializeUser = async () => {
          try {
            // 1. 사용자 정보 로드
            await loadUserInfo()

            // 2. 추천 데이터 로드 (사용자 정보 로드 완료 후)
            await loadRecommendedCities()

            // 3. 선호도 체크 (현재 userInfo state를 참조)
            // userInfo가 업데이트된 후에 체크하기 위해 setTimeout 사용
            setTimeout(() => {
              if (userInfo?.preferences) {
                checkUserPreferences(userInfo.preferences)
              }
            }, 100)

            console.log('로그인 사용자 초기화 완료')
          } catch (error) {
            console.warn('로그인 사용자 초기화 오류:', error)
          }
        }

        initializeUser()
      } else {
        // 비로그인 상태: 추천 데이터만 로드
        loadRecommendedCities().then(() => {
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
      <div className="sticky top-0 z-40 bg-[#0B1220] flex items-center justify-between px-4 pt-4 pb-4 mb-10">
        <h1 className="text-5xl font-logo text-[#3E68FF] tracking-wide">WITPLE</h1>
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

      {/* 추천 도시별 명소 섹션 (2개 고정) */}
      <main className="pl-[20px] pr-0 pb-24 space-y-12">
        {citySections.map((citySection, index) => {
          // 사용자 이름 기반 제목 생성
          let personalizedTitle = citySection.description
          if (session) {
            const userName = userInfo?.name || (session.user?.name) || '사용자'
            personalizedTitle = `${userName}님을 위한 장소를 추천드려요.`
          }

          return (
            <div key={`${citySection.id}-${index}`}>
              <SectionCarousel
                title={personalizedTitle}
                cityName={citySection.cityName}
                attractions={citySection.attractions}
                categorySections={citySection.categorySections}
                onAttractionClick={(attractionId) => router.push(`/attraction/${attractionId}`)}
              />
            </div>
          )
        })}

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
