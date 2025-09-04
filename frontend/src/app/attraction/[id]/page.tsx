'use client'

import React from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { RECOMMENDED_CITY_SECTIONS, type Attraction } from '../../../lib/dummyData'

interface AttractionDetailProps {
  params: { id: string }
}

export default function AttractionDetail({ params }: AttractionDetailProps) {
  const router = useRouter()
  
  // URL에서 attraction ID로 해당 명소와 도시 정보 찾기
  const findAttractionAndCity = (attractionId: string) => {
    for (const city of RECOMMENDED_CITY_SECTIONS) {
      const attraction = city.attractions.find(attr => attr.id === attractionId)
      if (attraction) {
        return { attraction, city }
      }
    }
    return null
  }

  const result = findAttractionAndCity(params.id)
  
  if (!result) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-xl text-[#94A9C9] mb-4">명소를 찾을 수 없습니다</p>
          <Link 
            href="/"
            className="text-[#3E68FF] hover:text-[#6FA0E6] transition-colors"
          >
            홈으로 돌아가기
          </Link>
        </div>
      </div>
    )
  }

  const { attraction, city } = result

  const handleBack = () => {
    router.back()
  }

  const handleSelectAttraction = () => {
    router.push(`/plan/${params.id}`)
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-white overflow-y-auto no-scrollbar">
      {/* Header with back button */}
      <div className="relative">
        <button
          onClick={handleBack}
          className="absolute top-4 left-4 z-10 p-2 bg-black/30 rounded-full backdrop-blur-sm hover:bg-black/50 transition-colors"
        >
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        {/* Main image */}
        <div className="relative h-[60vh] bg-gradient-to-b from-blue-600 to-purple-700 flex items-center justify-center">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-white mb-2">{attraction.name}</h1>
            <p className="text-lg text-blue-100 opacity-80">{city.cityName}</p>
          </div>
          
          {/* Gradient overlay at bottom */}
          <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-[#0B1220] to-transparent"></div>
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-4">
        {/* City and attraction name */}
        <div className="mb-6">
          <p className="text-[#6FA0E6] text-lg mb-1">{city.cityName}</p>
          <h2 className="text-3xl font-bold text-[#3E68FF] mb-4">{attraction.name}</h2>
        </div>

        {/* Rating and category */}
        <div className="flex items-center gap-4 mb-6">
          <div className="flex items-center bg-[#12345D]/50 rounded-full px-4 py-2">
            <svg className="w-5 h-5 text-yellow-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            <span className="text-white font-medium text-lg">{attraction.rating}</span>
          </div>
          
          <div className="bg-[#1F3C7A]/30 rounded-full px-4 py-2">
            <span className="text-[#94A9C9] text-sm">
              {getCategoryName(attraction.category)}
            </span>
          </div>
        </div>

        {/* Description */}
        <div className="mb-8">
          <p className="text-[#94A9C9] leading-relaxed text-lg">
            {getDetailedDescription(attraction.id, attraction.description)}
          </p>
        </div>

        {/* Action button */}
        <div className="mb-8">
          <button 
            onClick={handleSelectAttraction}
            className="w-full bg-[#3E68FF] hover:bg-[#4C7DFF] text-white py-4 rounded-2xl text-lg font-semibold transition-colors"
          >
            선택
          </button>
        </div>

        {/* Additional info or related attractions could go here */}
        <div className="border-t border-[#1F3C7A]/30 pt-6">
          <h3 className="text-xl font-semibold text-[#94A9C9] mb-4">
            {city.cityName}의 다른 명소
          </h3>
          <div className="grid grid-cols-1 gap-3">
            {city.attractions
              .filter(attr => attr.id !== attraction.id)
              .slice(0, 3)
              .map(relatedAttr => (
                <Link
                  key={relatedAttr.id}
                  href={`/attraction/${relatedAttr.id}`}
                  className="flex items-center p-3 bg-[#0F1A31]/50 rounded-lg hover:bg-[#12345D]/50 transition-colors group"
                >
                  <div className="flex-1">
                    <h4 className="text-white font-medium group-hover:text-[#3E68FF] transition-colors">
                      {relatedAttr.name}
                    </h4>
                    <p className="text-[#6FA0E6] text-sm mt-1">
                      ⭐ {relatedAttr.rating} • {getCategoryName(relatedAttr.category)}
                    </p>
                  </div>
                  <svg className="w-5 h-5 text-[#6FA0E6] group-hover:text-[#3E68FF] transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Link>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// 카테고리 한국어 변환 함수
function getCategoryName(category: string): string {
  const categoryMap: { [key: string]: string } = {
    tourist: '관광',
    food: '맛집',
    culture: '문화',
    nature: '자연',
    shopping: '쇼핑'
  }
  return categoryMap[category] || category
}

// 상세 설명 생성 함수 (실제로는 데이터베이스에서 가져와야 함)
function getDetailedDescription(attractionId: string, shortDescription: string): string {
  const detailedDescriptions: { [key: string]: string } = {
    'gyeongbokgung': '과거와 현재가 공존하며 하루가 다르게 변하는 서울을 여행하는 일은 매일이 새롭다. 도시 한복판에서 600년의 역사를 그대로 안고 있는 아름다운 고궁들과 더불어 대한민국의 트렌드를 이끌어나가는 예술과 문화의 크고 작은 동네들을 들러볼 수 있는 서울은 도시 여행에 최적화된 장소다.',
    'myeongdong': '명동은 서울의 대표적인 쇼핑과 관광의 중심지입니다. 국내외 브랜드 매장과 다양한 맛집들이 밀집해 있어 쇼핑과 미식을 동시에 즐길 수 있는 곳입니다.',
    'namsan-tower': '남산서울타워는 서울의 상징적인 랜드마크로, 서울 시내를 한눈에 내려다볼 수 있는 최고의 전망대입니다. 특히 야경이 아름다워 연인들에게 인기가 높습니다.',
    'hongdae': '홍익대학교 주변의 홍대는 젊은 예술가들과 대학생들이 만들어내는 역동적인 문화 공간입니다. 클럽, 라이브 하우스, 독특한 카페들이 가득한 젊음의 거리입니다.',
  }
  
  return detailedDescriptions[attractionId] || `${shortDescription}에 대한 더 자세한 정보를 제공합니다. 이곳은 ${shortDescription}로 유명한 곳으로, 방문객들에게 특별한 경험을 선사합니다.`
}