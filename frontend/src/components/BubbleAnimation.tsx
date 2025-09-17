'use client'

import { useEffect, useRef, useState } from 'react'
import { useRive, useStateMachineInput } from '@rive-app/react-canvas'
import { useChatbot } from './ChatbotProvider'
import { usePathname } from 'next/navigation'
import { useSession } from 'next-auth/react'

// DB user_preference 테이블의 priority 컬럼 기반 맞춤 메시지 생성 함수 (20자 이하)
function generatePersonalizedMessages(preferences: any) {
  const messages = []

  // 기본 인사 메시지 (17자)
  messages.push('새로운 여행지를 찾아볼까요?')

  // DB priority 컬럼 기반 맞춤 메시지 ('accommodation', 'shopping', 'experience', 'restaurants')
  if (preferences?.priority) {
    switch (preferences.priority) {
      case 'accommodation':
        messages.push('특별한 숙소는 어떠세요?')
        messages.push('힐링 숙소를 찾아드릴까요?')
        messages.push('편안한 숙박지 추천드려요!')
        messages.push('숙소 중심 여행 어떠세요?')
        break
      case 'shopping':
        messages.push('쇼핑 명소를 찾아볼까요?')
        messages.push('특별한 기념품은 어때요?')
        messages.push('쇼핑과 관광을 함께해요!')
        messages.push('현지 쇼핑 투어 떠나요!')
        break
      case 'experience':
        messages.push('특별한 체험 어떠세요?')
        messages.push('현지 문화 체험해볼까요?')
        messages.push('잊지 못할 경험 만들어요!')
        messages.push('액티비티 가득한 여행!')
        break
      case 'restaurants':
        messages.push('맛있는 현지 음식 찾아요!')
        messages.push('숨겨진 맛집 알려드려요!')
        messages.push('미식 여행 떠나볼까요?')
        messages.push('맛집 투어 어떠세요?')
        break
      default:
        // 예상치 못한 priority 값일 경우 기본 메시지
        messages.push('맞춤 추천을 받아보세요!')
        messages.push('특별한 여행지 찾아드려요!')
        break
    }
  }

  // 공통 추가 메시지 (모두 20자 이하)
  messages.push('새로운 발견을 해볼까요?')
  messages.push('특별한 추억 만들어요!')
  messages.push('완벽한 여행지가 기다려요!')

  return messages
}

