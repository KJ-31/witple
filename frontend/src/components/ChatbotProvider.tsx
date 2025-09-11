'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface ChatMessage {
  id: number
  type: 'user' | 'bot'
  message: string
  timestamp: Date
}

interface ChatbotContextType {
  showChatbot: boolean
  setShowChatbot: (show: boolean) => void
  chatMessage: string
  setChatMessage: (message: string) => void
  chatMessages: ChatMessage[]
  setChatMessages: (messages: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void
  handleChatSubmit: (message: string) => Promise<void>
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
          message: data.response || '죄송합니다. 응답을 생성할 수 없습니다.',
          timestamp: new Date()
        }
        return [...filteredMessages, botResponse]
      })


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

    }
  }

  const value: ChatbotContextType = {
    showChatbot,
    setShowChatbot,
    chatMessage,
    setChatMessage,
    chatMessages,
    setChatMessages,
    handleChatSubmit
  }

  return (
    <ChatbotContext.Provider value={value}>
      {children}
    </ChatbotContext.Provider>
  )
}