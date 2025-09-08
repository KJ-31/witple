'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

export default function PlanCalendar() {
  const router = useRouter()
  const [currentDate, setCurrentDate] = useState(new Date())
  const [selectedDates, setSelectedDates] = useState<Date[]>([])
  const [isSelectingRange, setIsSelectingRange] = useState(false)

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
    
    // 선택된 날짜들을 query parameter로 전달하며 세부 일정 페이지로 이동
    const startDate = selectedDates[0].toISOString().split('T')[0]
    const endDate = selectedDates[selectedDates.length - 1].toISOString().split('T')[0]
    
    // 기존 itinerary 페이지를 활용, general을 attractionId로 사용
    router.push(`/itinerary/general?startDate=${startDate}&endDate=${endDate}&days=${selectedDates.length}`)
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
        <p className="text-[#94A9C9] text-center text-sm">
          여행 날짜를 선택하여 일정을 계획해보세요
        </p>
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
      <div className="px-6 pb-24">
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
          선택 완료
        </button>
      </div>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-[#0F1A31]/95 backdrop-blur-md border-t border-[#1F3C7A]/30">
        <div className="flex items-center justify-around px-4 py-5 max-w-md mx-auto">
          <Link
            href="/"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="홈"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </Link>

          <Link
            href="/recommendations"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="추천"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
          </Link>

          <Link
            href="/plan/calendar"
            className="flex flex-col items-center py-1 px-2 text-[#3E68FF]"
            aria-label="일정 작성"
          >
            <svg className="w-6 h-6 mb-1" fill="currentColor" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3a1 1 0 011-1h6a1 1 0 011 1v4M8 7h8M8 7H6a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V9a2 2 0 00-2-2h-2m-6 4v4m-4-2h8" />
            </svg>
          </Link>

          <Link
            href="/feed"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="피드"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
            </svg>
          </Link>

          <Link
            href="/profile"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="마이페이지"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </Link>
        </div>
      </nav>
    </div>
  )
}