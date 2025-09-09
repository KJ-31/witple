'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

interface AttractionData {
  id: string
  name: string
  description: string
  imageUrl: string
  rating: number
  category: string
  address: string
  region: string
  city: {
    id: string
    name: string
    region: string
  }
  latitude?: number
  longitude?: number
  phoneNumber?: string
  parkingAvailable?: string
  usageHours?: string
  closedDays?: string
  detailedInfo?: string
  majorCategory?: string
  middleCategory?: string
  minorCategory?: string
  imageUrls?: string[]
  businessHours?: string
  signatureMenu?: string
  menu?: string
  roomCount?: string
  roomType?: string
  checkIn?: string
  checkOut?: string
  cookingAvailable?: string
}

interface PlanCalendarProps {
  params: { attractionId: string }
}

export default function PlanCalendar({ params }: PlanCalendarProps) {
  const router = useRouter()
  const [currentDate, setCurrentDate] = useState(new Date())
  const [selectedDates, setSelectedDates] = useState<Date[]>([])
  const [isSelectingRange, setIsSelectingRange] = useState(false)
  const [attraction, setAttraction] = useState<AttractionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // API에서 관광지 상세 정보 가져오기
  useEffect(() => {
    const fetchAttractionDetail = async () => {
      try {
        setLoading(true)
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
        // attractionId가 유효한지 확인
        if (!params.attractionId || params.attractionId === 'undefined') {
          throw new Error('유효하지 않은 관광지 ID입니다.')
        }
        
        const response = await fetch(`${API_BASE_URL}/api/v1/attractions/${params.attractionId}`)
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        
        const data = await response.json()
        setAttraction(data)
      } catch (error) {
        console.error('관광지 정보 로드 오류:', error)
        setError('관광지 정보를 불러올 수 없습니다.')
      } finally {
        setLoading(false)
      }
    }

    if (params.attractionId) {
      fetchAttractionDetail()
    }
  }, [params.attractionId])

  const handleBack = () => {
    router.back()
  }

  const handleDateClick = (date: Date) => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    
    // 과거 날짜는 선택 불가
    if (date < today) return

    if (selectedDates.length === 0) {
      // 첫 번째 날짜 선택
      setSelectedDates([date])
      setIsSelectingRange(true)
    } else if (selectedDates.length === 1 && isSelectingRange) {
      // 두 번째 날짜 선택 (범위 완성)
      const startDate = selectedDates[0]
      if (date >= startDate) {
        // 시작일부터 종료일까지의 모든 날짜 생성
        const dateRange = []
        const current = new Date(startDate)
        while (current <= date) {
          dateRange.push(new Date(current))
          current.setDate(current.getDate() + 1)
        }
        setSelectedDates(dateRange)
        setIsSelectingRange(false)
      } else {
        // 시작일보다 이전 날짜를 선택한 경우, 새로 시작
        setSelectedDates([date])
      }
    } else {
      // 새로운 선택 시작
      setSelectedDates([date])
      setIsSelectingRange(true)
    }
  }

  const isDateSelected = (date: Date) => {
    return selectedDates.some(selected => 
      selected.getTime() === date.getTime()
    )
  }

  const isDateInRange = (date: Date) => {
    if (selectedDates.length < 2 || !isSelectingRange) return false
    const startDate = selectedDates[0]
    return date >= startDate && date <= new Date()
  }

  const handlePrevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1))
  }

  const handleNextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1))
  }

  const handleSelectComplete = () => {
    if (selectedDates.length === 0) return
    
    // 로컬 시간 기준으로 YYYY-MM-DD 포맷팅 (UTC 변환 없이)
    const formatLocalDate = (date: Date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }
    
    // 선택된 날짜들을 query parameter로 전달하며 세부 일정 페이지로 이동
    const startDate = formatLocalDate(selectedDates[0])
    const endDate = formatLocalDate(selectedDates[selectedDates.length - 1])
    
    router.push(`/itinerary/${params.attractionId}?startDate=${startDate}&endDate=${endDate}&days=${selectedDates.length}`)
  }

  // 캘린더 날짜 생성
  const generateCalendarDays = () => {
    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const startDate = new Date(firstDay)
    
    // 월요일부터 시작하도록 조정
    const dayOfWeek = firstDay.getDay()
    const mondayStart = dayOfWeek === 0 ? 6 : dayOfWeek - 1
    startDate.setDate(firstDay.getDate() - mondayStart)

    const days = []
    const current = new Date(startDate)
    
    // 6주간의 날짜 생성 (42일)
    for (let i = 0; i < 42; i++) {
      days.push(new Date(current))
      current.setDate(current.getDate() + 1)
    }
    
    return days
  }

  const calendarDays = generateCalendarDays()
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
          <p className="text-[#94A9C9]">여행 계획을 준비하는 중...</p>
        </div>
      </div>
    )
  }

  if (error || !attraction) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-[#94A9C9] text-lg mb-4">{error || '명소를 찾을 수 없습니다'}</p>
          <button 
            onClick={() => router.back()}
            className="text-[#3E68FF] hover:text-[#6FA0E6] transition-colors"
          >
            돌아가기
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-white overflow-y-auto no-scrollbar">
      {/* Header */}
      <div className="flex items-center justify-between p-4">
        <button
          onClick={handleBack}
          className="p-2 hover:bg-[#1F3C7A]/30 rounded-full transition-colors"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Title */}
      <div className="px-6 mb-8">
        <h1 className="text-2xl font-bold text-[#3E68FF] text-center mb-2">
          여행 기간이 어떻게 되시나요?
        </h1>
      </div>

      {/* Calendar */}
      <div className="px-6 mb-8">
        {/* Month Navigation */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={handlePrevMonth}
            className="p-2 hover:bg-[#1F3C7A]/30 rounded-full transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          
          <h2 className="text-xl font-semibold text-[#94A9C9]">
            {currentDate.getFullYear()}년 {currentDate.getMonth() + 1}월
          </h2>
          
          <button
            onClick={handleNextMonth}
            className="p-2 hover:bg-[#1F3C7A]/30 rounded-full transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* Days of Week */}
        <div className="grid grid-cols-7 gap-1 mb-2">
          {['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'].map(day => (
            <div key={day} className="text-center text-[#6FA0E6] text-sm font-medium py-2">
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Grid */}
        <div className="grid grid-cols-7 gap-1">
          {calendarDays.map((date, index) => {
            const isCurrentMonth = date.getMonth() === currentDate.getMonth()
            const isToday = date.getTime() === today.getTime()
            const isPastDate = date < today
            const isSelected = isDateSelected(date)
            const isInSelectingRange = isSelectingRange && selectedDates.length === 1 && date >= selectedDates[0]

            return (
              <button
                key={index}
                onClick={() => handleDateClick(date)}
                disabled={isPastDate}
                className={`
                  aspect-square rounded-full flex items-center justify-center text-sm font-medium transition-all duration-200
                  ${!isCurrentMonth ? 'text-[#6FA0E6]/30' : ''}
                  ${isPastDate ? 'text-[#6FA0E6]/20 cursor-not-allowed' : 'hover:bg-[#1F3C7A]/30'}
                  ${isToday && !isSelected ? 'ring-1 ring-[#3E68FF]' : ''}
                  ${isSelected ? 'bg-[#3E68FF] text-white' : 'text-[#94A9C9]'}
                  ${isInSelectingRange && !isSelected ? 'bg-[#3E68FF]/20 text-[#3E68FF]' : ''}
                `}
              >
                {date.getDate()}
              </button>
            )
          })}
        </div>
      </div>

      {/* Selected Date Info */}
      {selectedDates.length > 0 && (
        <div className="px-6 mb-8">
          <div className="bg-[#12345D]/50 rounded-2xl p-4 text-center">
            <p className="text-[#6FA0E6] text-sm mb-1">선택된 여행 기간</p>
            <p className="text-white font-semibold">
              {selectedDates.length === 1 ? (
                isSelectingRange ? 
                  `${selectedDates[0].getMonth() + 1}월 ${selectedDates[0].getDate()}일부터...` :
                  `${selectedDates[0].getMonth() + 1}월 ${selectedDates[0].getDate()}일 (당일치기)`
              ) : (
                `${selectedDates[0].getMonth() + 1}월 ${selectedDates[0].getDate()}일 - ${selectedDates[selectedDates.length - 1].getMonth() + 1}월 ${selectedDates[selectedDates.length - 1].getDate()}일 (${selectedDates.length}일)`
              )}
            </p>
          </div>
        </div>
      )}

      {/* Action Button */}
      <div className="px-6 pb-8">
        <button
          onClick={handleSelectComplete}
          disabled={selectedDates.length === 0}
          className={`
            w-full py-4 rounded-2xl text-lg font-semibold transition-all duration-200
            ${selectedDates.length > 0 
              ? 'bg-[#3E68FF] hover:bg-[#4C7DFF] text-white' 
              : 'bg-[#1F3C7A]/30 text-[#6FA0E6] cursor-not-allowed'
            }
          `}
        >
          선택
        </button>
      </div>
    </div>
  )
}