export default function BubbleAnimation() {
  const { setShowChatbot, showChatbot, isAppLoading } = useChatbot()
  const pathname = usePathname()
  const { data: session } = useSession()

  // 표시해야 할 페이지 경로들 (메인화면과 추천탭에서만 표시)
  const allowedPaths = ['/', '/recommendations']

  // 현재 경로가 허용된 페이지가 아니면 렌더링하지 않음
  const shouldShowBubble = allowedPaths.some(path => {
    if (path === '/') {
      return pathname === '/'  // 메인화면은 정확히 일치해야 함
    }
    return pathname.startsWith(path)  // 추천탭은 startsWith로 체크
  })

  const { rive, RiveComponent } = useRive({
    src: '/rive/bubble_3.riv',
    stateMachines: 'State Machine 1',
    autoplay: true,
    autoBind: true as any, // ViewModel(Default Instance) 자동 바인딩
  })

  // ✅ .riv에 존재하는 Trigger는 'show' 하나
  const showTrigger = useStateMachineInput(rive, 'State Machine 1', 'show')

  const firstTimeout = useRef<number | null>(null)
  const textInterval = useRef<number | null>(null)
  const startedRef = useRef(false) // StrictMode 중복 가드

  const [visible, setVisible] = useState(false)
  const [userPreferences, setUserPreferences] = useState(null)
  const [messages, setMessages] = useState<string[]>([])

  // 사용자 취향 정보 가져오기
  useEffect(() => {
    async function loadUserPreferences() {
      // console.log('🔄 BubbleAnimation - 로그인 상태:', !!session?.user?.email)
      // console.log('🔄 BubbleAnimation - 사용자 이메일:', session?.user?.email)

      if (session?.user?.email) {
        try {
          // DB user_preference 테이블에서 사용자 취향 정보 가져오기
          // console.log('🔄 API 호출 시작 - 취향 정보 조회')
          const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
          const response = await fetch(`${API_BASE_URL}/api/v1/profile/me`, {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            },
            credentials: 'include'
          })

          // console.log('🔄 API 응답 상태:', response.status, response.ok)

          if (response.ok) {
            const preferences = await response.json()
            // console.log('✅ 취향 정보 로드 성공:', preferences)
            // console.log('✅ Priority 값:', preferences?.priority)
            // console.log('✅ 전체 응답 구조 확인:', JSON.stringify(preferences, null, 2))
            setUserPreferences(preferences)

            // priority 값이 있는지 체크
            if (preferences?.priority) {
              // 맞춤형 메시지 생성
              const personalizedMessages = generatePersonalizedMessages(preferences)
              console.log('✅ 생성된 맞춤형 메시지:', personalizedMessages)
              setMessages(personalizedMessages)
            } else {
              console.log('⚠️ Priority 값이 없음 - 기본 로그인 메시지 사용')
              const defaultMessages = [
                '새로운 여행지를 찾아볼까요?',
                '함께 여행을 계획해볼까요?',
                '맞춤 추천을 받아보세요!',
                '취향 설정하면 더 정확해요!'
              ]
              setMessages(defaultMessages)
            }
          } else {
            // 로그인했지만 취향 정보가 없는 경우 기본 로그인 메시지
            // console.log('⚠️ 취향 정보 없음 - 기본 로그인 메시지 사용')
            const defaultMessages = [
              '새로운 여행지를 찾아볼까요?',
              '함께 여행을 계획해볼까요?',
              '맞춤 추천을 받아보세요!',
              '취향 설정하면 더 정확해요!'
            ]
            // console.log('⚠️ 기본 로그인 메시지:', defaultMessages)
            setMessages(defaultMessages)
          }
        } catch (error) {
          console.error('❌ 취향 정보 로드 실패:', error)
          // 에러 시 기본 로그인 메시지
          const errorMessages = [
            '새로운 여행지를 찾아볼까요?',
            '함께 여행을 계획해볼까요?',
            '맞춤 추천을 받아보세요!'
          ]
          console.log('❌ 에러 시 메시지:', errorMessages)
          setMessages(errorMessages)
        }
      } else {
        // 비로그인 상태 - 기본 메시지
        // console.log('👤 비로그인 상태 - 기본 메시지 사용')
        const guestMessages = [
          '어디로 떠나고 싶으신가요?',
          'hello, World!',
          '원하는 곳을 말해보세요!',
          '한옥 경험은 어떠세요?',
          '인기 여행지가 궁금하세요?'
        ]
        // console.log('👤 비로그인 메시지:', guestMessages)
        setMessages(guestMessages)
      }
    }

    loadUserPreferences()
  }, [session?.user?.email])

  // ---- ViewModel을 통해 문구 바꾸기 (1순위) ----
  function setSpeech(text: string) {
    if (!rive) return
    // ViewModel(speech).sentence:String 갱신
    try {
      const vmi =
        (rive as any)?.viewModelInstance ??
        (rive as any)?.defaultViewModelInstance
      const stringProp = vmi?.string?.('sentence')
      if (stringProp) {
        stringProp.value = text
        return
      }
    } catch {
      /* noop */
    }
    // 폴백: Export된 Text Run 이름이 'sentence'일 때만
    try {
      (rive as any)?.setTextRunValue?.('sentence', text)
    } catch {
      /* noop */
    }
  }

  function triggerSpeakOnce() {
    if (!rive || !showTrigger) return
    if (document.visibilityState !== 'visible') return
    if (showChatbot) return
    // 상태머신이 재생 상태인지 보장 (이름으로 명시)
    try {
      rive.play && rive.play('State Machine 1')
    } catch {
      /* noop */
    }
    showTrigger.fire()
  }

  useEffect(() => {
    // shouldShowBubble이 false이면 애니메이션 중단
    if (!shouldShowBubble) {
      if (firstTimeout.current) clearTimeout(firstTimeout.current)
      if (textInterval.current) clearInterval(textInterval.current)
      startedRef.current = false
      setVisible(false)
      return
    }

    // rive가 없거나 이미 시작되었으면 리턴
    if (!rive || startedRef.current) return
    startedRef.current = true

    setVisible(true)

    // 초기 진입: 약간의 딜레이 후 첫 실행
    firstTimeout.current = window.setTimeout(() => {
      try {
        rive.play && rive.play('State Machine 1') // 상태머신 재생 보장
      } catch { }
      triggerSpeakOnce()
    }, 800)

    // 메시지가 아직 로드되지 않은 경우 기본 메시지 사용
    const currentMessages = messages.length > 0 ? messages : [
      '어디로 떠나고 싶으신가요?',
      'hello, World!',
      '원하는 곳을 말해보세요!'
    ]

    let idx = 0
    setSpeech(currentMessages[idx])

    textInterval.current = window.setInterval(() => {
      idx = (idx + 1) % currentMessages.length
      setSpeech(currentMessages[idx])
      // 텍스트 반영 다음 프레임에 트리거 발사 → 레이아웃/오토사이징 먼저 적용
      requestAnimationFrame(() => triggerSpeakOnce())
    }, 4000)

    return () => {
      if (firstTimeout.current) clearTimeout(firstTimeout.current)
      if (textInterval.current) clearInterval(textInterval.current)
      startedRef.current = false
    }
  }, [rive, showChatbot, showTrigger, shouldShowBubble, pathname, messages]) // messages 의존성 추가

  // 허용된 페이지가 아니거나 로딩 중이면 BubbleAnimation 숨김
  if (!shouldShowBubble || isAppLoading) {
    return null
  }

  return (
    <div className="fixed z-[9999] bottom-[136px] sm:bottom-[164px] right-[44px] sm:right-[58px] md:right-[68px] lg:right-[72px]">
      <div
        className={`transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      >
        <div className="relative">
          {/* 반응형 크기 조정 */}
          <div className="w-[300px] h-[70px] sm:w-[350px] sm:h-[87px] md:w-[400px] md:h-[100px]">
            <RiveComponent className="w-full h-full" />
          </div>

          {/* 클릭 히트박스 */}
          <div
            onClick={() => setShowChatbot(true)}
            className="absolute cursor-pointer top-[25%] left-[50%] w-[80%] h-[25%]"
          />
        </div>
      </div>
    </div>
  )
}
