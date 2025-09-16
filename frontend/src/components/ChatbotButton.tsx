'use client'

import React from 'react'
import { usePathname } from 'next/navigation'
import { useChatbot } from './ChatbotProvider'

export function ChatbotButton() {
  const { setShowChatbot } = useChatbot()
  const pathname = usePathname()

  // 표시해야 할 페이지 경로들 (메인화면과 추천탭에서만 표시)
  const allowedPaths = ['/', '/recommendations']

  // 현재 경로가 허용된 페이지가 아니면 렌더링하지 않음
  if (!allowedPaths.some(path => {
    if (path === '/') {
      return pathname === '/'  // 메인화면은 정확히 일치해야 함
    }
    return pathname.startsWith(path)  // 추천탭은 startsWith로 체크
  })) {
    return null
  }

  return (
    <button
      onClick={() => setShowChatbot(true)}
      className="
        fixed z-50
        bottom-[100px]
        right-4 sm:right-6 md:right-8 lg:right-9
        w-14 h-14 sm:w-16 sm:h-16
        bg-[#3E68FF] hover:bg-[#4C7DFF]
        rounded-full
        flex items-center justify-center
        shadow-lg
        transition-all duration-200 hover:scale-110
      "
    >
      <img
        src="/images/chat_icon.svg"
        alt="챗봇"
        className="w-8 h-8 sm:w-10 sm:h-10"
      />
    </button>
  )
}