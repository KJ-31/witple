'use client'

import { useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'

export default function CreatePostPage() {
  const router = useRouter()
  const { data: session } = useSession()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [caption, setCaption] = useState('')
  const [location, setLocation] = useState('')
  const [isUploading, setIsUploading] = useState(false)

  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        setSelectedImage(e.target?.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleImageUpload = () => {
    fileInputRef.current?.click()
  }

  const handleSubmit = async () => {
    if (!selectedImage || !caption.trim()) {
      alert('사진과 캡션을 모두 입력해주세요.')
      return
    }

    console.log('=== 세션 상태 디버깅 ===')
    console.log('전체 세션 객체:', session)
    console.log('세션 사용자:', session?.user)
    console.log('사용자 ID:', session?.user?.id)
    console.log('사용자 이메일:', session?.user?.email)
    console.log('백엔드 토큰:', (session as any)?.backendToken)
    console.log('========================')

    if (!session?.user?.id) {
      alert('로그인이 필요합니다.')
      router.push('/auth/login')
      return
    }

    setIsUploading(true)

    try {
      console.log('=== 게시글 생성 디버깅 ===')
      console.log('현재 세션 사용자 ID:', session.user.id)
      console.log('현재 세션 사용자 이메일:', session.user.email)
      console.log('백엔드 토큰:', (session as any)?.backendToken)

      const headers: any = {
        'Content-Type': 'application/json',
      }

      // 백엔드 토큰이 있으면 Authorization 헤더 추가
      if ((session as any)?.backendToken) {
        headers['Authorization'] = `Bearer ${(session as any).backendToken}`
      }

      // API 호출로 포스트 생성 (끝에 슬래시 추가하여 리다이렉트 방지)
      const response = await fetch('/api/proxy/api/v1/posts/', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          caption: caption,
          location: location || null,
          image_data: selectedImage // Base64 이미지 데이터
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '업로드 실패')
      }

      const result = await response.json()
      console.log('포스트 생성 성공:', result)

      alert('포스트가 성공적으로 업로드되었습니다!')
      router.push('/feed')
    } catch (error: any) {
      console.error('=== UPLOAD ERROR ===');
      console.error('Error type:', typeof error);
      console.error('Error name:', error.name);
      console.error('Error message:', error.message);
      console.error('Error stack:', error.stack);
      console.error('Full error object:', error);
      
      alert(`업로드 중 오류가 발생했습니다: ${error instanceof Error ? error.message : '알 수 없는 오류'}`)
      console.error('Upload error:', error)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="sticky top-0 z-50 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center justify-between px-4 py-3">
          <button
            onClick={() => router.back()}
            className="text-blue-400 text-2xl"
          >
            ‹
          </button>
          <h1 className="text-xl font-semibold">새 게시물</h1>
          <button
            onClick={handleSubmit}
            disabled={!selectedImage || !caption.trim() || isUploading}
            className="text-blue-400 font-semibold hover:text-blue-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? '업로드 중...' : '공유'}
          </button>
        </div>
      </div>

      <div className="max-w-lg mx-auto p-4">
        {/* Image Upload Section */}
        <div className="mb-6">
          {selectedImage ? (
            <div className="relative">
              <div className="aspect-square rounded-2xl overflow-hidden bg-gray-800">
                <img
                  src={selectedImage}
                  alt="Selected"
                  className="w-full h-full object-cover"
                />
              </div>
              <button
                onClick={() => setSelectedImage(null)}
                className="absolute top-3 right-3 w-8 h-8 bg-black bg-opacity-50 rounded-full flex items-center justify-center text-white hover:bg-opacity-70 transition-colors"
              >
                ×
              </button>
            </div>
          ) : (
            <div
              onClick={handleImageUpload}
              className="aspect-square rounded-2xl border-2 border-dashed border-gray-600 flex flex-col items-center justify-center cursor-pointer hover:border-blue-400 transition-colors"
            >
              <svg className="w-12 h-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              <p className="text-gray-400 text-center">
                사진을 선택하여<br />업로드해주세요
              </p>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleImageSelect}
            className="hidden"
          />
        </div>

        {/* User Info */}
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 rounded-full overflow-hidden">
            <img
              src="/QK.jpg"
              alt="Your profile"
              className="w-full h-full object-cover"
            />
          </div>
          <div>
            <p className="font-semibold text-white">김쿼카</p>
            <p className="text-sm text-gray-400">@kimquokka</p>
          </div>
        </div>

        {/* Caption Input */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            캡션
          </label>
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="이 순간에 대해 이야기해보세요..."
            rows={4}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-2xl text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 resize-none"
            maxLength={500}
          />
          <div className="text-right mt-1">
            <span className={`text-sm ${caption.length > 450 ? 'text-red-400' : 'text-gray-400'}`}>
              {caption.length}/500
            </span>
          </div>
        </div>

        {/* Location Input */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            위치 (선택사항)
          </label>
          <div className="relative">
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="위치를 추가해보세요"
              className="w-full pl-10 pr-4 py-3 bg-gray-800 border border-gray-700 rounded-2xl text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            />
            <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
        </div>

        {/* Additional Options */}
        <div className="space-y-4 mb-8">
          <div className="flex items-center justify-between p-4 bg-gray-800 rounded-2xl">
            <div className="flex items-center space-x-3">
              <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              <div>
                <p className="text-white font-medium">사람 태그하기</p>
                <p className="text-sm text-gray-400">친구들을 태그해보세요</p>
              </div>
            </div>
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>

          {/* <div className="flex items-center justify-between p-4 bg-gray-800 rounded-2xl">
            <div className="flex items-center space-x-3">
              <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className="text-white font-medium">Facebook에도 공유</p>
                <p className="text-sm text-gray-400">동시에 Facebook에 게시</p>
              </div>
            </div>
            <div className="relative inline-block w-10 mr-2 align-middle select-none">
              <input type="checkbox" className="sr-only" />
              <div className="w-10 h-6 bg-gray-600 rounded-full shadow-inner"></div>
              <div className="absolute block w-4 h-4 mt-1 ml-1 bg-white rounded-full shadow"></div>
            </div>
          </div> */}
        </div>

        {/* Upload Progress */}
        {isUploading && (
          <div className="mb-6">
            <div className="flex items-center justify-center space-x-2">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-400"></div>
              <span className="text-gray-300">업로드 중...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}