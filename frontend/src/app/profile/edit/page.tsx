'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

interface TravelPreferences {
  travelStyle: string
  investment: string
  accommodation: string
  destination: string
  experiences: string[]
}

export default function EditProfilePage() {
  const router = useRouter()
  const [activeSection, setActiveSection] = useState<'basic' | 'preferences'>('basic')
  
  const [profileData, setProfileData] = useState({
    name: '김쿼카',
    email: 'kimquokka@example.com',
    bio: '여행을 사랑하는 쿼카입니다 🌿',
    phone: '010-1234-5678',
    birthDate: '1995-03-15',
    location: '서울특별시'
  })

  const [preferences, setPreferences] = useState<TravelPreferences>({
    travelStyle: 'nature',
    investment: 'experience',
    accommodation: 'hotel',
    destination: 'mixed',
    experiences: ['nature', 'culture', 'art']
  })

  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const handleProfileChange = (field: string, value: string) => {
    setProfileData(prev => ({
      ...prev,
      [field]: value
    }))
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

  const handleSave = async () => {
    setLoading(true)
    try {
      // 여기서 API 호출 (추후 백엔드 연동)
      console.log('저장할 프로필 데이터:', profileData)
      console.log('저장할 선호도 데이터:', preferences)
      
      // 목업 저장 지연
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      setMessage('프로필이 성공적으로 업데이트되었습니다!')
      setTimeout(() => {
        router.push('/profile')
      }, 1500)
    } catch (error) {
      setMessage('저장 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const renderBasicInfo = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-24 h-24 rounded-full bg-gray-300 mx-auto mb-4 overflow-hidden">
          <img
            src="/QK.jpg"
            alt="Profile"
            className="w-full h-full object-cover"
          />
        </div>
        <button className="text-blue-400 text-sm hover:text-blue-300 transition-colors">
          사진 변경
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">이름</label>
          <input
            type="text"
            value={profileData.name}
            onChange={(e) => handleProfileChange('name', e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-2xl text-white focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">이메일</label>
          <input
            type="email"
            value={profileData.email}
            onChange={(e) => handleProfileChange('email', e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-2xl text-white focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">소개</label>
          <textarea
            value={profileData.bio}
            onChange={(e) => handleProfileChange('bio', e.target.value)}
            rows={3}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-2xl text-white focus:outline-none focus:border-blue-500 resize-none"
            placeholder="자신을 소개해주세요..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">전화번호</label>
          <input
            type="tel"
            value={profileData.phone}
            onChange={(e) => handleProfileChange('phone', e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-2xl text-white focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">생년월일</label>
          <input
            type="date"
            value={profileData.birthDate}
            onChange={(e) => handleProfileChange('birthDate', e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-2xl text-white focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">거주지역</label>
          <select
            value={profileData.location}
            onChange={(e) => handleProfileChange('location', e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-2xl text-white focus:outline-none focus:border-blue-500"
          >
            <option value="서울특별시">서울특별시</option>
            <option value="부산광역시">부산광역시</option>
            <option value="대구광역시">대구광역시</option>
            <option value="인천광역시">인천광역시</option>
            <option value="광주광역시">광주광역시</option>
            <option value="대전광역시">대전광역시</option>
            <option value="울산광역시">울산광역시</option>
            <option value="경기도">경기도</option>
            <option value="강원특별자치도">강원특별자치도</option>
            <option value="충청북도">충청북도</option>
            <option value="충청남도">충청남도</option>
            <option value="전라북도">전라북도</option>
            <option value="전라남도">전라남도</option>
            <option value="경상북도">경상북도</option>
            <option value="경상남도">경상남도</option>
            <option value="제주특별자치도">제주특별자치도</option>
          </select>
        </div>
      </div>
    </div>
  )

  const renderPreferences = () => (
    <div className="space-y-8">
      {/* 여행 스타일 */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">🏖️ 최고의 여행 모습</h3>
        <div className="space-y-3">
          {[
            { id: 'luxury', label: '럭셔리 리조트 휴식', desc: '편안하고 여유로운 휴식' },
            { id: 'city', label: '도시 문화와 쇼핑', desc: '활기찬 도시 생활 체험' },
            { id: 'nature', label: '대자연 속 모험', desc: '자연 속에서의 모험과 액티비티' },
            { id: 'food', label: '현지 맛집 탐방', desc: '다양한 현지 음식 체험' },
          ].map((option) => (
            <label
              key={option.id}
              className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${
                preferences.travelStyle === option.id
                  ? 'border-blue-500 bg-blue-500 bg-opacity-10'
                  : 'border-gray-700 bg-gray-800 hover:border-gray-600'
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
              <div>
                <p className="font-medium text-white">{option.label}</p>
                <p className="text-sm text-gray-400">{option.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* 투자 부분 */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">💰 아끼고 싶지 않은 것</h3>
        <div className="space-y-3">
          {[
            { id: 'accommodation', label: '숙소', desc: '편안하고 좋은 숙소' },
            { id: 'food', label: '음식', desc: '맛있는 현지 음식과 고급 레스토랑' },
            { id: 'experience', label: '경험', desc: '특별한 체험과 액티비티' },
            { id: 'shopping', label: '쇼핑', desc: '기념품과 현지 특산품' },
          ].map((option) => (
            <label
              key={option.id}
              className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${
                preferences.investment === option.id
                  ? 'border-blue-500 bg-blue-500 bg-opacity-10'
                  : 'border-gray-700 bg-gray-800 hover:border-gray-600'
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
              <div>
                <p className="font-medium text-white">{option.label}</p>
                <p className="text-sm text-gray-400">{option.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* 경험 키워드 */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">✨ 경험 키워드 (중복 선택 가능)</h3>
        <div className="space-y-3">
          {[
            { id: 'nature', label: '자연 속 힐링', desc: '국립공원, 산, 해변, 섬' },
            { id: 'culture', label: '역사와 문화', desc: '고궁, 성, 유명사찰, 문화유산' },
            { id: 'art', label: '예술과 감성', desc: '미술관, 박물관, 전시, 공연' },
            { id: 'activity', label: '액티비티', desc: '하이킹, 레포츠, 스포츠' },
            { id: 'shopping', label: '쇼핑과 미식', desc: '쇼핑, 음식점' },
            { id: 'accommodation', label: '편안한 숙소', desc: '호캉스, 펜션, 한옥' },
          ].map((option) => (
            <label
              key={option.id}
              className={`block p-4 border-2 rounded-2xl cursor-pointer transition-all ${
                preferences.experiences.includes(option.id)
                  ? 'border-blue-500 bg-blue-500 bg-opacity-10'
                  : 'border-gray-700 bg-gray-800 hover:border-gray-600'
              }`}
            >
              <input
                type="checkbox"
                checked={preferences.experiences.includes(option.id)}
                onChange={() => handleExperienceToggle(option.id)}
                className="hidden"
              />
              <div>
                <p className="font-medium text-white">{option.label}</p>
                <p className="text-sm text-gray-400">{option.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <button 
          onClick={() => router.back()}
          className="text-blue-400 text-2xl"
        >
          ‹
        </button>
        <h1 className="text-xl font-semibold">프로필 편집</h1>
        <button 
          onClick={handleSave}
          disabled={loading}
          className="text-blue-400 font-medium hover:text-blue-300 transition-colors disabled:opacity-50"
        >
          {loading ? '저장중...' : '저장'}
        </button>
      </div>

      {/* Success Message */}
      {message && (
        <div className={`p-4 mx-4 mt-4 rounded-2xl ${
          message.includes('성공') 
            ? 'bg-green-500 bg-opacity-20 border border-green-500 text-green-400'
            : 'bg-red-500 bg-opacity-20 border border-red-500 text-red-400'
        }`}>
          {message}
        </div>
      )}

      {/* Tab Navigation */}
      <div className="px-4 py-6">
        <div className="flex space-x-4 mb-6">
          <button
            onClick={() => setActiveSection('basic')}
            className={`flex-1 py-3 px-6 rounded-2xl font-medium transition-colors ${
              activeSection === 'basic'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-800 text-gray-300 border border-gray-700'
            }`}
          >
            기본 정보
          </button>
          <button
            onClick={() => setActiveSection('preferences')}
            className={`flex-1 py-3 px-6 rounded-2xl font-medium transition-colors ${
              activeSection === 'preferences'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-800 text-gray-300 border border-gray-700'
            }`}
          >
            여행 취향
          </button>
        </div>

        {/* Content */}
        <div>
          {activeSection === 'basic' ? renderBasicInfo() : renderPreferences()}
        </div>
      </div>
    </div>
  )
}