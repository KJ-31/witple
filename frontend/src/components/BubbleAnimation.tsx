'use client'

import { useEffect, useRef, useState } from 'react'
import { useRive, useStateMachineInput } from '@rive-app/react-canvas'
import { useChatbot } from './ChatbotProvider'

export default function BubbleAnimation() {
  const { setShowChatbot, showChatbot } = useChatbot()

  const { rive, RiveComponent } = useRive({
    src: '/rive/bubble_2.riv',
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
      '^.^',
      'hello, World!',
      '안녕하세요! 길이가 조금 더 긴 문장입니다.',
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
    <div className="fixed" style={{ top: '-110px', right: '35px', zIndex: 9999 }}>
      <div style={{ visibility: visible ? 'visible' : 'hidden' }}>
        <div className="relative">
          <RiveComponent style={{ width: 400, height: 400 }} />
          {/* 클릭 히트박스 */}
          <div
            onClick={() => setShowChatbot(true)}
            className="absolute cursor-pointer"
            style={{ top: '25%', left: '50%', width: '80%', height: '25%' }}
          />
        </div>
      </div>
    </div>
  )
}
