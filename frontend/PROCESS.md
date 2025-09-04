# 0902
현재 Witple 서비스의 React 컴포넌트 구조와
  데이터 호출 흐름을 설명해드리겠습니다! 🚀

  📱 서비스 전체 구조

  Witple 홈 화면
  ├── 상단 네비게이션 (마이페이지, 퀘스트,
  보물찾기, 피드)
  ├── 로고 및 검색바
  └── 무한 스크롤 추천 도시 섹션들

  ⚛️ React 컴포넌트 구조

  1. 메인 컴포넌트: Home (src/app/page.tsx)

  export default function Home() {
    // 상태 관리
    const [citySections, setCitySections] =
  useState<CitySection[]>([])
    const [loading, setLoading] = useState(false)
    const [hasMore, setHasMore] = useState(true)
    const [page, setPage] = useState(0)

    // 중복 호출 방지용 ref
    const loadingRef = useRef(false)
    const observerRef =
  useRef<IntersectionObserver | null>(null)
  }

  2. 서브 컴포넌트: SectionCarousel

  function SectionCarousel({
    title,        // "과거와 현재가 공존하는
  대한민국의 수도"
    cityName,     // "서울"
    attractions,  // 해당 도시의 명소들 배열
    recommendationScore // 95 (추천 점수)
  })

  🔄 데이터 호출 흐름

  1단계: 초기 데이터 로드

  // 컴포넌트 마운트 시 실행
  useEffect(() => {
    loadRecommendedCities(0) // 첫 페이지(0) 로드
  }, [])

  2단계: API 시뮬레이션 호출

  const loadRecommendedCities = async (pageNum:
  number) => {
    // 1. 중복 호출 방지
    if (loadingRef.current) return

    // 2. 로딩 상태 설정
    loadingRef.current = true
    setLoading(true)

    // 3. 더미 API 호출 (800ms 지연)
    const { data, hasMore } = await
  fetchRecommendedCities(pageNum, 3)

    // 4. 데이터 병합 또는 초기화
    if (pageNum === 0) {
      setCitySections(data)     // 첫 로드: 새로운
   데이터
    } else {
      setCitySections(prev => [...prev, ...data])
  // 무한스크롤: 기존 + 새 데이터
    }

    // 5. 상태 업데이트
    setHasMore(hasMore)
    setPage(pageNum)
  }

  3단계: 더미 데이터 처리 (src/lib/dummyData.ts)

  export const fetchRecommendedCities = async
  (page: number, limit: number) => {
    // 네트워크 지연 시뮬레이션
    await new Promise(resolve =>
  setTimeout(resolve, 800))

    // 페이지네이션 계산
    const startIndex = page * limit  // 0, 3, 6...
    const endIndex = startIndex + limit // 3, 6,
  9...

    // 해당 범위의 데이터 추출
    const data =
  RECOMMENDED_CITY_SECTIONS.slice(startIndex,
  endIndex)
    const hasMore = endIndex <
  RECOMMENDED_CITY_SECTIONS.length

    return { data, hasMore }
  }

  📜 무한 스크롤 구현 원리

  IntersectionObserver 활용

  const lastElementRef = useCallback((node:
  HTMLDivElement | null) => {
    // 1. 기존 Observer 해제
    if (observerRef.current)
  observerRef.current.disconnect()

    // 2. 새로운 Observer 생성
    observerRef.current = new
  IntersectionObserver(entries => {
      // 3. 마지막 요소가 화면에 보이고, 더 로드할
   데이터가 있을 때
      if (entries[0].isIntersecting && hasMore &&
  !loadingRef.current) {
        loadRecommendedCities(page + 1) // 다음
  페이지 로드
      }
    })

    // 4. 마지막 요소에 Observer 연결
    if (node) observerRef.current.observe(node)
  }, [hasMore, page])

  🎨 UI 렌더링 흐름

  1. 도시 섹션 렌더링

  {citySections.map((citySection, index) => (
    <div
      key={citySection.id}
      // 마지막 요소에 ref 연결 (무한스크롤
  트리거)
      ref={index === citySections.length - 1 ?
  lastElementRef : null}
    >
      <SectionCarousel {...citySection} />
    </div>
  ))}

  2. 각 도시별 명소 캐러셀

  // SectionCarousel 내부
  {attractions.map((attraction) => (
    <figure key={attraction.id}>
      {/* 이미지 (현재는 그라디언트 플레이스홀더)
  */}
      <div className="bg-gradient-to-br
  from-blue-600 to-purple-600">
        {attraction.name}
      </div>

      {/* 카테고리 배지, 평점, 상세 정보 */}
      <span>{getCategoryName(attraction.category)}
  </span>
      <span>⭐ {attraction.rating}</span>
      <h3>{attraction.name}</h3>
      <p>{attraction.description}</p>
    </figure>
  ))}

  🔄 실제 동작 시나리오

  1. 사용자가 페이지 접속 → useEffect 실행 → 첫
  3개 도시 로드 (서울, 제주도, 부산)
  2. 사용자가 스크롤 다운 → 마지막 섹션이 화면에
  나타남 → IntersectionObserver 감지 → 다음 3개
  도시 로드 (전주, 강릉, 경주)
  3. 계속 스크롤 → 또 다시 감지 → 마지막 2개 도시
  로드 (인천, 안동)
  4. 모든 데이터 로드 완료 → hasMore: false →
  "모든 추천 여행지를 확인했습니다" 메시지 표시

  💡 핵심 기술적 특징

  - 중복 호출 방지: loadingRef로 동시 요청 차단
  - 매끄러운 UX: 로딩 스피너와 상태 메시지
  - 메모리 효율성: IntersectionObserver로 스크롤
  이벤트 대신 교차 감지
  - 타입 안전성: TypeScript로 데이터 구조 보장
  - 반응형 디자인: Tailwind CSS로 모바일 우선 설계

  이렇게 추천 알고리즘 기반의 여행지 데이터를 무한
   스크롤로 자연스럽게 제공하는 서비스가
  완성되었습니다! 🎉