'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

interface TripCard {
  id: number
  title: string
  dates: string
  status: 'active' | 'completed' | 'planned'
  image?: string
}

interface Post {
  id: number
  title: string
  content: string
  date: string
  likes: number
  comments: number
}

interface SavedItem {
  id: number
  type: 'restaurant' | 'accommodation' | 'attraction'
  title: string
  location: string
  rating: number
  image?: string
}

export default function ProfilePage() {
  const [activeTab, setActiveTab] = useState<'trips' | 'posts' | 'saved'>('trips')
  const router = useRouter()

  // 목업 데이터
  const trips: TripCard[] = [
    {
      id: 1,
      title: '서울 시장 여행',
      dates: '2025.08.14(수) - 08.16(금)',
      status: 'active'
    },
    {
      id: 2,
      title: '전주 시장 여행',
      dates: '2025.03.03(월) - 03.04(화)',
      status: 'completed'
    },
    {
      id: 3,
      title: '부산 시장 여행',
      dates: '2024.07.02(화) - 07.04(목)',
      status: 'completed'
    },
    {
      id: 4,
      title: '강릉 시장 여행',
      dates: '2023.07.01(목) - 07.03(토)',
      status: 'completed'
    },
    {
      id: 5,
      title: '제주 시장 여행',
      dates: '2025.08.14(수) - 08.16(금)',
      status: 'planned'
    }
  ]

  const posts: Post[] = [
    {
      id: 1,
      title: '서울 명동 맛집 추천!',
      content: '명동에서 꼭 가봐야 할 맛집들을 소개합니다...',
      date: '2025.08.15',
      likes: 24,
      comments: 8
    },
    {
      id: 2,
      title: '부산 해운대 여행 후기',
      content: '해운대에서의 즐거운 여행 경험을 공유합니다...',
      date: '2024.07.05',
      likes: 18,
      comments: 12
    },
    {
      id: 3,
      title: '전주 한옥마을 가이드',
      content: '전주 한옥마을 완벽 가이드를 준비했습니다...',
      date: '2025.03.05',
      likes: 31,
      comments: 5
    }
  ]

  const savedItems: SavedItem[] = [
    {
      id: 1,
      type: 'restaurant',
      title: '보영식당',
      location: '경기도 의정부시',
      rating: 4.5
    },
    {
      id: 2,
      type: 'accommodation',
      title: '제주 오션뷰 펜션',
      location: '제주특별자치도 제주시',
      rating: 4.8
    },
    {
      id: 3,
      type: 'attraction',
      title: '경복궁',
      location: '서울특별시 종로구',
      rating: 4.7
    },
    {
      id: 4,
      type: 'restaurant',
      title: '싸리골',
      location: '강원특별자치도 정선군',
      rating: 4.2
    }
  ]

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-blue-500'
      case 'completed': return 'bg-gray-400'
      case 'planned': return 'bg-green-500'
      default: return 'bg-gray-400'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'active': return '여행 중'
      case 'completed': return '완료됨'
      case 'planned': return '예정됨'
      default: return ''
    }
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'trips':
        return (
          <div className="space-y-4">
            {trips.map((trip) => (
              <div
                key={trip.id}
                className={`relative p-4 rounded-2xl ${trip.status === 'active' ? 'bg-blue-500' : 'bg-gray-600'
                  } text-white`}
              >
                {trip.status === 'active' && (
                  <div className="absolute top-4 right-4">
                    <span className="bg-red-500 text-white px-2 py-1 rounded-full text-xs">
                      🚩
                    </span>
                  </div>
                )}
                <h3 className="text-lg font-semibold mb-2">{trip.title}</h3>
                <p className="text-sm opacity-90">{trip.dates}</p>
                <div className="mt-3 flex items-center space-x-2">
                  <span className={`w-2 h-2 rounded-full ${getStatusColor(trip.status)}`}></span>
                  <span className="text-xs">{getStatusText(trip.status)}</span>
                </div>
              </div>
            ))}
          </div>
        )

      case 'posts':
        return (
          <div className="space-y-4">
            {posts.map((post) => (
              <div key={post.id} className="bg-gray-800 p-4 rounded-2xl">
                <h3 className="text-white text-lg font-semibold mb-2">{post.title}</h3>
                <p className="text-gray-300 text-sm mb-3 line-clamp-2">{post.content}</p>
                <div className="flex items-center justify-between text-sm text-gray-400">
                  <span>{post.date}</span>
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-1">
                      <span>❤️</span>
                      <span>{post.likes}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <span>💬</span>
                      <span>{post.comments}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )

      case 'saved':
        return (
          <div className="space-y-4">
            {savedItems.map((item) => (
              <div key={item.id} className="bg-gray-800 p-4 rounded-2xl">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-xl">
                        {item.type === 'restaurant' ? '🍽️' :
                          item.type === 'accommodation' ? '🏨' : '🎯'}
                      </span>
                      <h3 className="text-white font-semibold">{item.title}</h3>
                    </div>
                    <p className="text-gray-300 text-sm mb-2">{item.location}</p>
                    <div className="flex items-center space-x-1">
                      <span className="text-yellow-400">⭐</span>
                      <span className="text-gray-300 text-sm">{item.rating}</span>
                    </div>
                  </div>
                  <button className="text-red-400 hover:text-red-300 transition-colors">
                    <span className="text-xl">❤️</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="relative p-4">
        <button
          onClick={() => router.back()}
          className="absolute left-4 top-4 text-blue-400 text-2xl"
        >
          ‹
        </button>
      </div>

      {/* Profile Section */}
      <div className="flex flex-col items-center px-4 pb-8">
        <div className="w-24 h-24 rounded-full bg-gray-300 mb-4 overflow-hidden">
          <img
            src="/QK.jpg"
            alt="Profile"
            className="w-full h-full object-cover"
          />
        </div>

        <h1 className="text-2xl font-bold text-blue-400 mb-2">김쿼카</h1>

        <div className="flex items-center space-x-1 mb-6">
          <span className="text-green-400">🍃</span>
          <span className="text-green-400 font-semibold">555</span>
        </div>

        <Link href="/profile/edit">
          <button className="w-64 bg-gray-200 text-gray-800 py-3 rounded-2xl font-medium hover:bg-gray-100 transition-colors">
            Edit Profile
          </button>
        </Link>
      </div>

      {/* Tab Navigation */}
      <div className="px-4 mb-6">
        <div className="flex space-x-4">
          {(['trips', 'posts', 'saved'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-3 px-6 rounded-2xl font-medium transition-colors ${activeTab === tab
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-800 text-gray-300 border border-gray-700'
                }`}
            >
              {tab === 'trips' ? 'Trips' :
                tab === 'posts' ? 'Posts' :
                  'Saved'}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="px-4 pb-8">
        {renderTabContent()}
      </div>
    </div>
  )
}