'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'

interface TravelPreferences {
  persona: string
  priority: string
  accommodation: string
  exploration: string
}

export default function PreferencesPage() {
  const router = useRouter()
  const { data: session } = useSession()
  const [preferences, setPreferences] = useState<TravelPreferences>({
    persona: '',
    priority: '',
    accommodation: '',
    exploration: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [step, setStep] = useState(1)

  const handlePreferenceChange = (key: keyof TravelPreferences, value: string) => {
    setPreferences(prev => ({
      ...prev,
      [key]: value
    }))
  }

  const nextStep = () => {
    if (step < 4) setStep(step + 1)
  }

  const prevStep = () => {
    if (step > 1) setStep(step - 1)
  }

  const handleSubmit = async () => {
    if (!preferences.persona || !preferences.priority || !preferences.accommodation || !preferences.exploration) {
      setError('모든 항목을 선택해주세요.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const token = (session as any)?.backendToken

      if (!token) {
        throw new Error('인증 토큰이 없습니다.')
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/users/preferences`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          persona: preferences.persona,
          priority: preferences.priority,
          accommodation: preferences.accommodation,
          exploration: preferences.exploration
        })
      })

      if (!response.ok) {
        throw new Error('선호도 저장에 실패했습니다.')
      }

      // 선호도 설정 완료 플래그 저장
      localStorage.setItem('preferences_completed', 'true')
      
      // 메인 페이지로 이동
      router.push('/')
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-2xl font-bold text-white mb-2">🏖️ 최고의 여행 모습</h3>
              <p className="text-[#94A9C9]">어떤 여행을 선호하시나요?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'luxury', label: '럭셔리 리조트 휴식', desc: '편안하고 여유로운 휴식' },
                { id: 'modern', label: '도시 문화와 쇼핑', desc: '활기찬 도시 생활 체험' },
                { id: 'nature_activity', label: '대자연 속 모험', desc: '자연 속에서의 모험과 액티비티' },
                { id: 'foodie', label: '현지 맛집 탐방', desc: '다양한 현지 음식 체험' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${
                    preferences.persona === option.id
                      ? 'border-[#3E68FF] bg-[#3E68FF]/10'
                      : 'border-[#1F3C7A] bg-[#0F1A31]/50 hover:border-[#3E68FF]/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="persona"
                    value={option.id}
                    checked={preferences.persona === option.id}
                    onChange={(e) => handlePreferenceChange('persona', e.target.value)}
                    className="hidden"
                  />
                  <div>
                    <p className="font-medium text-white">{option.label}</p>
                    <p className="text-sm text-[#94A9C9]">{option.desc}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )

      case 2:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-2xl font-bold text-white mb-2">💰 아끼고 싶지 않은 것</h3>
              <p className="text-[#94A9C9]">여행에서 투자를 아끼지 않고 싶은 부분은?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'accommodation', emoji: '😴', label: '숙소', desc: '편안하고 좋은 숙소' },
                { id: 'restaurants', emoji: '🍽️', label: '음식', desc: '맛있는 현지 음식과 고급 레스토랑' },
                { id: 'experience', emoji: '🎭', label: '경험', desc: '특별한 체험과 액티비티' },
                { id: 'shopping', emoji: '🛍️', label: '쇼핑', desc: '기념품과 현지 특산품' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${
                    preferences.priority === option.id
                      ? 'border-[#3E68FF] bg-[#3E68FF]/10'
                      : 'border-[#1F3C7A] bg-[#0F1A31]/50 hover:border-[#3E68FF]/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="priority"
                    value={option.id}
                    checked={preferences.priority === option.id}
                    onChange={(e) => handlePreferenceChange('priority', e.target.value)}
                    className="hidden"
                  />
                  <div className="flex items-center space-x-3">
                    <span className="text-2xl">{option.emoji}</span>
                    <div>
                      <p className="font-medium text-white">{option.label}</p>
                      <p className="text-sm text-[#94A9C9]">{option.desc}</p>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )

      case 3:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-2xl font-bold text-white mb-2">🏨 선호하는 숙소</h3>
              <p className="text-[#94A9C9]">어떤 숙소를 선호하시나요?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'comfort', label: '편안함', desc: '편리하고 쾌적한 숙소' },
                { id: 'healing', label: '힐링', desc: '휴식과 힐링이 가능한 숙소' },
                { id: 'traditional', label: '전통', desc: '현지 전통을 체험할 수 있는 숙소' },
                { id: 'community', label: '커뮤니티', desc: '다른 여행자들과 교류할 수 있는 숙소' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${
                    preferences.accommodation === option.id
                      ? 'border-[#3E68FF] bg-[#3E68FF]/10'
                      : 'border-[#1F3C7A] bg-[#0F1A31]/50 hover:border-[#3E68FF]/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="accommodation"
                    value={option.id}
                    checked={preferences.accommodation === option.id}
                    onChange={(e) => handlePreferenceChange('accommodation', e.target.value)}
                    className="hidden"
                  />
                  <div>
                    <p className="font-medium text-white">{option.label}</p>
                    <p className="text-sm text-[#94A9C9]">{option.desc}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )

      case 4:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-2xl font-bold text-white mb-2">🗺️ 탐험 스타일</h3>
              <p className="text-[#94A9C9]">어떤 방식으로 여행지를 탐험하고 싶으신가요?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'hot', label: '핫플레이스', desc: '인기 있는 관광지 위주' },
                { id: 'local', label: '로컬', desc: '현지인들이 가는 곳' },
                { id: 'balance', label: '밸런스', desc: '인기 장소와 숨은 장소의 균형' },
                { id: 'authentic_experience', label: '진정한 경험', desc: '진짜 현지 문화 체험' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${
                    preferences.exploration === option.id
                      ? 'border-[#3E68FF] bg-[#3E68FF]/10'
                      : 'border-[#1F3C7A] bg-[#0F1A31]/50 hover:border-[#3E68FF]/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="exploration"
                    value={option.id}
                    checked={preferences.exploration === option.id}
                    onChange={(e) => handlePreferenceChange('exploration', e.target.value)}
                    className="hidden"
                  />
                  <div>
                    <p className="font-medium text-white">{option.label}</p>
                    <p className="text-sm text-[#94A9C9]">{option.desc}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-slate-200">
      {/* Header */}
      <div className="px-4 pt-16 pb-8">
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => router.back()}
            className="p-2 text-[#94A9C9] hover:text-white transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-xl font-semibold text-white">여행 취향 설정</h1>
          <div className="w-10"></div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-[#1F3C7A]/30 rounded-full h-2 mb-8">
          <div 
            className="bg-[#3E68FF] h-2 rounded-full transition-all duration-300"
            style={{ width: `${(step / 4) * 100}%` }}
          ></div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 pb-8">
        {renderStep()}
      </div>

      {/* Error Message */}
      {error && (
        <div className="px-4 mb-4">
          <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-4">
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="px-4 pb-8">
        <div className="flex space-x-3">
          {step > 1 && (
            <button
              onClick={prevStep}
              className="flex-1 py-3 px-6 bg-[#1F3C7A]/50 hover:bg-[#1F3C7A]/70 border border-[#1F3C7A] rounded-2xl text-[#94A9C9] font-medium transition-colors"
            >
              이전
            </button>
          )}
          
          {step < 4 ? (
            <button
              onClick={nextStep}
              disabled={!preferences[Object.keys(preferences)[step - 1] as keyof TravelPreferences]}
              className="flex-1 py-3 px-6 bg-[#3E68FF] hover:bg-[#4C7DFF] disabled:bg-[#1F3C7A]/30 disabled:text-[#6FA0E6] rounded-2xl text-white font-medium transition-colors"
            >
              다음
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="flex-1 py-3 px-6 bg-[#3E68FF] hover:bg-[#4C7DFF] disabled:bg-[#1F3C7A]/30 disabled:text-[#6FA0E6] rounded-2xl text-white font-medium transition-colors"
            >
              {loading ? '저장 중...' : '완료'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
