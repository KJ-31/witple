'use client'

import React from 'react'
import { usePathname } from 'next/navigation'
import { useChatbot } from './ChatbotProvider'

export function ChatbotButton() {
  const { setShowChatbot } = useChatbot()
  const pathname = usePathname()

  // 숨겨야 할 페이지 경로들
  const hiddenPaths = ['/feed', '/profile', '/attraction', '/plan', '/itinerary']

  // 현재 경로가 숨겨야 할 페이지에 포함되면 렌더링하지 않음
  if (hiddenPaths.some(path => pathname.startsWith(path))) {
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