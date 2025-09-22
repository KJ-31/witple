'use client'

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import { useChatbot } from './ChatbotProvider'

// 동적 로딩 텍스트 컴포넌트
function LoadingAnimation() {
  const [textIndex, setTextIndex] = useState(0)

  const loadingTexts = useMemo(() => [
    "여행 정보를 검색중입니다",
    "AI가 최적의 여행 계획을 준비중입니다",
    "맞춤형 추천을 생성중입니다",
    "최신 여행 정보를 수집중입니다",
    "답변을 생성중입니다"
  ], [])

  useEffect(() => {
    const interval = setInterval(() => {
      setTextIndex((prev) => (prev + 1) % loadingTexts.length)
    }, 8000) // 8초마다 텍스트 변경

    return () => clearInterval(interval)
  }, [loadingTexts.length])

  return (
    <div className="flex items-center space-x-3 text-sm text-gray-600">
      <span className="animate-pulse">{loadingTexts[textIndex]}</span>
      <div className="flex space-x-1">
        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
      </div>
    </div>
  )
}

export function ChatbotModal() {
  const {
    showChatbot,
    setShowChatbot,
    chatMessage,
    setChatMessage,
    chatMessages,
    handleChatSubmit,
    clearChatHistory,
    toast,
    showToast
  } = useChatbot()

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 메시지가 업데이트될 때마다 스크롤을 맨 아래로
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [chatMessages])

  // 챗봇 모달이 열릴 때 스크롤을 맨 아래로
  useEffect(() => {
    if (showChatbot && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [showChatbot])


  const handleSubmit = useCallback(async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!chatMessage.trim()) return

    const messageText = chatMessage
    setChatMessage('')
    await handleChatSubmit(messageText)
  }, [chatMessage, setChatMessage, handleChatSubmit])

  const [isComposing, setIsComposing] = useState(false)

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !isComposing) {
      e.preventDefault()
      if (!chatMessage.trim()) return

      const messageText = chatMessage
      setChatMessage('')
      handleChatSubmit(messageText)
    }
  }, [chatMessage, setChatMessage, handleChatSubmit, isComposing])

  const handleCompositionStart = useCallback(() => {
    setIsComposing(true)
  }, [])

  const handleCompositionEnd = useCallback(() => {
    setIsComposing(false)
  }, [])

  const memoizedChatMessages = useMemo(() =>
    chatMessages.map((msg) => (
      <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
        <div className={`max-w-[80%] ${msg.type === 'user'
          ? 'bg-[#3E68FF] text-white'
          : 'bg-white border border-gray-200'
          } rounded-2xl px-4 py-2 shadow-sm`}>
          {msg.type === 'bot' && (msg.message.includes('생성하고 있습니다') || msg.message.includes('검색하고 있습니다') || msg.message.includes('준비 중입니다') || msg.message.includes('수집하고 있습니다')) ? (
            // 개선된 로딩 애니메이션
            <LoadingAnimation />
          ) : msg.type === 'bot' && msg.isHtml ? (
            // HTML 형태로 렌더링 (개행이 <br>로 변환됨)
            <div
              className="text-sm text-gray-800"
              dangerouslySetInnerHTML={{ __html: msg.message }}
            />
          ) : msg.type === 'bot' && msg.lines && Array.isArray(msg.lines) ? (
            // 줄별 배열로 렌더링
            <div className="text-sm text-gray-800">
              {msg.lines.map((line, index) => (
                <div key={index}>
                  {line === '' ? (
                    <br />
                  ) : (
                    <span>{line}</span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            // 기본 텍스트 렌더링
            <p className={`text-sm ${msg.type === 'user' ? 'text-white' : 'text-gray-800'}`}>
              {msg.message}
            </p>
          )}
        </div>
      </div>
    ))
  , [chatMessages])

  if (!showChatbot) return null

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center p-4"
      style={{ zIndex: 99999 }}
      onClick={() => setShowChatbot(false)}
    >
      <div
        className="bg-white rounded-lg w-full max-w-md h-[600px] flex flex-col overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
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
          <div className="flex items-center space-x-2">
            {/* 채팅 기록 초기화 버튼 */}
            <button
              onClick={async (e) => {
                e.preventDefault()
                e.stopPropagation()
                await clearChatHistory()
              }}
              className="text-white hover:text-blue-200 w-10 h-10 flex items-center justify-center rounded-full hover:bg-white/10 transition-all"
              title="채팅 기록 초기화"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
            {/* 닫기 버튼 */}
            <button
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                console.log('Close button clicked') // 디버깅용
                setShowChatbot(false)
              }}
              className="text-white hover:text-blue-200 text-2xl font-bold w-10 h-10 flex items-center justify-center rounded-full hover:bg-white/10 transition-all"
              title="채팅창 닫기"
            >
              ×
            </button>
          </div>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
          {memoizedChatMessages}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-200 bg-white">
          <form onSubmit={handleSubmit} className="flex items-center space-x-2">
            <input
              type="text"
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              onCompositionStart={handleCompositionStart}
              onCompositionEnd={handleCompositionEnd}
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

        {/* Toast Message */}
        {toast.show && (
          <div className={`absolute bottom-4 left-4 right-4 p-3 rounded-lg shadow-lg transition-all duration-300 ${
            toast.type === 'success' 
              ? 'bg-green-500 text-white' 
              : toast.type === 'error' 
              ? 'bg-red-500 text-white' 
              : 'bg-blue-500 text-white'
          }`}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{toast.message}</span>
              <button
                onClick={() => showToast('', 'info')}
                className="ml-2 text-white hover:text-gray-200"
              >
                ×
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}