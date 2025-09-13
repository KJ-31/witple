'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'

export default function BottomNavigation() {
  const pathname = usePathname()
  const { data: session, status } = useSession()
  const router = useRouter()

  const isActive = (href: string) => {
    if (href === '/') {
      return pathname === '/'
    }
    return pathname.startsWith(href)
  }

  const handleProfileClick = () => {
    if (status === 'authenticated' && session) {
      router.push('/profile')
    } else {
      router.push('/auth/login')
    }
  }

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-[#0F1A31]/95 backdrop-blur-md border-t border-[#1F3C7A]/30 z-50">
      <div className="flex items-center justify-around px-4 py-5 max-w-md mx-auto">
        <Link
          href="/"
          className={`flex flex-col items-center py-1 px-2 transition-colors ${isActive('/')
              ? 'text-[#3E68FF]'
              : 'text-[#6FA0E6] hover:text-[#3E68FF]'
            }`}
          aria-label="홈"
        >
          <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
        </Link>

        <Link
          href="/recommendations"
          className={`flex flex-col items-center py-1 px-2 transition-colors ${isActive('/recommendations')
              ? 'text-[#3E68FF]'
              : 'text-[#6FA0E6] hover:text-[#3E68FF]'
            }`}
          aria-label="추천"
        >
          <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
          </svg>
        </Link>

        <Link
          href="/plan/calendar"
          className={`flex flex-col items-center py-1 px-2 transition-colors ${isActive('/plan')
              ? 'text-[#3E68FF]'
              : 'text-[#6FA0E6] hover:text-[#3E68FF]'
            }`}
          aria-label="일정 작성"
        >
          <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3a1 1 0 011-1h6a1 1 0 011 1v4M8 7h8M8 7H6a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V9a2 2 0 00-2-2h-2m-6 4v4m-4-2h8" />
          </svg>
        </Link>

        <Link
          href="/feed"
          className={`flex flex-col items-center py-1 px-2 transition-colors ${isActive('/feed')
              ? 'text-[#3E68FF]'
              : 'text-[#6FA0E6] hover:text-[#3E68FF]'
            }`}
          aria-label="피드"
        >
          <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
          </svg>
        </Link>

        <button
          onClick={handleProfileClick}
          className="flex flex-col items-center py-1 px-2 text-[#6FA0E6] hover:text-[#3E68FF] transition-colors"
          aria-label="마이페이지"
        >
          <svg className="w-6 h-6 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        </button>
      </div>
    </nav>
  )
}