'use client'

import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react'

interface ChatMessage {
  id: number
  type: 'user' | 'bot'
  message: string
  timestamp: Date
  isHtml?: boolean  // HTML 형태인지 여부
  lines?: string[]  // 줄별 배열 데이터
  formatted_response?: any  // 구조화된 응답 데이터
}

interface ChatbotContextType {
  showChatbot: boolean
  setShowChatbot: (show: boolean) => void
  chatMessage: string
  setChatMessage: (message: string) => void
  chatMessages: ChatMessage[]
  setChatMessages: (messages: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void
  handleChatSubmit: (message: string) => Promise<void>
  isAppLoading: boolean
  setIsAppLoading: (loading: boolean) => void
  hasUnreadResponse: boolean
  clearNotification: () => void
}

const ChatbotContext = createContext<ChatbotContextType | undefined>(undefined)

export function useChatbot() {
  const context = useContext(ChatbotContext)
  if (context === undefined) {
    throw new Error('useChatbot must be used within a ChatbotProvider')
  }
  return context
}

interface ChatbotProviderProps {
  children: ReactNode
}

export function ChatbotProvider({ children }: ChatbotProviderProps) {
  const [showChatbot, setShowChatbot] = useState(false)
  const [chatMessage, setChatMessage] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [isAppLoading, setIsAppLoading] = useState(false)
  const [hasUnreadResponse, setHasUnreadResponse] = useState(false)

  // hasUnreadResponse 상태 변화 추적
  useEffect(() => {
    console.log('🔔 hasUnreadResponse 상태 변경됨:', hasUnreadResponse)
  }, [hasUnreadResponse])
  const [pendingResponseId, setPendingResponseId] = useState<number | null>(null)
  const modalClosedDuringResponseRef = useRef(false)

  // 초기 메시지 및 저장된 메시지 로드
  useEffect(() => {
    const loadChatMessages = () => {
      try {
        const savedMessages = sessionStorage.getItem('chatMessages')
        
        if (savedMessages) {
          const parsedMessages = JSON.parse(savedMessages)
          // 날짜 객체 복원
          const messagesWithDates = parsedMessages.map((msg: any) => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
          }))
          setChatMessages(messagesWithDates)
        } else {
          // 저장된 메시지가 없으면 초기 메시지 설정
          const initialMessage = {
            id: 1,
            type: 'bot' as const,
            message: '쉽게 여행 계획을 작성해볼래?',
            timestamp: new Date()
          }
          setChatMessages([initialMessage])
        }
      } catch (error) {
        console.error('채팅 메시지 로드 오류:', error)
        // 오류 시 초기 메시지 설정
        const initialMessage = {
          id: 1,
          type: 'bot' as const,
          message: '쉽게 여행 계획을 작성해볼래?',
          timestamp: new Date()
        }
        setChatMessages([initialMessage])
      }
    }

    loadChatMessages()
  }, [])

  // 메시지 변경 시 sessionStorage에 저장
  useEffect(() => {
    if (chatMessages.length > 0) {
      try {
        sessionStorage.setItem('chatMessages', JSON.stringify(chatMessages))
      } catch (error) {
        console.error('채팅 메시지 저장 오류:', error)
      }
    }
  }, [chatMessages])

  // 모달 상태 변화 추적
  useEffect(() => {
    console.log('🔄 모달 상태 변경:', showChatbot ? '열림' : '닫힘')

    if (showChatbot) {
      // 모달이 열리면 알림 클리어
      console.log('🔔 모달이 열림 - 알림 클리어')
      setHasUnreadResponse(false)
      modalClosedDuringResponseRef.current = false
    } else {
      // 모달이 닫히면서 진행 중인 응답이 있으면 플래그 설정
      console.log('🚪 모달이 닫힘 - pendingResponseId:', pendingResponseId)
      if (pendingResponseId !== null) {
        console.log('🚪 모달이 닫힘 - 진행 중인 응답 있음, 알림 플래그 설정')
        modalClosedDuringResponseRef.current = true
        console.log('🚪 modalClosedDuringResponseRef.current 설정됨:', modalClosedDuringResponseRef.current)
      } else {
        console.log('🚪 모달이 닫힘 - 진행 중인 응답 없음')
      }
    }
  }, [showChatbot, pendingResponseId])

  const clearNotification = () => {
    setHasUnreadResponse(false)
    setPendingResponseId(null)
    modalClosedDuringResponseRef.current = false
  }

  const handleChatSubmit = async (messageText: string) => {
    if (!messageText.trim()) return

    // 사용자 메시지 추가
    const userMessage: ChatMessage = {
      id: Date.now(),
      type: 'user',
      message: messageText,
      timestamp: new Date()
    }

    setChatMessages(prev => [...prev, userMessage])

    // 로딩 메시지 추가
    const loadingMessage: ChatMessage = {
      id: Date.now() + 1,
      type: 'bot',
      message: '답변을 생성하고 있습니다...',
      timestamp: new Date()
    }
    setChatMessages(prev => [...prev, loadingMessage])

    // 진행 중인 응답 추적 (모달이 닫혔을 때 알림을 위해)
    console.log('📤 메시지 전송 - pendingResponseId 설정:', loadingMessage.id)
    setPendingResponseId(loadingMessage.id)

    try {
      // API 호출
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: messageText
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      // 로딩 메시지 제거 후 실제 응답 추가
      setChatMessages(prev => {
        const filteredMessages = prev.filter(msg => msg.id !== loadingMessage.id)
        const botResponse: ChatMessage = {
          id: Date.now() + 2,
          type: 'bot',
          message: data.response_html || data.response || '죄송합니다. 응답을 생성할 수 없습니다.',
          timestamp: new Date(),
          isHtml: !!data.response_html,  // HTML 형태인지 표시
          lines: data.response_lines,    // 줄별 배열 데이터
          formatted_response: data.formatted_response  // 구조화된 데이터
        }

        // 리다이렉트 URL이 있으면 페이지 이동
        if (data.redirect_url) {
          console.log('🗺️ 지도 페이지로 리다이렉트:', data.redirect_url)
          setTimeout(() => {
            window.location.href = data.redirect_url
          }, 2000) // 2초 후 리다이렉트 (사용자가 확정 메시지를 읽을 시간 제공)
        }

        return [...filteredMessages, botResponse]
      })

      // 응답 완료 후 알림 처리
      console.log('🔔 응답 완료:', {
        pendingResponseId,
        loadingMessageId: loadingMessage.id,
        modalClosedDuringResponse: modalClosedDuringResponseRef.current,
        currentShowChatbot: showChatbot
      })

      // pendingResponseId 체크 없이 modalClosedDuringResponseRef만 확인
      console.log('🔄 알림 체크 - modalClosedDuringResponse:', modalClosedDuringResponseRef.current)

      // 모달이 응답 중에 닫힌 경우에만 알림 표시
      if (modalClosedDuringResponseRef.current) {
        console.log('🔴 알림 설정됨 - 모달이 응답 중에 닫혔음')
        setHasUnreadResponse(true)
        console.log('🔴 setHasUnreadResponse(true) 호출됨')

        // 상태 변경이 즉시 적용되는지 확인
        setTimeout(() => {
          console.log('🔴 1초 후 hasUnreadResponse 상태 확인 필요')
        }, 1000)
      } else {
        console.log('🟡 알림 설정 안함 - 모달이 열린 상태에서 응답 완료')
      }

      // pendingResponseId 초기화 및 플래그 리셋
      setPendingResponseId(null)
      modalClosedDuringResponseRef.current = false


    } catch (error) {
      console.error('Chat API error:', error)
      
      // 로딩 메시지 제거 후 에러 메시지 추가
      setChatMessages(prev => {
        const filteredMessages = prev.filter(msg => msg.id !== loadingMessage.id)
        const errorResponse: ChatMessage = {
          id: Date.now() + 2,
          type: 'bot',
          message: '죄송합니다. 현재 서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.',
          timestamp: new Date()
        }
        return [...filteredMessages, errorResponse]
      })

      // 에러 발생 시에도 알림 처리
      console.log('❌ 에러 발생 후 알림 처리:', {
        pendingResponseId,
        loadingMessageId: loadingMessage.id,
        modalClosedDuringResponse: modalClosedDuringResponseRef.current,
        currentShowChatbot: showChatbot
      })

      // 모달이 응답 중에 닫힌 경우에만 알림 표시
      if (modalClosedDuringResponseRef.current) {
        console.log('🔴 알림 설정됨 - 모달이 응답 중에 닫혔는데 에러 발생')
        setHasUnreadResponse(true)
      } else {
        console.log('🟡 알림 설정 안함 - 모달이 열린 상태에서 에러 발생')
      }

      // pendingResponseId 초기화 및 플래그 리셋
      setPendingResponseId(null)
      modalClosedDuringResponseRef.current = false

    }
  }

  const value: ChatbotContextType = {
    showChatbot,
    setShowChatbot,
    chatMessage,
    setChatMessage,
    chatMessages,
    setChatMessages,
    handleChatSubmit,
    isAppLoading,
    setIsAppLoading,
    hasUnreadResponse,
    clearNotification
  }

  return (
    <ChatbotContext.Provider value={value}>
      {children}
    </ChatbotContext.Provider>
  )
}