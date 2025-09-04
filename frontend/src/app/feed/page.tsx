'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

interface User {
  id: number
  full_name: string
  username: string
  email: string
}

interface Post {
  id: number
  user_id: number
  user: User
  image_url: string
  caption: string
  likes_count: number
  comments_count: number
  created_at: string
  location?: string
  isLiked: boolean
}

export default function FeedPage() {
  const router = useRouter()
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(true)

  // 포스트 데이터를 API에서 가져오는 함수
  const fetchPosts = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/posts/')
      if (response.ok) {
        const data = await response.json()
        // API 응답 형태에 맞게 데이터 변환
        const postsWithLiked = data.posts.map((post: any) => ({
          ...post,
          isLiked: false // 초기값은 좋아요 안함
        }))
        setPosts(postsWithLiked)
      } else {
        console.error('포스트 가져오기 실패')
        // 실패시 빈 배열 유지
        setPosts([])
      }
    } catch (error) {
      console.error('포스트 가져오기 오류:', error)
      setPosts([])
    } finally {
      setLoading(false)
    }
  }

  // 컴포넌트 마운트시 포스트 가져오기
  useEffect(() => {
    fetchPosts()
  }, [])

  const handleLike = (postId: number) => {
    setPosts(prevPosts =>
      prevPosts.map(post =>
        post.id === postId
          ? {
            ...post,
            isLiked: !post.isLiked,
            likes_count: post.isLiked ? post.likes_count - 1 : post.likes_count + 1
          }
          : post
      )
    )
  }

  const handleCreatePost = () => {
    router.push('/feed/create')
  }

  const formatTimeAgo = (dateString: string) => {
    const now = new Date()
    const postDate = new Date(dateString)
    const diffInHours = Math.floor((now.getTime() - postDate.getTime()) / (1000 * 60 * 60))
    
    if (diffInHours < 1) return '방금 전'
    if (diffInHours < 24) return `${diffInHours}시간 전`
    const diffInDays = Math.floor(diffInHours / 24)
    if (diffInDays < 7) return `${diffInDays}일 전`
    return postDate.toLocaleDateString()
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white pb-20">
      {/* Floating Create Post Button */}
      <button
        onClick={handleCreatePost}
        className="fixed bottom-24 right-6 z-50 w-12 h-12 bg-blue-500 hover:bg-blue-600 rounded-full flex items-center justify-center shadow-lg transition-colors"
      >
        <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
      </button>

      {/* Loading State */}
      {loading && (
        <div className="flex justify-center items-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          <span className="ml-2 text-gray-300">포스트를 불러오는 중...</span>
        </div>
      )}

      {/* Posts Feed */}
      <div className="max-w-lg mx-auto">
        {!loading && posts.length === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-400 text-lg">아직 포스트가 없습니다.</p>
            <p className="text-gray-500 text-sm mt-2">첫 번째 포스트를 작성해보세요!</p>
          </div>
        )}
        
        {posts.map((post) => (
          <div key={post.id} className="bg-gray-800 mb-4 border-b border-gray-700">
            {/* Post Header */}
            <div className="flex items-center justify-between p-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-full overflow-hidden">
                  <img
                    src="/QK.jpg"
                    alt={post.user.full_name || post.user.username}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div>
                  <p className="font-semibold text-white">{post.user.full_name || post.user.username}</p>
                  {post.location && (
                    <p className="text-xs text-gray-400">{post.location}</p>
                  )}
                </div>
              </div>
              <button className="text-gray-400 hover:text-white transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                </svg>
              </button>
            </div>

            {/* Post Image */}
            <div className="aspect-square relative">
              <img
                src={`http://localhost:8000${post.image_url}`}
                alt="Post"
                className="w-full h-full object-cover"
              />
            </div>

            {/* Post Actions */}
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => handleLike(post.id)}
                    className={`transition-colors ${post.isLiked ? 'text-red-500' : 'text-gray-400 hover:text-red-500'
                      }`}
                  >
                    <svg className="w-6 h-6" fill={post.isLiked ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                  </button>
                  <button className="text-gray-400 hover:text-white transition-colors">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </button>
                  <button className="text-gray-400 hover:text-white transition-colors">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  </button>
                </div>
                <button className="text-gray-400 hover:text-white transition-colors">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                  </svg>
                </button>
              </div>

              {/* Likes Count */}
              <div className="mb-2">
                <p className="font-semibold text-white">좋아요 {post.likes_count}개</p>
              </div>

              {/* Caption */}
              <div className="mb-2">
                <p className="text-white">
                  <span className="font-semibold mr-2">{post.user.full_name || post.user.username}</span>
                  {post.caption}
                </p>
              </div>

              {/* Comments */}
              {/* <div className="mb-2">
                <button className="text-gray-400 text-sm hover:text-gray-300 transition-colors">
                  댓글 {post.comments_count}개 모두 보기
                </button>
              </div> */}

              {/* Timestamp */}
              <div>
                <p className="text-xs text-gray-500">{formatTimeAgo(post.created_at)}</p>
              </div>
            </div>

            {/* Add Comment */}
            {/* <div className="border-t border-gray-700 p-4">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-full overflow-hidden">
                  <img
                    src="/QK.jpg"
                    alt="Your profile"
                    className="w-full h-full object-cover"
                  />
                </div>
                <input
                  type="text"
                  placeholder="댓글 달기..."
                  className="flex-1 bg-transparent text-white placeholder-gray-400 outline-none"
                />
                <button className="text-blue-400 font-semibold hover:text-blue-300 transition-colors">
                  게시
                </button>
              </div>
            </div> */}
          </div>
        ))}
      </div>

      {/* Loading indicator for infinite scroll (future enhancement) */}
      <div className="flex justify-center py-8">
        <p className="text-gray-400">더 많은 게시물을 불러오는 중...</p>
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
            href="/quest"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="퀘스트"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </Link>

          <Link
            href="/treasure"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="보물찾기"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </Link>

          <Link
            href="/feed"
            className="flex flex-col items-center py-1 px-2 text-[#3E68FF]"
            aria-label="피드"
          >
            <svg className="w-6 h-6 mb-1" fill="currentColor" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
            </svg>
          </Link>

          <button
            onClick={() => {
              // 임시로 로그인 상태를 확인 (실제 구현에서는 인증 상태를 확인)
              const isLoggedIn = false // 여기서 실제 로그인 상태 확인
              if (isLoggedIn) {
                router.push('/profile')
              } else {
                router.push('/auth/register')
              }
            }}
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="마이페이지"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </button>
        </div>
      </nav>
    </div>
  )
}