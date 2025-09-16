'use client'

import React, { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { useChatbot } from './ChatbotProvider'

export function ChatbotButton() {
  const { setShowChatbot, isAppLoading, hasUnreadResponse, clearNotification } = useChatbot()
  const pathname = usePathname()

  // 표시해야 할 페이지 경로들 (메인화면과 추천탭에서만 표시)
  const allowedPaths = ['/', '/recommendations']


  // 현재 경로가 허용된 페이지가 아니거나 로딩 중이면 렌더링하지 않음
  if (!allowedPaths.some(path => {
    if (path === '/') {
      return pathname === '/'  // 메인화면은 정확히 일치해야 함
    }
    return pathname.startsWith(path)  // 추천탭은 startsWith로 체크
  }) || isAppLoading) {
    return null
  }

  return (
    <div className="fixed z-50 bottom-[100px] right-4 sm:right-6 md:right-8 lg:right-9">
      <div className="relative">
        <button
          onClick={() => {
            setShowChatbot(true)
            if (hasUnreadResponse) {
              clearNotification()
            }
          }}
          className="
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

        {/* 알림 아이콘 - 버튼 위 오른쪽 모서리 */}
        {hasUnreadResponse && (
          <div
            className="notification-dot"
            style={{
              position: 'absolute',
              top: '-4px',
              right: '-4px',
              width: '20px',
              height: '20px',
              backgroundColor: '#ef4444',

              borderRadius: '50%',
              zIndex: 99999,
              boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
              animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
            }}
          >
          </div>
        )}
      </div>
    </div>
  )
}