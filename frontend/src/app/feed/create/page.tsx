'use client'

import { useState, useRef, useEffect } from 'react'
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
  const [showLocationOptions, setShowLocationOptions] = useState(false)
  const [isGettingLocation, setIsGettingLocation] = useState(false)
  const [coordinates, setCoordinates] = useState<{ lat: number, lng: number } | null>(null)
  const [searchResults, setSearchResults] = useState<Array<{
    display_name: string
    lat: string
    lon: string
    name?: string
    type?: string
    city?: string
    importance?: number
  }>>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showSearchResults, setShowSearchResults] = useState(false)
  const locationInputRef = useRef<HTMLInputElement>(null)

  // 외부 클릭시 드롭다운 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element
      if (showLocationOptions && !target.closest('.location-dropdown')) {
        setShowLocationOptions(false)
      }
      if (showSearchResults && !target.closest('.search-results')) {
        setShowSearchResults(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showLocationOptions, showSearchResults])

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

  // GPS 위치 가져오기
  const getCurrentLocation = () => {
    if (!navigator.geolocation) {
      alert('GPS 기능을 지원하지 않는 브라우저입니다.')
      return
    }

    setIsGettingLocation(true)
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords
        setCoordinates({ lat: latitude, lng: longitude })

        // 역 지오코딩으로 주소 가져오기
        try {
          const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&accept-language=ko`
          )
          const data = await response.json()

          if (data.display_name) {
            // 간소화된 주소 생성 (첫 번째, 마지막 정보만)
            const parts = data.display_name.split(',').map((part: string) => part.trim())
            const first = parts[0] || ''
            const last = parts[parts.length - 1] || ''

            let simplifiedAddress = ''
            if (first === last || parts.length === 1) {
              simplifiedAddress = last
            } else {
              simplifiedAddress = `${first}, ${last}`
            }

            setLocation(simplifiedAddress)
          } else {
            setLocation(`${latitude}, ${longitude}`)
          }

          setShowLocationOptions(false)
        } catch (error) {
          console.error('주소 변환 실패:', error)
          setLocation(`${latitude}, ${longitude}`)
          setShowLocationOptions(false)
        } finally {
          setIsGettingLocation(false)
        }
      },
      (error) => {
        console.error('위치 가져오기 실패:', error)
        let errorMessage = '위치를 가져올 수 없습니다.'

        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMessage = '위치 접근 권한이 거부되었습니다. 브라우저 설정에서 위치 접근을 허용해주세요.'
            break
          case error.POSITION_UNAVAILABLE:
            errorMessage = '위치 정보를 사용할 수 없습니다.'
            break
          case error.TIMEOUT:
            errorMessage = '위치 요청 시간이 초과되었습니다.'
            break
        }

        alert(errorMessage)
        setIsGettingLocation(false)
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
      }
    )
  }

  // 위치 검색 (OpenStreetMap Nominatim API 사용)
  const searchLocation = async (query: string) => {
    if (!query.trim()) {
      setSearchResults([])
      setShowSearchResults(false)
      return
    }

    setIsSearching(true)
    try {
      const response = await fetch(
        `/api/places?query=${encodeURIComponent(query)}`
      )

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      if (data.error) {
        throw new Error(data.error)
      }

      // 검색 결과를 표준 형식으로 변환
      const formattedResults = data.map((item: any) => ({
        display_name: item.display_name,
        lat: item.lat,
        lon: item.lon,
        name: item.name,
        type: item.type,
        city: item.city,
        importance: item.importance
      }))

      setSearchResults(formattedResults)
      setShowSearchResults(true)
    } catch (error) {
      console.error('위치 검색 실패:', error)
      setSearchResults([])
      // 사용자에게 친화적인 오류 메시지 표시
      alert('위치 검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.')
    } finally {
      setIsSearching(false)
    }
  }

  // 검색 결과에서 위치 선택
  const selectSearchResult = (result: {
    display_name: string
    lat: string
    lon: string
    name?: string
    type?: string
    city?: string
    importance?: number
  }) => {
    // 간소화된 주소 생성 (첫 번째, 마지막 정보만)
    const parts = result.display_name.split(',').map((part: string) => part.trim())
    const first = parts[0] || ''
    const last = parts[parts.length - 1] || ''

    let simplifiedAddress = ''
    if (first === last || parts.length === 1) {
      simplifiedAddress = last
    } else {
      simplifiedAddress = `${first}, ${last}`
    }

    setLocation(simplifiedAddress)
    setCoordinates({ lat: parseFloat(result.lat), lng: parseFloat(result.lon) })
    setShowSearchResults(false)
    setShowLocationOptions(false)
  }

  // 디바운싱을 위한 useEffect
  useEffect(() => {
    const delayedSearch = setTimeout(() => {
      if (location && showSearchResults) {
        searchLocation(location)
      }
    }, 500)

    return () => clearTimeout(delayedSearch)
  }, [location, showSearchResults])

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

      // API 호출로 포스트 생성
      const response = await fetch('/api/proxy/api/v1/posts/', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          user_id: session.user.id, // 명시적으로 user_id 전송
          caption: caption,
          location: location || null,
          coordinates: coordinates ? `${coordinates.lat},${coordinates.lng}` : null,
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

        {/* User Info
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
        </div> */}

        {/* Caption Input */}
        <div className="mb-6">
          {/* <label className="block text-sm font-medium text-gray-300 mb-2">
            캡션
          </label> */}
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
        <div className="mb-6 location-dropdown">
          <div className="relative">
            <input
              ref={locationInputRef}
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder={showSearchResults ? "장소명을 입력하세요 (예: 홍대입구역, 강남구)" : "위치를 추가해보세요"}
              className="w-full pl-10 pr-12 py-3 bg-gray-800 border border-gray-700 rounded-2xl text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              onFocus={() => {
                if (location.trim()) {
                  setShowSearchResults(true)
                }
              }}
            />
            <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>

            {/* Location Options Button */}
            <button
              type="button"
              onClick={() => setShowLocationOptions(!showLocationOptions)}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-blue-400 hover:text-blue-300 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
              </svg>
            </button>
          </div>

          {/* Location Options Dropdown */}
          {showLocationOptions && (
            <div className="mt-2 bg-gray-800 border border-gray-700 rounded-2xl overflow-hidden">
              <button
                type="button"
                onClick={getCurrentLocation}
                disabled={isGettingLocation}
                className="w-full flex items-center px-4 py-3 text-left hover:bg-gray-700 transition-colors disabled:opacity-50"
              >
                <svg className="w-5 h-5 text-green-400 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <div>
                  <p className="text-white font-medium">
                    {isGettingLocation ? '현재 위치 가져오는 중...' : '현재 위치 사용'}
                  </p>
                  <p className="text-sm text-gray-400">GPS로 현재 위치를 가져옵니다</p>
                </div>
                {isGettingLocation && (
                  <div className="ml-auto">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-green-400"></div>
                  </div>
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setShowLocationOptions(false)
                  setShowSearchResults(true)
                  // 입력 필드에 포커스
                  setTimeout(() => {
                    locationInputRef.current?.focus()
                  }, 100)
                }}
                className="w-full flex items-center px-4 py-3 text-left hover:bg-gray-700 transition-colors border-t border-gray-700"
              >
                <svg className="w-5 h-5 text-blue-400 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <div>
                  <p className="text-white font-medium">위치 검색</p>
                  <p className="text-sm text-gray-400">장소명으로 위치를 검색합니다</p>
                </div>
              </button>
            </div>
          )}

          {/* Search Results Dropdown */}
          {showSearchResults && (
            <div className="mt-2 bg-gray-800 border border-gray-700 rounded-2xl overflow-hidden search-results">
              <div className="p-3 border-b border-gray-700">
                <div className="flex items-center space-x-2">
                  <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <p className="text-sm text-white font-medium">위치 검색 모드</p>
                </div>
                <p className="text-xs text-gray-400 mt-1">장소명을 입력하면 실시간으로 검색 결과가 나타납니다</p>
              </div>

              {isSearching && (
                <div className="p-4 flex items-center justify-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-400 mr-2"></div>
                  <span className="text-gray-400 text-sm">검색 중...</span>
                </div>
              )}

              {!isSearching && searchResults.length > 0 && (
                <div className="max-h-60 overflow-y-auto">
                  {searchResults.map((result, index) => (
                    <button
                      key={index}
                      type="button"
                      onClick={() => selectSearchResult(result)}
                      className="w-full flex items-start px-4 py-3 text-left hover:bg-gray-700 transition-colors border-b border-gray-700 last:border-b-0"
                    >
                      <svg className="w-4 h-4 text-red-400 mt-1 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <div className="flex-1">
                        <p className="text-white text-sm font-medium line-clamp-1">
                          {result.name || result.display_name.split(',')[0]}
                        </p>
                        <p className="text-gray-400 text-xs mt-1">
                          {(() => {
                            const parts = result.display_name.split(',').map((part: string) => part.trim())
                            const first = parts[0] || ''
                            const last = parts[parts.length - 1] || ''

                            // 첫 번째와 마지막이 같으면 하나만 표시
                            if (first === last || parts.length === 1) {
                              return last
                            }

                            return `${first}, ${last}`
                          })()}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {!isSearching && searchResults.length === 0 && location.trim() && (
                <div className="p-4 text-center">
                  <p className="text-gray-400 text-sm">&quot;{location}&quot;에 대한 검색 결과가 없습니다</p>
                  <p className="text-gray-500 text-xs mt-1">다른 키워드로 검색해보세요</p>
                </div>
              )}

              {!isSearching && searchResults.length === 0 && !location.trim() && (
                <div className="p-4 text-center">
                  <p className="text-gray-400 text-sm">검색어 예시:</p>
                  <div className="flex flex-wrap gap-2 mt-2 justify-center">
                    {['홍대입구역', '강남구', '부산역', '제주도'].map((example) => (
                      <button
                        key={example}
                        type="button"
                        onClick={() => {
                          setLocation(example)
                          locationInputRef.current?.focus()
                        }}
                        className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded hover:bg-gray-600 transition-colors"
                      >
                        {example}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Selected Location Display */}
          {location && coordinates && (
            <div className="mt-2 p-3 bg-gray-800 border border-gray-700 rounded-2xl">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="text-white font-medium text-sm">
                    {(() => {
                      const parts = location.split(',').map((part: string) => part.trim())
                      const first = parts[0] || ''
                      const last = parts[parts.length - 1] || ''

                      // 첫 번째와 마지막이 같으면 하나만 표시
                      if (first === last || parts.length === 1) {
                        return last
                      }

                      return `${first}, ${last}`
                    })()}
                  </p>
                  <p className="text-gray-400 text-xs mt-1">
                    좌표: {coordinates.lat.toFixed(6)}, {coordinates.lng.toFixed(6)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setLocation('')
                    setCoordinates(null)
                  }}
                  className="text-gray-400 hover:text-white transition-colors ml-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Additional Options */}
        {/* <div className="space-y-4 mb-8">
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
        </div> */}

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