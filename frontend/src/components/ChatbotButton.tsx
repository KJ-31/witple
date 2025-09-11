'use client'

import React from 'react'
import { useChatbot } from './ChatbotProvider'

export function ChatbotButton() {
  const { setShowChatbot } = useChatbot()

  return (
    <button
      onClick={() => setShowChatbot(true)}
      className="fixed bottom-24 right-6 z-50 w-12 h-12 bg-[#3E68FF] hover:bg-[#4C7DFF] rounded-full flex items-center justify-center shadow-lg transition-all duration-200 hover:scale-110"
    >
      <img
        src="/images/chat_icon.svg"
        alt="챗봇"
        className="w-8 h-8"
      />
    </button>
  )
}