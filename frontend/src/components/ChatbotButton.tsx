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

  const buttonClass = "fixed top-4 right-4 z-50 w-12 h-12 bg-[#3E68FF] hover:bg-[#4C7DFF] rounded-full flex items-center justify-center shadow-lg transition-all duration-200 hover:scale-110"

  return (
    <button
      onClick={() => setShowChatbot(true)}
      className={buttonClass}
    >
      <img
        src="/images/chat_icon.svg"
        alt="챗봇"
        className="w-7 h-7"
      />
    </button>
  )
}