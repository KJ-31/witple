'use client'

import { useEffect, useRef, useState } from 'react'
import { useRive } from '@rive-app/react-canvas'
import { useChatbot } from './ChatbotProvider'

export default function BubbleAnimation() {
  const { setShowChatbot, showChatbot } = useChatbot()
  const { rive, RiveComponent } = useRive({
    src: '/rive/bubble.riv',
    autoplay: false,          // 상태머신 미사용. 수동 제어
    animations: 'closed',     // 초기 포즈가 있다면 'closed' 타임라인 지정
  })

  const firstTimeout = useRef<number | null>(null)
  const loopInterval = useRef<number | null>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!rive) return

    // 1) 초기 'closed' 포즈 적용 후 다음 프레임에만 캔버스 보이기 (플래시 방지)
    // 'closed'가 없다면 아래 두 줄은 제거해도 됨
    rive.play('closed')
    requestAnimationFrame(() => {
      rive.pause('closed')
      setVisible(true)
    })

    // 2) 단일 사이클: show 2 타임라인만 재생
    const playShow2Once = () => {
      if (document.visibilityState !== 'visible') return
      if (showChatbot) return  // 챗봇 모달이 열려있으면 애니메이션 중단
      rive.stop('show 3')      // 혹시 재생 중이면 정지
      rive.play('show 3')      // ★ 이 타임라인만 실행 (Rive에서 One Shot로 설정)
    }

    const start = () => {
      // 로드 후 5초 뒤 첫 재생
      firstTimeout.current = window.setTimeout(() => {
        playShow2Once()
        // 이후 5분마다 반복
        loopInterval.current = window.setInterval(playShow2Once, 500_0)
      }, 5_000)
    }

    // 런타임 시작(타임라인 호출에 반응하도록)
    rive.play()

    if (document.readyState === 'complete') start()
    else window.addEventListener('load', start, { once: true })

    // 정리
    return () => {
      window.removeEventListener('load', start)
      if (firstTimeout.current) clearTimeout(firstTimeout.current)
      if (loopInterval.current) clearInterval(loopInterval.current)
    }
  }, [rive, showChatbot])

  return (
    <div className="fixed" style={{ top: '-40px', right: '20px', zIndex: 9999 }}>
      <div style={{ visibility: visible ? 'visible' : 'hidden' }}>
        <div className="relative">
          <RiveComponent style={{ width: 250, height: 250 }} />
          <div
            onClick={() => setShowChatbot(true)}
            className="absolute cursor-pointer"
            style={{
              top: '25%',
              left: '50%',
              width: '80%',
              height: '25%',
            }}
          />
        </div>
      </div>
    </div>
  )
}
