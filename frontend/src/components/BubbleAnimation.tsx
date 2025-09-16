'use client'

import { useEffect, useRef, useState } from 'react'
import { useRive, useStateMachineInput } from '@rive-app/react-canvas'
import { useChatbot } from './ChatbotProvider'
import { usePathname } from 'next/navigation'

export default function BubbleAnimation() {
  const { setShowChatbot, showChatbot } = useChatbot()
  const pathname = usePathname()

  // ChatbotButton 표시 여부 확인 (ChatbotButton과 동일한 로직)
  const hiddenPaths = ['/feed', '/profile', '/attraction', '/plan', '/itinerary']
  const shouldHideButton = hiddenPaths.some(path => pathname.startsWith(path))

  // ChatbotButton이 숨겨진 페이지에서는 BubbleAnimation도 숨김
  if (shouldHideButton) {
    return null
  }

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
      '안녕하세요! 쉽지만 간단하게 여행을 짜보세요',
      'Rive + Data Binding 테스트 중…',
      '줄바꿈/오토 레이아웃 확인용 문구예요.',
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
  }, [rive, showChatbot, showTrigger])

  return (
    <div className="fixed z-[9999] bottom-[136px] sm:bottom-[164px] right-[44px] sm:right-[58px] md:right-[68px] lg:right-[72px]">
      <div
        className={`transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      >
        <div className="relative">
          {/* 반응형 크기 조정 */}
          <div className="w-[280px] h-[70px] sm:w-[350px] sm:h-[87px] md:w-[400px] md:h-[100px]">
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
