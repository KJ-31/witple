'use client'

import React, { createContext, useContext, useState, useEffect, useRef, ReactNode, useMemo, useCallback } from 'react'
import { useSession } from 'next-auth/react'

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
  clearChatHistory: () => void  // 새로운 함수 추가
  toast: {
    show: boolean
    message: string
    type: 'success' | 'error' | 'info'
  }
  showToast: (message: string, type?: 'success' | 'error' | 'info') => void
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
  const { data: session } = useSession()
  const [showChatbot, setShowChatbot] = useState(false)
  const [chatMessage, setChatMessage] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [isAppLoading, setIsAppLoading] = useState(false)
  const [hasUnreadResponse, setHasUnreadResponse] = useState(false)
  const [sessionId, setSessionId] = useState<string>(() => {
    // 초기 session_id 생성 또는 복원
    if (typeof window !== 'undefined') {
      const saved = sessionStorage.getItem('chatSessionId')
      return saved || crypto.randomUUID()
    }
    return crypto.randomUUID()
  })

  const [pendingResponseId, setPendingResponseId] = useState<number | null>(null)
  const modalClosedDuringResponseRef = useRef(false)
  const [isProcessing, setIsProcessing] = useState(false) // 중복 요청 방지
  
  // 토스트 메시지 상태
  const [toast, setToast] = useState<{
    show: boolean
    message: string
    type: 'success' | 'error' | 'info'
  }>({
    show: false,
    message: '',
    type: 'info'
  })

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

  // session_id를 sessionStorage에 저장
  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('chatSessionId', sessionId)
    }
  }, [sessionId])

  // 모달 상태 변화 추적
  useEffect(() => {
    if (showChatbot) {
      // 모달이 열리면 알림 클리어
      setHasUnreadResponse(false)
      modalClosedDuringResponseRef.current = false
    } else {
      // 모달이 닫히면서 진행 중인 응답이 있으면 플래그 설정
      if (pendingResponseId !== null) {
        modalClosedDuringResponseRef.current = true
      }
    }
  }, [showChatbot, pendingResponseId])

  const clearNotification = useCallback(() => {
    setHasUnreadResponse(false)
    setPendingResponseId(null)
    modalClosedDuringResponseRef.current = false
  }, [])

  // 토스트 메시지 함수
  const showToast = useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ show: true, message, type })
    setTimeout(() => {
      setToast({ show: false, message: '', type: 'info' })
    }, 3000) // 3초 후 자동 사라짐
  }, [])

  const clearChatHistory = useCallback(async () => {
    try {
      // 1. 새로운 session_id 생성
      const newSessionId = crypto.randomUUID()
      setSessionId(newSessionId)

      // 2. 백엔드 여행 상태 초기화
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      }

      // 인증 헤더 추가 (배포 환경 호환성 개선)
      const token = (session as any)?.backendToken || session?.accessToken
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      } else {
        console.warn('⚠️ 채팅 API 호출 시 인증 토큰이 없습니다. 세션 상태:', !!session)
      }

      await fetch(`${API_BASE_URL}/api/v1/chat/clear-state`, {
        method: 'POST',
        headers
      })

      // 3. 프론트엔드 채팅 메시지 초기화
      const initialMessage = {
        id: Date.now(),
        type: 'bot' as const,
        message: '쉽게 여행 계획을 작성해볼래?',
        timestamp: new Date()
      }
      setChatMessages([initialMessage])

      // 4. sessionStorage 초기화
      sessionStorage.removeItem('chatMessages')
      sessionStorage.setItem('chatSessionId', newSessionId)

      // 5. 알림 상태 초기화
      clearNotification()

      // 6. 성공 토스트 메시지 표시
      showToast('채팅 기록이 초기화되었습니다!', 'success')

      console.log('✅ 채팅 기록 및 여행 상태 초기화 완료')

    } catch (error) {
      console.error('❌ 채팅 기록 초기화 실패:', error)

      // 에러가 발생해도 프론트엔드 상태는 초기화
      const newSessionId = crypto.randomUUID()
      setSessionId(newSessionId)

      const initialMessage = {
        id: Date.now(),
        type: 'bot' as const,
        message: '쉽게 여행 계획을 작성해볼래?',
        timestamp: new Date()
      }
      setChatMessages([initialMessage])
      sessionStorage.removeItem('chatMessages')
      sessionStorage.setItem('chatSessionId', newSessionId)
      clearNotification()

      // 에러 토스트 메시지 표시
      showToast('채팅 기록 초기화 중 오류가 발생했습니다.', 'error')
    }
  }, [session, showToast, clearNotification])

  const handleChatSubmit = useCallback(async (messageText: string) => {
    if (!messageText.trim()) return
    
    // 중복 요청 방지
    if (isProcessing) {
      console.log('⚠️ 이미 처리 중인 요청이 있습니다. 중복 요청을 무시합니다.')
      return
    }
    
    setIsProcessing(true)

    // 새로운 여행 요청인지 감지 (간단한 키워드 기반)
    const messageTextLower = messageText.toLowerCase()
    const travelKeywords = ['추천', '여행', '일정', '계획', '가고싶어', '놀러', '구경', '관광']
    const regionKeywords = ['서울', '부산', '제주', '강릉', '경주', '전주', '대구', '광주', '인천']
    const questionPatterns = ['어디', '뭐', '뭘', '어떤', '추천해', '알려줘', '가볼만한']
    
    const isNewTravelRequest = (
      travelKeywords.some(keyword => messageTextLower.includes(keyword)) ||
      regionKeywords.some(keyword => messageTextLower.includes(keyword)) ||
      questionPatterns.some(pattern => messageTextLower.includes(pattern))
    )

    // 새로운 여행 요청이면 백엔드 상태 클리어
    if (isNewTravelRequest) {
      try {
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
        await fetch(`${API_BASE_URL}/api/v1/chat/clear-state`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          }
        })
        console.log('🔄 백엔드 여행 상태 초기화됨')
      } catch (error) {
        console.warn('백엔드 상태 초기화 실패:', error)
      }
    }

    // 사용자 메시지 추가
    const userMessage: ChatMessage = {
      id: Date.now(),
      type: 'user',
      message: messageText,
      timestamp: new Date()
    }

    setChatMessages(prev => [...prev, userMessage])

    // 다양한 로딩 메시지들
    const loadingMessages = [
      '답변을 생성하고 있습니다...',
      '여행 정보를 검색하고 있습니다...',
      'AI가 최적의 여행 계획을 준비 중입니다...',
      '맞춤형 추천을 생성하고 있습니다...',
      '최신 여행 정보를 수집하고 있습니다...'
    ]

    // 랜덤한 로딩 메시지 선택
    const randomLoadingMessage = loadingMessages[Math.floor(Math.random() * loadingMessages.length)]

    // 로딩 메시지 추가
    const loadingMessage: ChatMessage = {
      id: Date.now() + 1,
      type: 'bot',
      message: randomLoadingMessage,
      timestamp: new Date()
    }
    setChatMessages(prev => [...prev, loadingMessage])

    // 진행 중인 응답 추적 (모달이 닫혔을 때 알림을 위해)
    setPendingResponseId(loadingMessage.id)

    try {
      // API 호출
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      }

      // 인증 헤더 추가 (배포 환경 호환성 개선)
      const token = (session as any)?.backendToken || session?.accessToken
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      } else {
        console.warn('⚠️ 채팅 API 호출 시 인증 토큰이 없습니다. 세션 상태:', !!session)

        // 토큰이 없으면 에러 메시지 표시하고 조기 return
        setChatMessages(prev => {
          const filteredMessages = prev.filter(msg => msg.id !== loadingMessage.id)
          const errorResponse: ChatMessage = {
            id: Date.now() + 2,
            type: 'bot',
            message: '로그인이 필요한 서비스입니다. 다시 로그인해주세요.',
            timestamp: new Date()
          }
          return [...filteredMessages, errorResponse]
        })

        setIsProcessing(false)
        setPendingResponseId(null)
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: messageText,
          session_id: sessionId
        })
      })

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('인증이 만료되었습니다. 다시 로그인해주세요.')
        }
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
      if (modalClosedDuringResponseRef.current) {
        setHasUnreadResponse(true)
      }

      // pendingResponseId 초기화 및 플래그 리셋
      setPendingResponseId(null)
      modalClosedDuringResponseRef.current = false
      
      // 처리 완료
      setIsProcessing(false)

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
      if (modalClosedDuringResponseRef.current) {
        setHasUnreadResponse(true)
      }

      // pendingResponseId 초기화 및 플래그 리셋
      setPendingResponseId(null)
      modalClosedDuringResponseRef.current = false
      
      // 에러 발생 시에도 처리 완료
      setIsProcessing(false)

    }
  }, [sessionId, session, isProcessing, setChatMessages, setPendingResponseId, modalClosedDuringResponseRef, setIsProcessing, setHasUnreadResponse])

  const value: ChatbotContextType = useMemo(() => ({
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
    clearNotification,
    clearChatHistory,
    toast,
    showToast
  }), [
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
    clearNotification,
    clearChatHistory,
    toast,
    showToast
  ])

  return (
    <ChatbotContext.Provider value={value}>
      {children}
    </ChatbotContext.Provider>
  )
}