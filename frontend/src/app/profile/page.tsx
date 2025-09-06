'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useSession, signOut } from 'next-auth/react'

interface TripCard {
  id: number
  title: string
  dates: string
  status: 'active' | 'completed' | 'planned'
  image?: string
}

interface Post {
  id: number
  user_id: string
  caption: string
  image_url: string
  location?: string
  likes_count: number
  comments_count: number
  created_at: string
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
  const [posts, setPosts] = useState<Post[]>([])
  const [postsLoading, setPostsLoading] = useState(false)
  const router = useRouter()
  const { data: session, status } = useSession()

  // 사용자 게시글 가져오기
  const fetchUserPosts = useCallback(async () => {
    if (!session) return
    
    setPostsLoading(true)
    try {
      const response = await fetch('/api/proxy/api/v1/posts/', {
        headers: {
          'Content-Type': 'application/json',
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        console.log('=== 사용자 게시글 필터링 디버그 ===')
        console.log('현재 세션 사용자 ID:', session.user?.id)
        console.log('현재 세션 사용자 이메일:', session.user?.email)
        console.log('전체 게시글 수:', data.posts?.length || 0)
        console.log('게시글 user_id 샘플:', data.posts?.[0]?.user_id)
        
        // 현재 사용자의 게시글만 필터링
        const userPosts = data.posts.filter((post: Post) => post.user_id === session.user?.id)
        console.log('필터링된 게시글 수:', userPosts.length)
        console.log('==============================')
        setPosts(userPosts)
      } else {
        console.error('게시글 가져오기 실패')
        setPosts([])
      }
    } catch (error) {
      console.error('게시글 가져오기 오류:', error)
      setPosts([])
    } finally {
      setPostsLoading(false)
    }
  }, [session])

  // 로그인하지 않은 사용자는 로그인 페이지로 리다이렉트
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/auth/login')
    }
  }, [status, router])

  // 세션이 있을 때 게시글 가져오기
  useEffect(() => {
    if (session) {
      fetchUserPosts()
    }
  }, [session, fetchUserPosts])

  // 로딩 중이면 로딩 화면 표시
  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-400">프로필을 불러오는 중...</p>
        </div>
      </div>
    )
  }

  // 로그인하지 않은 경우 아무것도 렌더링하지 않음 (리다이렉트 처리됨)
  if (!session) {
    return null
  }

  // 로그아웃 핸들러
  const handleLogout = async () => {
    try {
      await signOut({ 
        callbackUrl: '/', // 로그아웃 후 메인 페이지로 이동
        redirect: true 
      })
    } catch (error) {
      console.error('로그아웃 오류:', error)
    }
  }

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
        if (postsLoading) {
          return (
            <div className="flex justify-center items-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
              <span className="ml-2 text-gray-400">게시글을 불러오는 중...</span>
            </div>
          )
        }

        if (posts.length === 0) {
          return (
            <div className="text-center py-8">
              <p className="text-gray-400">작성한 게시글이 없습니다.</p>
              <Link href="/feed/create">
                <button className="mt-4 px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors">
                  첫 게시글 작성하기
                </button>
              </Link>
            </div>
          )
        }

        return (
          <div className="space-y-4">
            {posts.map((post) => (
              <div key={post.id} className="bg-gray-800 p-4 rounded-2xl">
                {/* 이미지가 있으면 표시 */}
                {post.image_url && (
                  <div className="mb-3 rounded-lg overflow-hidden">
                    <img 
                      src={post.image_url} 
                      alt="Post image"
                      className="w-full h-48 object-cover"
                    />
                  </div>
                )}
                
                <p className="text-white text-base mb-3">{post.caption}</p>
                
                {/* 위치 정보가 있으면 표시 */}
                {post.location && (
                  <div className="flex items-center mb-2 text-sm text-gray-400">
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span>{post.location}</span>
                  </div>
                )}
                
                <div className="flex items-center justify-between text-sm text-gray-400">
                  <span>{new Date(post.created_at).toLocaleDateString('ko-KR')}</span>
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-1">
                      <span>❤️</span>
                      <span>{post.likes_count}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <span>💬</span>
                      <span>{post.comments_count}</span>
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
          {session.user?.image ? (
            <img
              src={session.user.image}
              alt="Profile"
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-blue-500 text-white text-2xl font-bold">
              {(session.user?.name || session.user?.email || 'U')[0].toUpperCase()}
            </div>
          )}
        </div>

        <h1 className="text-2xl font-bold text-blue-400 mb-2">
          {session.user?.name || session.user?.email || '사용자'}
        </h1>

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

      {/* Logout Button at Bottom */}
      <div className="px-4 pb-8">
        <button 
          onClick={handleLogout}
          className="w-full bg-red-500 text-white py-4 rounded-2xl font-medium hover:bg-red-600 transition-colors"
        >
          로그아웃
        </button>
      </div>
    </div>
  )
}