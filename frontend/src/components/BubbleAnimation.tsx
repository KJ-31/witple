'use client'

import { useEffect, useRef, useState } from 'react'
import { useRive, useStateMachineInput } from '@rive-app/react-canvas'
import { useChatbot } from './ChatbotProvider'
import { usePathname } from 'next/navigation'

export default function BubbleAnimation() {
  const { setShowChatbot, showChatbot, isAppLoading } = useChatbot()
  const pathname = usePathname()

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

    // 샘플 문구 순환
    const samples = [
      '어디로 떠나고 싶으신가요?',
      'hello, World!',
      '원하는 곳을 말해보세요!',
      '한옥에서 보내는 특별한 경험은 어떠신가요?',
      '최근 가장 인기있는 곳이 궁금하신가요?',
    ]
    let idx = 0
    setSpeech(samples[idx])

    textInterval.current = window.setInterval(() => {
      idx = (idx + 1) % samples.length
      setSpeech(samples[idx])
      // 텍스트 반영 다음 프레임에 트리거 발사 → 레이아웃/오토사이징 먼저 적용
      requestAnimationFrame(() => triggerSpeakOnce())
    }, 4000)

    return () => {
      if (firstTimeout.current) clearTimeout(firstTimeout.current)
      if (textInterval.current) clearInterval(textInterval.current)
      startedRef.current = false
    }
  }, [rive, showChatbot, showTrigger, shouldShowBubble, pathname]) // pathname 의존성 추가

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
