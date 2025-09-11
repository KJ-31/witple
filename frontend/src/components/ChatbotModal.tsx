'use client'

import React, { useEffect, useRef } from 'react'
import { useChatbot } from './ChatbotProvider'

export function ChatbotModal() {
  const { 
    showChatbot, 
    setShowChatbot, 
    chatMessage, 
    setChatMessage, 
    chatMessages, 
    handleChatSubmit
  } = useChatbot()
  
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 메시지가 업데이트될 때마다 스크롤을 맨 아래로
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [chatMessages])


  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!chatMessage.trim()) return

    const messageText = chatMessage
    setChatMessage('')
    await handleChatSubmit(messageText)
  }

  if (!showChatbot) return null

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg w-full max-w-md h-[600px] flex flex-col overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="bg-[#3E68FF] p-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <img
              src="/images/chat_icon.svg"
              alt="챗봇"
              className="w-12 h-12 bg-white rounded-full p-2"
            />
            <div>
              <h3 className="text-white font-semibold">쿼카</h3>
              <p className="text-blue-100 text-sm">여행 마스터</p>
            </div>
          </div>
          <button
            onClick={() => setShowChatbot(false)}
            className="text-white hover:text-blue-200 text-xl font-bold w-8 h-8 flex items-center justify-center"
          >
            ×
          </button>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
          {chatMessages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] ${msg.type === 'user'
                ? 'bg-[#3E68FF] text-white'
                : 'bg-white border border-gray-200'
                } rounded-2xl px-4 py-2 shadow-sm`}>
                <p className={`text-sm ${msg.type === 'user' ? 'text-white' : 'text-gray-800'}`}>
                  {msg.message}
                </p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-200 bg-white">
          <form onSubmit={handleSubmit} className="flex items-center space-x-2">
            <input
              type="text"
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              placeholder="메시지를 입력하세요..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-[#3E68FF] focus:border-transparent text-gray-800"
            />
            <button
              type="submit"
              disabled={!chatMessage.trim()}
              className="w-10 h-10 bg-[#3E68FF] hover:bg-[#4C7DFF] disabled:bg-gray-300 rounded-full flex items-center justify-center transition-colors"
            >
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}