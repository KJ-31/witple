'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'

interface AttractionDetailProps {
  params: { id: string }
}

interface AttractionData {
  id: string
  name: string
  description: string
  imageUrl: string
  rating: number
  category: string
  address: string
  region: string
  city: {
    id: string
    name: string
    region: string
  }
  latitude?: number
  longitude?: number
  phoneNumber?: string
  parkingAvailable?: string
  usageHours?: string
  closedDays?: string
  detailedInfo?: string
  majorCategory?: string
  middleCategory?: string
  minorCategory?: string
  imageUrls?: string[]
  businessHours?: string
  signatureMenu?: string
  menu?: string
  roomCount?: string
  roomType?: string
  checkIn?: string
  checkOut?: string
  cookingAvailable?: string
}

export default function AttractionDetail({ params }: AttractionDetailProps) {
  const router = useRouter()
  const { data: session } = useSession()
  const [attraction, setAttraction] = useState<AttractionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSaved, setIsSaved] = useState(false)
  const [saveLoading, setSaveLoading] = useState(false)

  // 토큰 가져오기 함수
  const getToken = () => {
    // 먼저 세션에서 토큰 확인
    if ((session as any)?.backendToken) {
      return (session as any).backendToken
    }
    // 세션에 없으면 localStorage에서 확인
    return localStorage.getItem('access_token')
  }

  // API에서 관광지 상세 정보 가져오기
  useEffect(() => {
    const fetchAttractionDetail = async () => {
      try {
        setLoading(true)
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
        
        // 새로운 ID 형식 처리: table_name_id 형식인 경우
        let apiUrl = `${API_BASE_URL}/api/v1/attractions/attractions/${params.id}`
        
        const response = await fetch(apiUrl)
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        
        const data = await response.json()
        setAttraction(data)
        
        // 저장 상태도 함께 확인
        await checkSavedStatus(data)
      } catch (error) {
        console.error('관광지 정보 로드 오류:', error)
        setError('관광지 정보를 불러올 수 없습니다.')
      } finally {
        setLoading(false)
      }
    }

    if (params.id) {
      fetchAttractionDetail()
    }
  }, [params.id])

  // 저장 상태 확인 함수
  const checkSavedStatus = async (attractionData: AttractionData) => {
    try {
      const token = getToken()
      if (!token) return
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/saved-locations/check`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          name: attractionData.name,
          address: attractionData.address,
          latitude: attractionData.latitude?.toString(),
          longitude: attractionData.longitude?.toString()
        })
      })
      
      if (response.ok) {
        const data = await response.json()
        setIsSaved(data.is_saved)
      } else if (response.status === 401) {
        console.log('토큰 만료됨 - 저장 상태 확인 건너뛰기')
        localStorage.removeItem('access_token')
      }
    } catch (error) {
      console.error('저장 상태 확인 오류:', error)
    }
  }

  // 북마크 토글 함수
  const handleBookmarkToggle = async () => {
    if (!attraction || saveLoading) return
    
    try {
      setSaveLoading(true)
      const token = getToken()
      
      if (!token) {
        alert('로그인이 필요합니다.')
        router.push('/auth/login')
        return
      }
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      
      if (isSaved) {
        // 저장 해제
        const checkResponse = await fetch(`${API_BASE_URL}/api/v1/saved-locations/check`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            name: attraction.name,
            address: attraction.address,
            latitude: attraction.latitude?.toString(),
            longitude: attraction.longitude?.toString()
          })
        })
        
        if (checkResponse.ok) {
          const checkData = await checkResponse.json()
          if (checkData.location_id) {
            const deleteResponse = await fetch(`${API_BASE_URL}/api/v1/saved-locations/${checkData.location_id}`, {
              method: 'DELETE',
              headers: {
                'Authorization': `Bearer ${token}`
              }
            })
            
            if (deleteResponse.ok) {
              setIsSaved(false)
            } else if (deleteResponse.status === 401) {
              alert('세션이 만료되었습니다. 다시 로그인해주세요.')
              localStorage.removeItem('access_token')
              router.push('/auth/login')
              return
            }
          }
        } else if (checkResponse.status === 401) {
          alert('세션이 만료되었습니다. 다시 로그인해주세요.')
          localStorage.removeItem('access_token')
          router.push('/auth/login')
          return
        }
      } else {
        // 저장
        const response = await fetch(`${API_BASE_URL}/api/v1/saved-locations/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            name: attraction.name,
            address: attraction.address,
            latitude: attraction.latitude?.toString(),
            longitude: attraction.longitude?.toString()
          })
        })
        
        if (response.ok) {
          setIsSaved(true)
        } else if (response.status === 401) {
          alert('세션이 만료되었습니다. 다시 로그인해주세요.')
          localStorage.removeItem('access_token')
          router.push('/auth/login')
          return
        }
      }
    } catch (error) {
      console.error('북마크 처리 오류:', error)
    } finally {
      setSaveLoading(false)
    }
  }

  const handleBack = () => {
    router.back()
  }

  const handleAddToItinerary = () => {
    // 여행 계획 세우기 페이지로 이동
    router.push(`/plan/${params.id}`)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
          <p className="text-[#94A9C9]">상세 정보를 불러오는 중...</p>
        </div>
      </div>
    )
  }

  if (error || !attraction) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-xl text-[#94A9C9] mb-4">{error || '명소를 찾을 수 없습니다'}</p>
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

  return (
    <div className="min-h-screen bg-[#0B1220] text-white overflow-y-auto no-scrollbar">
      {/* Header with back button and bookmark */}
      <div className="relative">
        <button
          onClick={handleBack}
          className="absolute top-4 left-4 z-10 p-2 bg-black/30 rounded-full backdrop-blur-sm hover:bg-black/50 transition-colors"
        >
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        {/* Bookmark button */}
        <button
          onClick={handleBookmarkToggle}
          disabled={saveLoading}
          className={`absolute top-4 right-4 z-10 p-2 rounded-full backdrop-blur-sm transition-colors ${
            isSaved 
              ? 'bg-[#3E68FF]/80 hover:bg-[#3E68FF]' 
              : 'bg-black/30 hover:bg-black/50'
          } ${saveLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {saveLoading ? (
            <div className="animate-spin rounded-full h-6 w-6 border-2 border-white border-t-transparent"></div>
          ) : (
            <svg 
              className={`w-6 h-6 transition-colors ${isSaved ? 'text-white' : 'text-white'}`}
              fill={isSaved ? "currentColor" : "none"} 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" 
              />
            </svg>
          )}
        </button>

        {/* Main image */}
        <div className="relative h-[60vh] bg-gradient-to-b from-blue-600 to-purple-700 flex items-center justify-center">
          {attraction.imageUrls && attraction.imageUrls.length > 0 ? (
            <div className="absolute inset-0">
              <img 
                src={attraction.imageUrls[0]} 
                alt={attraction.name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  const target = e.target as HTMLImageElement;
                  target.style.display = 'none';
                }}
              />
              <div className="absolute inset-0 bg-black/30"></div>
            </div>
          ) : null}
          
          <div className="text-center relative z-10">
            <h1 className="text-4xl font-bold text-white mb-2">{attraction.name}</h1>
            <p className="text-lg text-blue-100 opacity-80">{attraction.city.name}</p>
          </div>
          
          {/* Gradient overlay at bottom */}
          <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-[#0B1220] to-transparent"></div>
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-4">
        {/* City and attraction name */}
        <div className="mb-6">
          <p className="text-[#6FA0E6] text-lg mb-1">{attraction.city.name}</p>
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
        <div className="mb-6">
          <p className="text-[#94A9C9] leading-relaxed text-lg mb-4">
            {attraction.description}
          </p>
          {attraction.detailedInfo && (
            <div className="bg-[#0F1A31]/50 rounded-lg p-4">
              <h4 className="text-white font-medium mb-2">상세 정보</h4>
              <p className="text-[#94A9C9] text-sm leading-relaxed"
                 dangerouslySetInnerHTML={{ __html: attraction.detailedInfo.replace(/\n/g, '<br>') }}
              ></p>
            </div>
          )}
        </div>

        {/* Location and Contact Info */}
        {(attraction.address || attraction.phoneNumber) && (
          <div className="mb-6 space-y-3">
            {attraction.address && (
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-[#6FA0E6] mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <div>
                  <p className="text-white font-medium text-sm">주소</p>
                  <p className="text-[#94A9C9] text-sm">{attraction.address}</p>
                </div>
              </div>
            )}
            
            {attraction.phoneNumber && (
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-[#6FA0E6] mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
                <div>
                  <p className="text-white font-medium text-sm">전화번호</p>
                  <p className="text-[#94A9C9] text-sm">{attraction.phoneNumber}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Operating Hours and Additional Info */}
        <div className="mb-6 space-y-3">
          {(attraction.businessHours || attraction.usageHours) && (
            <div className="bg-[#0F1A31]/30 rounded-lg p-4">
              <h4 className="text-white font-medium mb-2 flex items-center gap-2">
                <svg className="w-4 h-4 text-[#6FA0E6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                운영시간
              </h4>
              <p className="text-[#94A9C9] text-sm"
                 dangerouslySetInnerHTML={{ 
                   __html: (attraction.businessHours || attraction.usageHours || '').replace(/\n/g, '<br>').replace(/<br>/g, '<br>') 
                 }}
              ></p>
            </div>
          )}
          
          {attraction.closedDays && (
            <div className="bg-[#0F1A31]/30 rounded-lg p-4">
              <h4 className="text-white font-medium mb-2">휴무일</h4>
              <p className="text-[#94A9C9] text-sm">{attraction.closedDays}</p>
            </div>
          )}

          {attraction.parkingAvailable && (
            <div className="bg-[#0F1A31]/30 rounded-lg p-4">
              <h4 className="text-white font-medium mb-2">주차 정보</h4>
              <p className="text-[#94A9C9] text-sm"
                 dangerouslySetInnerHTML={{ __html: attraction.parkingAvailable.replace(/<br>/g, '<br>') }}
              ></p>
            </div>
          )}

          {/* Restaurant specific info */}
          {attraction.signatureMenu && (
            <div className="bg-[#0F1A31]/30 rounded-lg p-4">
              <h4 className="text-white font-medium mb-2">대표 메뉴</h4>
              <p className="text-[#94A9C9] text-sm">{attraction.signatureMenu}</p>
              {attraction.menu && (
                <>
                  <h4 className="text-white font-medium mb-1 mt-3">메뉴</h4>
                  <p className="text-[#94A9C9] text-sm">{attraction.menu}</p>
                </>
              )}
            </div>
          )}

          {/* Accommodation specific info */}
          {attraction.checkIn && (
            <div className="bg-[#0F1A31]/30 rounded-lg p-4">
              <h4 className="text-white font-medium mb-2">숙박 정보</h4>
              <div className="space-y-1 text-sm">
                <p className="text-[#94A9C9]">체크인: {attraction.checkIn}</p>
                <p className="text-[#94A9C9]">체크아웃: {attraction.checkOut}</p>
                {attraction.roomCount && <p className="text-[#94A9C9]">객실 수: {attraction.roomCount}</p>}
                {attraction.cookingAvailable && <p className="text-[#94A9C9]">취사 가능: {attraction.cookingAvailable}</p>}
              </div>
            </div>
          )}
        </div>

        {/* Action button */}
        <div className="mb-8">
          <button 
            onClick={handleAddToItinerary}
            className="w-full bg-[#3E68FF] hover:bg-[#4C7DFF] text-white py-4 rounded-2xl text-lg font-semibold transition-colors flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3a1 1 0 011-1h6a1 1 0 011 1v4M8 7h8M8 7H6a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V9a2 2 0 00-2-2h-2m-6 4v4m-4-2h8" />
            </svg>
            여행 계획 세우기
          </button>
        </div>
      </div>
    </div>
  )
}

// 카테고리 한국어 변환 함수
function getCategoryName(category: string): string {
  const categoryMap: { [key: string]: string } = {
    nature: '자연',
    restaurants: '맛집',
    shopping: '쇼핑',
    accommodation: '숙박',
    humanities: '인문',
    leisure_sports: '레저'
  }
  return categoryMap[category] || category
}