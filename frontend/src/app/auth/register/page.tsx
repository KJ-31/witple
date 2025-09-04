'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { register } from './api'

interface TravelPreferences {
  travelStyle: string
  investment: string
  accommodation: string
  destination: string
  experiences: string[]
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
    destination: '',
    experiences: []
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

  const handleExperienceToggle = (experience: string) => {
    setPreferences(prev => ({
      ...prev,
      experiences: prev.experiences.includes(experience)
        ? prev.experiences.filter(e => e !== experience)
        : [...prev.experiences, experience]
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
      // 기본 회원가입 + 선호도 데이터 (추후 백엔드 연동 시 사용)
      console.log('회원가입 데이터:', { ...formData, preferences })
      await register(formData.email, formData.password, formData.full_name)
      router.push('/auth/login?message=registration_success')
    } catch (err) {
      setError('회원가입에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setLoading(false)
    }
  }

  const nextStep = () => {
    if (step < 6) setStep(step + 1)
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
              <h3 className="text-lg font-medium text-gray-900 mb-4">기본 정보를 입력해주세요</h3>
            </div>
            <div className="space-y-4">
              <input
                name="full_name"
                type="text"
                required
                className="relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="이름"
                value={formData.full_name}
                onChange={handleChange}
              />
              <input
                name="email"
                type="email"
                required
                className="relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="이메일"
                value={formData.email}
                onChange={handleChange}
              />
              <input
                name="password"
                type="password"
                required
                className="relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="비밀번호"
                value={formData.password}
                onChange={handleChange}
              />
              <input
                name="confirmPassword"
                type="password"
                required
                className="relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="비밀번호 확인"
                value={formData.confirmPassword}
                onChange={handleChange}
              />
            </div>
            <button
              type="button"
              onClick={nextStep}
              className="w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              다음 단계 → 여행 취향 알아보기
            </button>
          </div>
        )

      case 2:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-medium text-gray-900 mb-2">최고의 여행 모습 👉</h3>
              <p className="text-sm text-gray-600">어떤 여행이 가장 매력적으로 느껴지시나요?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'luxury', emoji: '🏖️', label: '럭셔리 리조트 휴식', desc: '편안하고 여유로운 휴식' },
                { id: 'city', emoji: '🌆', label: '도시 문화와 쇼핑', desc: '활기찬 도시 생활 체험' },
                { id: 'nature', emoji: '⛰️', label: '대자연 속 모험', desc: '자연 속에서의 모험과 액티비티' },
                { id: 'food', emoji: '🍽️', label: '현지 맛집 탐방', desc: '다양한 현지 음식 체험' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-lg cursor-pointer transition-all ${
                    preferences.travelStyle === option.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
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
                      <p className="font-medium text-gray-900">{option.label}</p>
                      <p className="text-sm text-gray-600">{option.desc}</p>
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
              <h3 className="text-lg font-medium text-gray-900 mb-2">아끼고 싶지 않은 것 👉</h3>
              <p className="text-sm text-gray-600">여행에서 투자를 아끼지 않고 싶은 부분은?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'accommodation', emoji: '😴', label: '숙소', desc: '편안하고 좋은 숙소' },
                { id: 'food', emoji: '🍽️', label: '음식', desc: '맛있는 현지 음식과 고급 레스토랑' },
                { id: 'experience', emoji: '🎭', label: '경험', desc: '특별한 체험과 액티비티' },
                { id: 'shopping', emoji: '🛍️', label: '쇼핑', desc: '기념품과 현지 특산품' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-lg cursor-pointer transition-all ${
                    preferences.investment === option.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
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
                      <p className="font-medium text-gray-900">{option.label}</p>
                      <p className="text-sm text-gray-600">{option.desc}</p>
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
              <h3 className="text-lg font-medium text-gray-900 mb-2">선호하는 숙소 유형 👉</h3>
              <p className="text-sm text-gray-600">여행의 피로를 풀어줄 숙소, 어떤 곳을 선호하시나요?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'hotel', emoji: '🏨', label: '완벽한 서비스와 편리함', desc: '모든 것이 갖춰진 편안함 (관광호텔, 서비스드레지던스)' },
                { id: 'nature', emoji: '🏡', label: '자연 속 아늑한 휴식처', desc: '프라이빗한 우리만의 공간 (펜션, 콘도미니엄)' },
                { id: 'traditional', emoji: '🏯', label: '한국의 멋과 정취', desc: '전통 가옥에서의 특별한 하룻밤 (한옥, 템플스테이)' },
                { id: 'social', emoji: '🥂', label: '새로운 만남과 교류', desc: '여행의 즐거움을 나누는 공간 (게스트하우스, 민박)' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-lg cursor-pointer transition-all ${
                    preferences.accommodation === option.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
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
                      <p className="font-medium text-gray-900">{option.label}</p>
                      <p className="text-sm text-gray-600">{option.desc}</p>
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
              <h3 className="text-lg font-medium text-gray-900 mb-2">여행지 선택 스타일 👉</h3>
              <p className="text-sm text-gray-600">낯선 여행지에서 당신의 선택은?</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'famous', emoji: '🗺️', label: '모두가 인정하는 필수 명소', desc: '실패 없는 여행을 위한 검증된 랜드마크' },
                { id: 'hidden', emoji: '🤫', label: '현지인만 아는 숨은 명소', desc: '나만 알고 싶은 골목길과 로컬 스팟' },
                { id: 'mixed', emoji: '🧭', label: '유명한 곳과 숨은 곳의 조화', desc: '중심가를 여행하되, 가끔은 골목으로!' },
                { id: 'experience', emoji: '✨', label: '장소보다는 특별한 경험', desc: '그곳에서만 할 수 있는 독특한 활동과 체험' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-lg cursor-pointer transition-all ${
                    preferences.destination === option.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
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
                      <p className="font-medium text-gray-900">{option.label}</p>
                      <p className="text-sm text-gray-600">{option.desc}</p>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )

      case 6:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-medium text-gray-900 mb-2">경험 키워드 👉</h3>
              <p className="text-sm text-gray-600">관심 있는 여행 경험을 모두 선택해주세요 (중복 선택 가능)</p>
            </div>
            <div className="space-y-3">
              {[
                { id: 'nature', emoji: '🌳', label: '자연 속 힐링', desc: '국립공원, 산, 해변, 섬' },
                { id: 'culture', emoji: '📜', label: '역사와 문화', desc: '고궁, 성, 유명사찰, 문화유산' },
                { id: 'art', emoji: '🎨', label: '예술과 감성', desc: '미술관, 박물관, 전시, 공연' },
                { id: 'activity', emoji: '🤸', label: '액티비티', desc: '하이킹, 레포츠, 스포츠' },
                { id: 'shopping', emoji: '🛍️', label: '쇼핑과 미식', desc: '쇼핑, 음식점' },
                { id: 'accommodation', emoji: '🏨', label: '편안한 숙소', desc: '호캉스, 펜션, 한옥' },
              ].map((option) => (
                <label
                  key={option.id}
                  className={`block p-4 border-2 rounded-lg cursor-pointer transition-all ${
                    preferences.experiences.includes(option.id)
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={preferences.experiences.includes(option.id)}
                    onChange={() => handleExperienceToggle(option.id)}
                    className="hidden"
                  />
                  <div className="flex items-center space-x-3">
                    <span className="text-2xl">{option.emoji}</span>
                    <div>
                      <p className="font-medium text-gray-900">{option.label}</p>
                      <p className="text-sm text-gray-600">{option.desc}</p>
                    </div>
                  </div>
                </label>
              ))}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {step === 1 ? '회원가입' : `여행 취향 알아보기 (${step-1}/5)`}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            또는{' '}
            <Link href="/auth/login" className="font-medium text-blue-600 hover:text-blue-500">
              기존 계정으로 로그인
            </Link>
          </p>
        </div>

        {/* 진행 표시줄 */}
        {step > 1 && (
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${((step - 1) / 5) * 100}%` }}
            ></div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}
          
          {renderStep()}
          
          {step > 1 && step < 6 && (
            <div className="flex justify-between space-x-4 mt-6">
              <button
                type="button"
                onClick={prevStep}
                className="flex-1 flex justify-center py-3 px-4 border border-gray-300 text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                ← 이전
              </button>
              <button
                type="button"
                onClick={nextStep}
                className="flex-1 flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                다음 →
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
