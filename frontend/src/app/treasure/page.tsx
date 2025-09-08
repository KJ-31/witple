'use client'

import React from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

export default function TreasurePage() {
  const router = useRouter()

  return (
    <div className="min-h-screen bg-[#0B1220] text-white pb-20">
      {/* Header */}
      <div className="sticky top-0 bg-[#0B1220]/95 backdrop-blur-md z-40 border-b border-[#1F3C7A]/30">
        <div className="px-4 py-4">
          <h1 className="text-2xl font-bold text-[#3E68FF]">보물찾기</h1>
          <p className="text-[#94A9C9] text-sm mt-1">숨겨진 보물을 찾아보세요</p>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-6">
        <div className="text-center mt-20">
          <div className="w-24 h-24 bg-[#3E68FF]/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-12 h-12 text-[#3E68FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white mb-4">보물찾기 기능 준비 중</h2>
          <p className="text-[#94A9C9] mb-8">곧 새로운 보물찾기 기능을 만나실 수 있습니다.</p>
          <button
            onClick={() => router.push('/')}
            className="bg-[#3E68FF] text-white px-6 py-3 rounded-lg font-medium hover:bg-[#2E58EF] transition-colors"
          >
            홈으로 돌아가기
          </button>
        </div>
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
            href="/recommendations"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="추천"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
          </Link>

          <Link
            href="/treasure"
            className="flex flex-col items-center py-1 px-2 text-[#3E68FF]"
            aria-label="보물찾기"
          >
            <svg className="w-6 h-6 mb-1" fill="currentColor" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </Link>

          <Link
            href="/feed"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="피드"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
            </svg>
          </Link>

          <Link
            href="/profile"
            className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
            aria-label="마이페이지"
          >
            <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </Link>
        </div>
      </nav>
    </div>
  )
}