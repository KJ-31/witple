'use client'

import React, { useState } from 'react'
import Link from 'next/link'

export default function Home() {
  const [searchQuery, setSearchQuery] = useState('')
  const [currentImageIndex, setCurrentImageIndex] = useState<{[key: number]: number}>({})

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

  const nextImage = (setIndex: number) => {
    setCurrentImageIndex(prev => ({
      ...prev,
      [setIndex]: ((prev[setIndex] || 0) + 1) % imageSets[setIndex].images.length
    }))
  }

  const prevImage = (setIndex: number) => {
    setCurrentImageIndex(prev => ({
      ...prev,
      [setIndex]: ((prev[setIndex] || 0) - 1 + imageSets[setIndex].images.length) % imageSets[setIndex].images.length
    }))
  }

  const handleSearch = async (e: React.FormEvent<HTMLFormElement>) => {
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
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Top Navigation */}
      <nav className="flex justify-between items-center p-4">
        <div className="flex space-x-6">
          {/* My Page Icon */}
          <Link href="/mypage" className="p-2 rounded-full border-2 border-blue-500 hover:bg-blue-500 transition-colors">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </Link>
        </div>

        <div className="flex space-x-6">
          {/* Quest Icon */}
          <Link href="/quest" className="p-2 rounded-full border-2 border-blue-500 hover:bg-blue-500 transition-colors">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </Link>
          
          {/* Treasure Hunt Icon */}
          <Link href="/treasure" className="p-2 rounded-full border-2 border-blue-500 hover:bg-blue-500 transition-colors">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </Link>
          
          {/* Feed Icon */}
          <Link href="/feed" className="p-2 rounded-full border-2 border-blue-500 hover:bg-blue-500 transition-colors">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
            </svg>
          </Link>
        </div>
      </nav>

      {/* Main Content */}
      <main className="px-4 pb-8">
        {/* Logo */}
        <div className="text-center mb-12 mt-8">
          <h1 className="text-6xl font-bold text-blue-500 mb-4">witple</h1>
        </div>

        {/* Search Bar */}
        <div className="max-w-2xl mx-auto mb-16">
          <form onSubmit={handleSearch} className="relative">
            <input
              type="text"
              placeholder="어디로 떠나볼까요?"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-6 py-4 text-lg rounded-full bg-blue-900 text-white placeholder-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="absolute right-4 top-1/2 transform -translate-y-1/2 p-2 text-blue-300 hover:text-white transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
          </form>
        </div>

        {/* Image Carousel Sections */}
        <div className="space-y-12">
          {imageSets.map((imageSet, setIndex) => {
            const currentIndex = currentImageIndex[setIndex] || 0
            return (
              <div key={setIndex} className="max-w-4xl mx-auto">
                <h2 className="text-2xl font-semibold mb-6 text-gray-300">
                  {imageSet.title}
                </h2>
                
                {/* Carousel Container */}
                <div className="relative">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {imageSet.images.map((image, imageIndex) => (
                      <div
                        key={imageIndex}
                        className={`relative group cursor-pointer overflow-hidden rounded-lg transition-all duration-500 ${
                          imageIndex === currentIndex 
                            ? 'transform scale-105 ring-2 ring-blue-500' 
                            : 'opacity-70 hover:opacity-100'
                        }`}
                        onClick={() => setCurrentImageIndex(prev => ({ ...prev, [setIndex]: imageIndex }))}
                      >
                        {/* Placeholder for images - in real app, use Next.js Image component */}
                        <div className="aspect-[4/3] bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
                          <span className="text-white text-lg opacity-70">
                            {image.alt}
                          </span>
                        </div>
                        <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all duration-300"></div>
                      </div>
                    ))}
                  </div>
                  
                  {/* Carousel Navigation */}
                  {imageSet.images.length > 2 && (
                    <>
                      <button
                        onClick={() => prevImage(setIndex)}
                        className="absolute left-0 top-1/2 transform -translate-y-1/2 -translate-x-4 bg-black bg-opacity-50 hover:bg-opacity-75 rounded-full p-2 transition-all duration-200"
                      >
                        <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                      <button
                        onClick={() => nextImage(setIndex)}
                        className="absolute right-0 top-1/2 transform -translate-y-1/2 translate-x-4 bg-black bg-opacity-50 hover:bg-opacity-75 rounded-full p-2 transition-all duration-200"
                      >
                        <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </>
                  )}
                  
                  {/* Dot indicators */}
                  <div className="flex justify-center space-x-2 mt-4">
                    {imageSet.images.map((_, index) => (
                      <button
                        key={index}
                        onClick={() => setCurrentImageIndex(prev => ({ ...prev, [setIndex]: index }))}
                        className={`w-3 h-3 rounded-full transition-all duration-200 ${
                          index === currentIndex 
                            ? 'bg-blue-500' 
                            : 'bg-gray-600 hover:bg-gray-400'
                        }`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </main>
    </div>
  )
}
