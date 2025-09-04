'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

interface User {
  id: number
  name: string
  username: string
  profileImage: string
}

interface Post {
  id: number
  user: User
  image: string
  caption: string
  likes: number
  comments: number
  timestamp: string
  location?: string
  isLiked: boolean
}

export default function FeedPage() {
  const router = useRouter()
  const [posts, setPosts] = useState<Post[]>([
    {
      id: 1,
      user: {
        id: 1,
        name: '김쿼카',
        username: 'kimquokka',
        profileImage: '/QK.jpg'
      },
      image: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=400&fit=crop',
      caption: '제주도에서의 아름다운 일출 🌅 정말 멋진 하루의 시작이었어요! #제주도여행 #일출 #힐링',
      likes: 24,
      comments: 8,
      timestamp: '2시간 전',
      location: '제주특별자치도 성산일출봉',
      isLiked: false
    },
    {
      id: 2,
      user: {
        id: 2,
        name: '여행러버',
        username: 'travellover',
        profileImage: 'https://images.unsplash.com/photo-1494790108755-2616b332c301?w=150&h=150&fit=crop&crop=face'
      },
      image: 'https://images.unsplash.com/photo-1555881400-74d7acaacd8b?w=400&h=400&fit=crop',
      caption: '부산 감천문화마을에서 찍은 사진이에요 📸 알록달록한 집들이 너무 예뻐요!',
      likes: 42,
      comments: 15,
      timestamp: '4시간 전',
      location: '부산광역시 사하구 감천문화마을',
      isLiked: true
    },
    {
      id: 3,
      user: {
        id: 3,
        name: '맛집탐험가',
        username: 'foodexplorer',
        profileImage: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop&crop=face'
      },
      image: 'https://images.unsplash.com/photo-1551218808-94e220e084d2?w=400&h=400&fit=crop',
      caption: '전주 한옥마을에서 먹은 비빔밥 🥗 역시 본고장 맛이 다르네요! 너무 맛있었어요',
      likes: 18,
      comments: 6,
      timestamp: '1일 전',
      location: '전라북도 전주시 한옥마을',
      isLiked: false
    }
  ])

  const handleLike = (postId: number) => {
    setPosts(prevPosts =>
      prevPosts.map(post =>
        post.id === postId
          ? {
              ...post,
              isLiked: !post.isLiked,
              likes: post.isLiked ? post.likes - 1 : post.likes + 1
            }
          : post
      )
    )
  }

  const handleCreatePost = () => {
    router.push('/feed/create')
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white pb-20">
      {/* Header */}
      <div className="sticky top-0 z-50 bg-gray-900/95 backdrop-blur-md border-b border-gray-800">
        <div className="flex items-center justify-between px-4 py-3">
          <h1 className="text-2xl font-bold text-blue-400">Feed</h1>
          <button
            onClick={handleCreatePost}
            className="p-2 text-blue-400 hover:text-blue-300 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Posts Feed */}
      <div className="max-w-lg mx-auto">
        {posts.map((post) => (
          <div key={post.id} className="bg-gray-800 mb-4 border-b border-gray-700">
            {/* Post Header */}
            <div className="flex items-center justify-between p-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-full overflow-hidden">
                  <img
                    src={post.user.profileImage}
                    alt={post.user.name}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div>
                  <p className="font-semibold text-white">{post.user.name}</p>
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
                src={post.image}
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
                    className={`transition-colors ${
                      post.isLiked ? 'text-red-500' : 'text-gray-400 hover:text-red-500'
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
                <p className="font-semibold text-white">좋아요 {post.likes}개</p>
              </div>

              {/* Caption */}
              <div className="mb-2">
                <p className="text-white">
                  <span className="font-semibold mr-2">{post.user.name}</span>
                  {post.caption}
                </p>
              </div>

              {/* Comments */}
              <div className="mb-2">
                <button className="text-gray-400 text-sm hover:text-gray-300 transition-colors">
                  댓글 {post.comments}개 모두 보기
                </button>
              </div>

              {/* Timestamp */}
              <div>
                <p className="text-xs text-gray-500">{post.timestamp}</p>
              </div>
            </div>

            {/* Add Comment */}
            <div className="border-t border-gray-700 p-4">
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
            </div>
          </div>
        ))}
      </div>

      {/* Loading indicator for infinite scroll (future enhancement) */}
      <div className="flex justify-center py-8">
        <p className="text-gray-400">더 많은 게시물을 불러오는 중...</p>
      </div>
    </div>
  )
}