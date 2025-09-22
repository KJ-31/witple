'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { signIn } from 'next-auth/react'
import { register, saveUserPreferences, login } from './api'

interface TravelPreferences {
  travelStyle: string
  investment: string
  accommodation: string
  destination: string
}

export default function RegisterPage() {
  const [step, setStep] = useState(1)
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: ''
  })
  const [preferences, setPreferences] = useState<TravelPreferences>({
    travelStyle: '',
    investment: '',
    accommodation: '',
    destination: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  const handlePreferenceChange = (key: keyof TravelPreferences, value: string) => {
    setPreferences(prev => ({
      ...prev,
      [key]: value
    }))
  }


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    if (formData.password !== formData.confirmPassword) {
      setError('비밀번호가 일치하지 않습니다.')
      setLoading(false)
      return
    }

    try {
      // 1. 기본 회원가입
      console.log('회원가입 데이터:', { ...formData, preferences })
      await register(formData.email, formData.password, formData.full_name)

      // 2. 로그인하여 토큰 받기
      const loginResponse = await login(formData.email, formData.password)
      const token = loginResponse.access_token

      // 3. 선호도 저장
      if (preferences.travelStyle && preferences.investment && preferences.accommodation && preferences.destination) {
        await saveUserPreferences(preferences, token)
        console.log('선호도 저장 완료')

        // 회원가입시 취향설정 완료 플래그 설정
        localStorage.setItem('preferences_completed', 'true')
        console.log('회원가입 취향설정 완료 - localStorage 플래그 설정됨')
      }

      // 4. 토큰 저장
      localStorage.setItem('token', token)

      router.push('/auth/login?message=registration_success')
    } catch (err: any) {
      console.error('회원가입 오류:', err)
      setError(`회원가입에 실패했습니다: ${err.response?.data?.detail || err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const nextStep = () => {
    if (step < 5) setStep(step + 1)
  }

  const prevStep = () => {
    if (step > 1) setStep(step - 1)
  }

  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-medium text-white mb-4">기본 정보를 입력해주세요</h3>
            </div>
            <div className="space-y-4">
              <input
                name="full_name"
                type="text"
                required
                className="w-full px-4 py-3 bg-[#12345D]/50 border border-[#1F3C7A] rounded-2xl text-white placeholder-[#6FA0E6] focus:outline-none focus:ring-2 focus:ring-[#3E68FF] focus:border-transparent"
                placeholder="이름"
                value={formData.full_name}
                onChange={handleChange}
              />
              <input
                name="email"
                type="email"
                required
                className="w-full px-4 py-3 bg-[#12345D]/50 border border-[#1F3C7A] rounded-2xl text-white placeholder-[#6FA0E6] focus:outline-none focus:ring-2 focus:ring-[#3E68FF] focus:border-transparent"
                placeholder="이메일"
                value={formData.email}
                onChange={handleChange}
              />
              <input
                name="password"
                type="password"
                required
                className="w-full px-4 py-3 bg-[#12345D]/50 border border-[#1F3C7A] rounded-2xl text-white placeholder-[#6FA0E6] focus:outline-none focus:ring-2 focus:ring-[#3E68FF] focus:border-transparent"
                placeholder="비밀번호"
                value={formData.password}
                onChange={handleChange}
              />
              <input
                name="confirmPassword"
                type="password"
                required
                className="w-full px-4 py-3 bg-[#12345D]/50 border border-[#1F3C7A] rounded-2xl text-white placeholder-[#6FA0E6] focus:outline-none focus:ring-2 focus:ring-[#3E68FF] focus:border-transparent"
                placeholder="비밀번호 확인"
                value={formData.confirmPassword}
                onChange={handleChange}
              />
            </div>
            <div className="space-y-3">
              <button
                type="button"
                onClick={nextStep}
                className="w-full py-3 bg-[#3E68FF] hover:bg-[#4C7DFF] rounded-2xl text-white font-semibold transition-colors"
              >
                다음 단계 → 여행 취향 알아보기
              </button>

              {/* <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-300" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-gray-50 text-gray-500">또는</span>
                </div>
              </div> */}

              {/* <button
                type="button"
                onClick={() => signIn('google', { callbackUrl: '/dashboard' })}
                className="w-full flex justify-center items-center py-3 px-4 border border-gray-300 text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Google로 계속하기
              </button> */}
            </div>
          </div>
        )

      case 2:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-medium text-white mb-2">최고의 여행 모습 👉</h3>
              <p className="text-sm text-[#94A9C9]">어떤 여행이 가장 매력적으로 느껴지시나요?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'luxury', emoji: '🏖️', label: '럭셔리 리조트 휴식', desc: '편안하고 여유로운 휴식' },
                { id: 'modern', emoji: '🌆', label: '도시 문화와 쇼핑', desc: '활기찬 도시 생활 체험' },
                { id: 'nature_activity', emoji: '⛰️', label: '대자연 속 모험', desc: '자연 속에서의 모험과 액티비티' },
                { id: 'foodie', emoji: '🍽️', label: '현지 맛집 탐방', desc: '다양한 현지 음식 체험' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${preferences.travelStyle === option.id
                    ? 'border-[#3E68FF] bg-[#3E68FF]/10'
                    : 'border-[#1F3C7A] bg-[#0F1A31]/50 hover:border-[#3E68FF]/50'
                    }`}
                >
                  <input
                    type="radio"
                    name="travelStyle"
                    value={option.id}
                    checked={preferences.travelStyle === option.id}
                    onChange={(e) => handlePreferenceChange('travelStyle', e.target.value)}
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
              <h3 className="text-lg font-medium text-white mb-2">아끼고 싶지 않은 것 👉</h3>
              <p className="text-sm text-[#94A9C9]">여행에서 투자를 아끼지 않고 싶은 부분은?</p>
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
                  className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${preferences.investment === option.id
                    ? 'border-[#3E68FF] bg-[#3E68FF]/10'
                    : 'border-[#1F3C7A] bg-[#0F1A31]/50 hover:border-[#3E68FF]/50'
                    }`}
                >
                  <input
                    type="radio"
                    name="investment"
                    value={option.id}
                    checked={preferences.investment === option.id}
                    onChange={(e) => handlePreferenceChange('investment', e.target.value)}
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

      case 4:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-medium text-white mb-2">선호하는 숙소 유형 👉</h3>
              <p className="text-sm text-[#94A9C9]">여행의 피로를 풀어줄 숙소, 어떤 곳을 선호하시나요?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'comfort', emoji: '🏨', label: '완벽한 서비스와 편리함', desc: '모든 것이 갖춰진 편안함 (관광호텔, 서비스드레지던스)' },
                { id: 'healing', emoji: '🏡', label: '자연 속 아늑한 휴식처', desc: '프라이빗한 우리만의 공간 (펜션, 콘도미니엄)' },
                { id: 'traditional', emoji: '🏯', label: '한국의 멋과 정취', desc: '전통 가옥에서의 특별한 하룻밤 (한옥, 템플스테이)' },
                { id: 'community', emoji: '🥂', label: '새로운 만남과 교류', desc: '여행의 즐거움을 나누는 공간 (게스트하우스, 민박)' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${preferences.accommodation === option.id
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

      case 5:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-medium text-white mb-2">여행지 선택 스타일 👉</h3>
              <p className="text-sm text-[#94A9C9]">낯선 여행지에서 당신의 선택은?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'hot', emoji: '🗺️', label: '모두가 인정하는 필수 명소', desc: '실패 없는 여행을 위한 검증된 랜드마크' },
                { id: 'local', emoji: '🤫', label: '현지인만 아는 숨은 명소', desc: '나만 알고 싶은 골목길과 로컬 스팟' },
                { id: 'balance', emoji: '🧭', label: '유명한 곳과 숨은 곳의 조화', desc: '중심가를 여행하되, 가끔은 골목으로!' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${preferences.destination === option.id
                    ? 'border-[#3E68FF] bg-[#3E68FF]/10'
                    : 'border-[#1F3C7A] bg-[#0F1A31]/50 hover:border-[#3E68FF]/50'
                    }`}
                >
                  <input
                    type="radio"
                    name="destination"
                    value={option.id}
                    checked={preferences.destination === option.id}
                    onChange={(e) => handlePreferenceChange('destination', e.target.value)}
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
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#3E68FF] hover:bg-[#4C7DFF] rounded-2xl text-white font-semibold transition-colors disabled:opacity-50"
            >
              {loading ? '가입 중...' : '🎉 회원가입 완료'}
            </button>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-white">
      {/* Header with back button */}
      <div className="flex items-center justify-between p-4 h-20">
        <button
          onClick={() => router.back()}
          className="p-2 hover:bg-[#1F3C7A]/30 rounded-full transition-colors"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="text-lg font-semibold text-white">회원가입</h1>
        <div className="w-10"></div>
      </div>

      <div className="flex items-center justify-center px-6 pb-20">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            <h2 className="text-3xl font-bold text-[#3E68FF] mb-2">
              {step === 1 ? '회원가입' : `여행 취향 알아보기 (${step - 1}/4)`}
            </h2>
            <p className="text-[#94A9C9] text-sm">
              또는{' '}
              <Link href="/auth/login" className="font-medium text-[#3E68FF] hover:text-[#4C7DFF]">
                기존 계정으로 로그인
              </Link>
            </p>
          </div>

          {/* 진행 표시줄 */}
          {step > 1 && (
            <div className="w-full bg-[#1F3C7A]/30 rounded-full h-2">
              <div
                className="bg-[#3E68FF] h-2 rounded-full transition-all duration-300"
                style={{ width: `${((step - 1) / 4) * 100}%` }}
              ></div>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {error && (
              <div className="bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-3 rounded-2xl mb-4">
                {error}
              </div>
            )}

            {renderStep()}

            {step > 1 && step < 5 && (
              <div className="flex justify-between space-x-4 mt-6">
                <button
                  type="button"
                  onClick={prevStep}
                  className="flex-1 flex justify-center py-3 px-4 border border-[#1F3C7A] text-sm font-medium rounded-2xl text-[#94A9C9] bg-[#1F3C7A]/50 hover:bg-[#1F3C7A]/70 focus:outline-none focus:ring-2 focus:ring-[#3E68FF]"
                >
                  ← 이전
                </button>
                <button
                  type="button"
                  onClick={nextStep}
                  className="flex-1 flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-2xl text-white bg-[#3E68FF] hover:bg-[#4C7DFF] focus:outline-none focus:ring-2 focus:ring-[#3E68FF]"
                >
                  다음 →
                </button>
              </div>
            )}
          </form>
        </div>
      </div>
    </div>
  )
}
