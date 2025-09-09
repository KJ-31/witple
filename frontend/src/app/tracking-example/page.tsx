'use client'

import React, { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useActionTracker } from '@/lib/actionTracker'

// 실제 적용 예시 페이지
export default function TrackingExamplePage() {
  const { data: session } = useSession()
  const tracker = useActionTracker()
  
  const [stats, setStats] = useState<any>({})

  useEffect(() => {
    // 사용자가 로그인하면 트래커에 사용자 ID 설정
    if (session?.user?.id) {
      tracker.setUserId(session.user.id)
    }
  }, [session, tracker])

  // 통계 업데이트
  useEffect(() => {
    const interval = setInterval(() => {
      setStats(tracker.getStats())
    }, 1000)
    
    return () => clearInterval(interval)
  }, [tracker])

  // 예시 장소 데이터
  const examplePlaces = [
    { id: '1', name: '제주 한라산', category: 'nature', position: 1 },
    { id: '2', name: '부산 해운대', category: 'nature', position: 2 },
    { id: '3', name: '서울 경복궁', category: 'humanities', position: 3 },
    { id: '4', name: '강릉 커피거리', category: 'restaurants', position: 4 },
    { id: '5', name: '여수 밤바다', category: 'leisure_sports', position: 5 }
  ]

  const handlePlaceClick = (place: any) => {
    tracker.trackCardClick(place.id, place.category, place.position)
    alert(`${place.name} 클릭 트래킹됨!`)
  }

  const handleBookmark = (place: any) => {
    tracker.trackBookmark(place.id, place.category, true)
    alert(`${place.name} 북마크 트래킹됨!`)
  }

  const handleLike = (place: any) => {
    tracker.trackLike(place.id, place.category, true)
    alert(`${place.name} 좋아요 트래킹됨!`)
  }

  const handleSearch = () => {
    const query = (document.getElementById('searchInput') as HTMLInputElement)?.value || ''
    if (query) {
      tracker.trackSearch(query, 'general', 5)
      alert(`검색 "${query}" 트래킹됨!`)
    }
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Action Tracking 테스트</h1>
      
      {/* 사용자 정보 */}
      <div className="bg-blue-50 p-4 rounded-lg mb-6">
        <h2 className="text-xl font-semibold mb-2">현재 상태</h2>
        <p>사용자 ID: {session?.user?.id || '로그인 필요'}</p>
        <p>세션 ID: {stats.sessionId}</p>
        <p>대기 중인 액션: {stats.pendingActions}개</p>
      </div>

      {/* 검색 테스트 */}
      <div className="bg-gray-50 p-4 rounded-lg mb-6">
        <h2 className="text-xl font-semibold mb-4">검색 트래킹 테스트</h2>
        <div className="flex gap-2">
          <input
            id="searchInput"
            type="text"
            placeholder="검색어 입력..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded"
          />
          <button
            onClick={handleSearch}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            검색 트래킹
          </button>
        </div>
      </div>

      {/* 장소 카드들 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {examplePlaces.map((place) => (
          <div key={place.id} className="bg-white border rounded-lg p-4 shadow-sm">
            <h3 className="text-lg font-semibold mb-2">{place.name}</h3>
            <p className="text-sm text-gray-600 mb-4">카테고리: {place.category}</p>
            
            <div className="flex gap-2">
              <button
                onClick={() => handlePlaceClick(place)}
                className="flex-1 px-3 py-2 bg-green-500 text-white rounded text-sm hover:bg-green-600"
              >
                클릭 트래킹
              </button>
              <button
                onClick={() => handleBookmark(place)}
                className="px-3 py-2 bg-yellow-500 text-white rounded text-sm hover:bg-yellow-600"
              >
                📖
              </button>
              <button
                onClick={() => handleLike(place)}
                className="px-3 py-2 bg-red-500 text-white rounded text-sm hover:bg-red-600"
              >
                ❤️
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* 스크롤 트래킹 영역 */}
      <div className="mt-8 bg-gradient-to-b from-purple-100 to-purple-300 p-8 rounded-lg">
        <h2 className="text-xl font-semibold mb-4">스크롤 트래킹 테스트 영역</h2>
        <div className="h-96 overflow-y-auto bg-white p-4 rounded">
          <ScrollTrackingContent />
        </div>
      </div>

      {/* 개발자 정보 */}
      <div className="mt-8 bg-gray-800 text-white p-4 rounded-lg">
        <h2 className="text-xl font-semibold mb-2">개발자 정보</h2>
        <pre className="text-sm overflow-auto">
          {JSON.stringify(stats, null, 2)}
        </pre>
      </div>
    </div>
  )
}

// 스크롤 트래킹용 컨텐츠
function ScrollTrackingContent() {
  const tracker = useActionTracker()
  const [scrollPercentage, setScrollPercentage] = useState(0)

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const element = e.currentTarget
    const scrollTop = element.scrollTop
    const scrollHeight = element.scrollHeight - element.clientHeight
    const percentage = Math.floor((scrollTop / scrollHeight) * 100)
    
    setScrollPercentage(percentage)
    
    // 스크롤 트래킹
    tracker.trackScrollDepth('scroll-test-area', 'general', percentage)
  }

  return (
    <div className="space-y-4" onScroll={handleScroll}>
      <div className="sticky top-0 bg-white border-b pb-2 mb-4">
        <p className="text-sm font-semibold">현재 스크롤: {scrollPercentage}%</p>
        <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
          <div 
            className="bg-purple-500 h-2 rounded-full transition-all duration-300"
            style={{ width: `${scrollPercentage}%` }}
          />
        </div>
      </div>
      
      {Array.from({ length: 50 }, (_, i) => (
        <div key={i} className="p-4 bg-gray-50 rounded">
          <h3 className="font-semibold">컨텐츠 블록 {i + 1}</h3>
          <p className="text-sm text-gray-600 mt-2">
            이 영역을 스크롤하면 25%, 50%, 75%, 100% 지점에서 자동으로 트래킹됩니다.
            스크롤 깊이: {scrollPercentage}%
          </p>
        </div>
      ))}
    </div>
  )
}