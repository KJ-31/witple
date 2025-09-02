'use client'

import React, { useState, FormEvent } from 'react'
import Link from 'next/link'

export default function Home() {
  const [searchQuery, setSearchQuery] = useState('')

  const imageSets = [
    {
      title: '과거와 현재가 공존하는, 서울',
      images: [
        { src: '/images/seoul-modern.jpg', alt: '서울 현대적 건물' },
        { src: '/images/seoul-traditional.jpg', alt: '서울 전통 건물' }
      ]
    },
    {
      title: '영화의 도시, 부산',
      images: [
        { src: '/images/busan-market.jpg', alt: '부산 전통시장' },
        { src: '/images/busan-food.jpg', alt: '부산 음식' }
      ]
    }
  ]

  const handleSearch = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    try {
      const { searchPlaces } = await import('./api/search')
      const results = await searchPlaces(searchQuery)
      console.log('검색 결과:', results)
    } catch (error) {
      console.error('검색 오류:', error)
    }
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-slate-200 overflow-y-auto no-scrollbar">
      {/* Top Navigation */}
      <nav className="flex items-center justify-between px-4 pt-4">
        <Link
          href="/mypage"
          className="p-2 rounded-full border border-[#1F3C7A] text-[#4C7DFF] hover:bg-[#14213B] transition-colors"
          aria-label="마이페이지"
        >
          {/* user icon */}
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        </Link>

        <div className="flex items-center gap-4">
          <Link href="/quest" className="p-2 rounded-full border border-[#1F3C7A] text-[#4C7DFF] hover:bg-[#14213B] transition-colors" aria-label="퀘스트">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </Link>
          <Link href="/treasure" className="p-2 rounded-full border border-[#1F3C7A] text-[#4C7DFF] hover:bg-[#14213B] transition-colors" aria-label="보물찾기">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </Link>
          <Link href="/feed" className="p-2 rounded-full border border-[#1F3C7A] text-[#4C7DFF] hover:bg-[#14213B] transition-colors" aria-label="피드">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
            </svg>
          </Link>
        </div>
      </nav>

      {/* Logo */}
      <div className="text-center mt-10 mb-8">
        <h1 className="text-6xl font-extrabold text-[#3E68FF] tracking-tight">witple</h1>
      </div>

      {/* Search Bar */}
      <div className="px-4 mb-12">
        <form onSubmit={handleSearch} className="relative">
          <input
            type="text"
            placeholder="어디로 떠나볼까요?"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="
              w-full px-6 pr-12 py-5 text-lg
              rounded-3xl
              bg-[#12345D]/70
              text-slate-200 placeholder-[#6FA0E6]
              ring-1 ring-[#1F3C7A] shadow-xl
              focus:outline-none focus:ring-2 focus:ring-[#3E68FF]/60
            "
          />
          <button
            type="submit"
            className="absolute right-5 top-1/2 -translate-y-1/2 p-1 text-[#6FA0E6] hover:text-white transition"
            aria-label="검색"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
        </form>
      </div>

      {/* 세로로 섹션이 쌓이고, 섹션 안의 이미지들은 가로 스와이프 */}
      <main className="px-4 pb-16 space-y-12">
        {imageSets.map((set, i) => (
          <SectionCarousel key={i} title={set.title} images={set.images} />
        ))}
      </main>
    </div>
  )
}

/** 섹션 하나: 제목 + (가로 스와이프) 카드들 */
function SectionCarousel({
  title,
  images,
}: {
  title: string
  images: { src: string; alt: string }[]
}) {
  return (
    <section aria-label={title} className="w-full">
      <h2 className="text-2xl md:text-3xl font-semibold text-[#94A9C9] mb-5">
        {title}
      </h2>

      {/* 가로 캐러셀 트랙 */}
      <div className="relative -mx-4 px-4">
        <div
          className="
            flex items-stretch gap-4
            overflow-x-auto no-scrollbar
            snap-x snap-mandatory scroll-smooth
            pb-2
          "
          style={{ scrollBehavior: 'smooth' }}
        >
          {images.map((img, idx) => (
            <figure
              key={idx}
              className="
                snap-start shrink-0
                rounded-[28px] overflow-hidden
                bg-[#0F1A31] ring-1 ring-white/5
                aspect-[4/3]
                w-[78%] xs:w-[70%] sm:w-[320px]
              "
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img.src}
                alt={img.alt}
                loading="lazy"
                className="w-full h-full object-cover"
              />
            </figure>
          ))}
        </div>

        {/* 좌/우 가장자리 페이드(선택사항) */}
        <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-[#0B1220] to-transparent" />
        <div className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-[#0B1220] to-transparent" />
      </div>
    </section>
  )
}

/* 전역 CSS(globals.css) 권장 추가
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
*/
