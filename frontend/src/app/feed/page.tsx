'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { BottomNavigation } from '../../components'
import { actionTracker } from '@/lib/actionTracker'

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
  const { data: session } = useSession()
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(true)

  // 포스트 데이터를 API에서 가져오는 함수
  const fetchPosts = async () => {
    try {
      const response = await fetch('/api/proxy/api/v1/posts/')
      if (response.ok) {
        const data = await response.json()
        console.log('=== 포스트 API 응답 디버깅 ===')
        console.log('전체 응답:', data)
        console.log('첫 번째 포스트:', data.posts?.[0])
        console.log('첫 번째 포스트 사용자:', data.posts?.[0]?.user)
        console.log('OAuth 계정:', data.posts?.[0]?.user?.oauth_accounts)
        console.log('==============================')
        
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
    
    // actionTracker에 사용자 ID 설정
    if (session?.user?.email) {
      actionTracker.setUserId(session.user.email)
    }
  }, [session])

  const handleLike = async (postId: number) => {
    try {
      // 현재 좋아요 상태 확인
      const currentPost = posts.find(post => post.id === postId)
      if (!currentPost) return

      const endpoint = currentPost.isLiked 
        ? `/api/proxy/api/v1/posts/${postId}/like`  // DELETE 요청
        : `/api/proxy/api/v1/posts/${postId}/like`  // POST 요청

      const method = currentPost.isLiked ? 'DELETE' : 'POST'

      const response = await fetch(endpoint, {
        method: method,
        headers: {
          'Content-Type': 'application/json',
        }
      })

      if (response.ok) {
        const result = await response.json()
        
        // 🔥 Collection Server로 좋아요 액션 전송
        actionTracker.trackLike(
          postId.toString(),
          'social_feed',
          !currentPost.isLiked // 새로운 좋아요 상태
        )
        
        // UI 업데이트 - 서버 응답의 likes_count 사용
        setPosts(prevPosts =>
          prevPosts.map(post =>
            post.id === postId
              ? {
                ...post,
                isLiked: !post.isLiked,
                likes_count: result.likes_count
              }
              : post
          )
        )
      } else {
        console.error('좋아요 처리 실패')
      }
    } catch (error) {
      console.error('좋아요 처리 중 오류:', error)
    }
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
                  {(post.user as any).profile_image ? (
                    <img
                      src={(post.user as any).profile_image}
                      alt={(post.user as any).name || post.user.email}
                      className="w-full h-full object-cover"
                    />
                  ) : (post.user as any).oauth_accounts?.find((account: any) => account.provider === 'google')?.profile_picture ? (
                    <img
                      src={(post.user as any).oauth_accounts.find((account: any) => account.provider === 'google').profile_picture}
                      alt={(post.user as any).name || post.user.email}
                      className="w-full h-full object-cover"
                    />
                  ) : session?.user?.id === String(post.user_id) && session?.user?.image ? (
                    <img
                      src={session.user.image}
                      alt={(post.user as any).name || post.user.email}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-blue-500 text-white text-sm font-bold">
                      {((post.user as any).name || post.user.email || 'U')[0].toUpperCase()}
                    </div>
                  )}
                </div>
                <div>
                  <p className="font-semibold text-white">{(post.user as any).name || post.user.email}</p>
                  {post.location && (
                    <p className="text-xs text-gray-400">{post.location}</p>
                  )}
                </div>
              </div>
              {/* <button className="text-gray-400 hover:text-white transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                </svg>
              </button> */}
            </div>

            {/* Post Image */}
            <div className="aspect-square relative">
              <img
                src={post.image_url}
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
                    className="transition-colors hover:scale-110 transform"
                  >
                    <svg 
                      className="w-6 h-6" 
                      fill={post.isLiked ? '#ef4444' : 'none'} 
                      stroke={post.isLiked ? '#ef4444' : '#ffffff'} 
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                  </button>
                  <div className="mb-2 mt-2">
                    <p className="font-semibold text-white">좋아요 {post.likes_count}개</p>
                  </div>
                  {/* <button className="text-gray-400 hover:text-white transition-colors">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </button>
                  <button className="text-gray-400 hover:text-white transition-colors">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  </button> */}
                </div>
                <button className="text-gray-400 hover:text-white transition-colors">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                  </svg>
                </button>
              </div>

              {/* Likes Count */}
              {/* <div className="mb-2">
                <p className="font-semibold text-white">좋아요 {post.likes_count}개</p>
              </div> */}

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

      <BottomNavigation />
    </div>
  )
}