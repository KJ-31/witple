'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { BottomNavigation } from '../../components'

interface SavedPlace {
  id: string
  name: string
  address?: string
  image?: string
  category?: string
  saved_at: string
}

export default function SavedPage() {
  const router = useRouter()
  const { data: session } = useSession()
  const [savedPlaces, setSavedPlaces] = useState<SavedPlace[]>([])
  const [loading, setLoading] = useState(true)

  const fetchSavedPlaces = async () => {
    try {
      const response = await fetch('/api/proxy/api/v1/saved-locations/', {
        headers: {
          'Content-Type': 'application/json',
        }
      })

      if (response.ok) {
        const data = await response.json()
        setSavedPlaces(data.saved_locations || [])
      } else {
        console.error('저장된 장소 가져오기 실패')
        setSavedPlaces([])
      }
    } catch (error) {
      console.error('저장된 장소 가져오기 오류:', error)
      setSavedPlaces([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSavedPlaces()
  }, [])

  const handleRemoveBookmark = async (placeId: string) => {
    try {
      const response = await fetch('/api/proxy/api/v1/saved-locations/', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ place_id: placeId })
      })

      if (response.ok) {
        setSavedPlaces(prev => prev.filter(place => place.id !== placeId))
      } else {
        console.error('북마크 제거 실패')
      }
    } catch (error) {
      console.error('북마크 제거 중 오류:', error)
    }
  }

  const handleBack = () => {
    router.back()
  }

  const formatTimeAgo = (dateString: string) => {
    const now = new Date()
    const savedDate = new Date(dateString)
    const diffInHours = Math.floor((now.getTime() - savedDate.getTime()) / (1000 * 60 * 60))

    if (diffInHours < 1) return '방금 전'
    if (diffInHours < 24) return `${diffInHours}시간 전`
    const diffInDays = Math.floor(diffInHours / 24)
    if (diffInDays < 7) return `${diffInDays}일 전`
    return savedDate.toLocaleDateString()
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-white overflow-y-auto no-scrollbar">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#1F3C7A]/30">
        <button
          onClick={handleBack}
          className="p-2 hover:bg-[#1F3C7A]/30 rounded-full transition-colors"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        
        <h1 className="text-xl font-bold text-[#3E68FF]">저장된 장소</h1>
        
        <div className="w-10"></div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex justify-center items-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF]"></div>
          <span className="ml-2 text-[#94A9C9]">저장된 장소를 불러오는 중...</span>
        </div>
      )}

      {/* Empty State */}
      {!loading && savedPlaces.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 px-6">
          <div className="w-16 h-16 bg-[#1F3C7A]/30 rounded-full flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-[#6FA0E6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-[#94A9C9] mb-2">저장된 장소가 없습니다</h2>
          <p className="text-[#6FA0E6] text-center text-sm">
            여행 일정을 만들 때 마음에 드는 장소를<br />
            북마크해서 저장해보세요!
          </p>
        </div>
      )}

      {/* Saved Places List */}
      <div className="px-4 py-4 space-y-4 pb-20">
        {savedPlaces.map((place) => (
          <div key={place.id} className="bg-[#12345D]/50 rounded-2xl p-4 border border-[#1F3C7A]/30">
            <div className="flex justify-between items-start mb-3">
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-white mb-1">{place.name}</h3>
                {place.address && (
                  <p className="text-[#6FA0E6] text-sm mb-2">{place.address}</p>
                )}
                {place.category && (
                  <span className="inline-block bg-[#3E68FF]/20 text-[#3E68FF] px-2 py-1 rounded-lg text-xs">
                    {place.category}
                  </span>
                )}
              </div>
              
              <button
                onClick={() => handleRemoveBookmark(place.id)}
                className="p-2 hover:bg-[#1F3C7A]/30 rounded-full transition-colors"
              >
                <svg className="w-5 h-5 text-[#ef4444]" fill="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                </svg>
              </button>
            </div>

            {place.image && (
              <div className="w-full h-32 rounded-lg overflow-hidden mb-3">
                <img
                  src={place.image}
                  alt={place.name}
                  className="w-full h-full object-cover"
                />
              </div>
            )}

            <div className="flex items-center justify-end">
              <span className="text-[#6FA0E6] text-xs">
                {formatTimeAgo(place.saved_at)}에 저장됨
              </span>
            </div>
          </div>
        ))}
      </div>

      <BottomNavigation />
    </div>
  )
}