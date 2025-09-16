'use client'

import React, { useEffect, useRef, useState, memo, useMemo } from 'react'
import { Loader } from '@googlemaps/js-api-loader'

interface GoogleMapProps {
  className?: string
  center?: { lat: number; lng: number }
  zoom?: number
  markers?: Array<{
    position: { lat: number; lng: number }
    title?: string
    id?: string
    type?: 'itinerary' | 'category'
    category?: string
  }>
  onMapLoad?: (map: any) => void
  onMarkerClick?: (markerId: string, markerType: string, position?: { lat: number; lng: number }) => void
  selectedMarkerIdFromParent?: string | null
  source?: string | null // GPS 활성화 여부를 결정하는 source 파라미터 추가
  disableAutoBounds?: boolean // 자동 bounds 조정 비활성화 옵션
}

// 카테고리별 아이콘 매핑
const getCategoryIcon = (category?: string): string => {
  const iconMap: { [key: string]: string } = {
    'accommodation': '🏨',
    'humanities': '🏛️', 
    'leisure_sports': '⚽',
    'nature': '🌿',
    'restaurants': '🍽️',
    'shopping': '🛍️'
  }
  return iconMap[category || ''] || '📍'
}

// 마커 아이콘 생성 함수
const createMarkerIcon = (categoryIcon: string, isSelected: boolean = false) => {
  const size = isSelected ? 30 : 20 // 선택된 마커는 1.5배 크기
  const anchor = isSelected ? 15 : 10
  
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
      <svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
        <circle cx="20" cy="20" r="18" fill="#3E68FF" stroke="#ffffff" stroke-width="2"/>
        <text x="20" y="27" font-family="Arial" font-size="16" text-anchor="middle" fill="white">${categoryIcon}</text>
      </svg>
    `)}`,
    scaledSize: new (window as any).google.maps.Size(size, size),
    anchor: new (window as any).google.maps.Point(anchor, anchor)
  }
}

const GoogleMapComponent: React.FC<GoogleMapProps> = memo(({
  className = '',
  center = { lat: 37.5665, lng: 126.9780 },
  zoom = 13,
  markers = [],
  onMapLoad,
  onMarkerClick,
  selectedMarkerIdFromParent = null,
  source = null,
  disableAutoBounds = false
}) => {
  const mapRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<any>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const [selectedMarkerId, setSelectedMarkerId] = useState<string | null>(null)
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null)
  const [userLocationMarker, setUserLocationMarker] = useState<any>(null)
  const [locationWatchId, setLocationWatchId] = useState<number | null>(null)
  const [gpsMode, setGpsMode] = useState<'off' | 'location' | 'compass'>('off') // GPS 버튼 모드 상태
  const [currentHeading, setCurrentHeading] = useState<number | null>(null) // 현재 방향 저장
  const itineraryMarkersRef = useRef<any[]>([])
  const categoryMarkersRef = useRef<any[]>([])
  const markerInstancesRef = useRef<Map<string, { marker: any, category: string }>>(new Map())

  // 마커를 타입별로 분리 (메모이제이션으로 최적화)
  const itineraryMarkers = useMemo(() => {
    const filtered = markers.filter(m => m.type === 'itinerary')
    return filtered
  }, [JSON.stringify(markers.filter(m => m.type === 'itinerary'))])
  
  const categoryMarkers = useMemo(() => {
    const filtered = markers.filter(m => m.type === 'category')
    return filtered
  }, [JSON.stringify(markers.filter(m => m.type === 'category'))])

  useEffect(() => {
    const initMap = async () => {
      // // 모바일 환경 감지
      // const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
      // console.log('Mobile device detected:', isMobile)
      
      
      const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
      
      
      if (!apiKey || apiKey === '') {
        console.error('Google Maps API Key가 설정되지 않았습니다')
        return
      }

      const loader = new Loader({
        apiKey,
        version: 'weekly',
        libraries: ['places']
      })

      try {
        const google = await loader.load()
        
        if (mapRef.current && (window as any).google) {
          const mapInstance = new (window as any).google.maps.Map(mapRef.current, {
            center,
            zoom,
            disableDefaultUI: true,
            gestureHandling: 'greedy',
            clickableIcons: false,
            keyboardShortcuts: false,
          })

          setMap(mapInstance)
          setIsLoaded(true)
          
          // 지도가 로드되면 부모 컴포넌트에 알림
          if (onMapLoad) {
            onMapLoad(mapInstance)
          }
        }
      } catch (error) {
        console.error('Google Maps 로드 실패:', error)
      }
    }

    // 지도가 아직 없을 때만 초기화
    if (!map && mapRef.current) {
      initMap()
    }
  }, [center, zoom, map, onMapLoad])

  // 일정 마커 관리
  useEffect(() => {
    if (map && (window as any).google) {
      // 기존 일정 마커 제거
      itineraryMarkersRef.current.forEach(marker => marker.setMap(null))
      itineraryMarkersRef.current = []

      itineraryMarkers.forEach((markerData) => {
        const isSelected = selectedMarkerId === markerData.id
        const scale = isSelected ? 12 : 8 // 선택된 마커는 1.5배 크기

        const marker = new (window as any).google.maps.Marker({
          position: markerData.position,
          map,
          title: markerData.title || '',
          icon: {
            path: (window as any).google.maps.SymbolPath.CIRCLE,
            scale: scale,
            fillColor: '#FF6B6B', // 일정 마커는 빨간색
            fillOpacity: 1,
            strokeColor: '#ffffff',
            strokeWeight: 2
          }
        })

        // 마커 인스턴스와 카테고리 정보 저장 (일정 마커용)
        if (markerData.id) {
          markerInstancesRef.current.set(markerData.id, {
            marker: marker,
            category: 'itinerary' // 일정 마커 표시
          })
        }

        // 마커 클릭 이벤트 추가
        marker.addListener('click', () => {
          if (onMarkerClick && markerData.id) {
            // 부모 컴포넌트에 일정 마커 클릭 알림
            onMarkerClick(markerData.id, markerData.type || 'itinerary', markerData.position)
          }
        })

        itineraryMarkersRef.current.push(marker)
      })
    }
  }, [map, itineraryMarkers, selectedMarkerId])

  // 카테고리 마커 관리
  useEffect(() => {
    if (map && (window as any).google) {
      // 기존 카테고리 마커 제거
      categoryMarkersRef.current.forEach(marker => marker.setMap(null))
      categoryMarkersRef.current = []
      
      // 마커 인스턴스 맵 초기화 (선택 상태는 유지)
      markerInstancesRef.current.clear()

      categoryMarkers.forEach((markerData, index) => {
        // 같은 위치의 마커들을 약간씩 오프셋 적용 (겹치지 않도록)
        const offsetAmount = 0.00003 // 약 3미터 정도의 작은 오프셋
        const offset = {
          lat: markerData.position.lat + (Math.random() - 0.5) * offsetAmount,
          lng: markerData.position.lng + (Math.random() - 0.5) * offsetAmount
        }
        
        // 카테고리별 이모티콘 마커 생성
        const categoryIcon = getCategoryIcon(markerData.category)
        const isSelected = selectedMarkerId === markerData.id
        
        const marker = new (window as any).google.maps.Marker({
          position: offset,
          map,
          title: markerData.title || '',
          icon: createMarkerIcon(categoryIcon, isSelected)
        })

        // 마커 인스턴스와 카테고리 정보 저장
        if (markerData.id) {
          markerInstancesRef.current.set(markerData.id, {
            marker: marker,
            category: markerData.category || ''
          })
        }

        // 마커 클릭 이벤트 추가
        marker.addListener('click', () => {
          if (onMarkerClick && markerData.id) {
            // 부모 컴포넌트에만 알리고, 마커 크기 변경은 useEffect에서 처리
            onMarkerClick(markerData.id, markerData.type || 'category', markerData.position)
          }
        })

        categoryMarkersRef.current.push(marker)
      })
    }
  }, [map, categoryMarkers])

  // 부모 컴포넌트에서 선택된 마커 ID 변경 시 처리
  useEffect(() => {
    if (selectedMarkerIdFromParent !== selectedMarkerId) {
      // 이전 선택된 마커를 원래 크기로 되돌리기
      if (selectedMarkerId) {
        const prevMarkerInfo = markerInstancesRef.current.get(selectedMarkerId)
        if (prevMarkerInfo) {
          if (prevMarkerInfo.category === 'itinerary') {
            // 일정 마커인 경우 (빨간색 원)
            prevMarkerInfo.marker.setIcon({
              path: (window as any).google.maps.SymbolPath.CIRCLE,
              scale: 8,
              fillColor: '#FF6B6B',
              fillOpacity: 1,
              strokeColor: '#ffffff',
              strokeWeight: 2
            })
          } else {
            // 카테고리 마커인 경우 (이모티콘)
            const prevIcon = getCategoryIcon(prevMarkerInfo.category)
            prevMarkerInfo.marker.setIcon(createMarkerIcon(prevIcon, false))
          }
        }
      }

      // 새로 선택된 마커를 큰 크기로 변경
      if (selectedMarkerIdFromParent) {
        const newMarkerInfo = markerInstancesRef.current.get(selectedMarkerIdFromParent)
        if (newMarkerInfo) {
          if (newMarkerInfo.category === 'itinerary') {
            // 일정 마커인 경우 (빨간색 원)
            newMarkerInfo.marker.setIcon({
              path: (window as any).google.maps.SymbolPath.CIRCLE,
              scale: 12, // 1.5배 크기
              fillColor: '#FF6B6B',
              fillOpacity: 1,
              strokeColor: '#ffffff',
              strokeWeight: 2
            })
          } else {
            // 카테고리 마커인 경우 (이모티콘)
            const newIcon = getCategoryIcon(newMarkerInfo.category)
            newMarkerInfo.marker.setIcon(createMarkerIcon(newIcon, true))
          }
        }
      }

      setSelectedMarkerId(selectedMarkerIdFromParent)
    }
  }, [selectedMarkerIdFromParent, selectedMarkerId])

  // 지도 영역 조정 (모든 마커가 보이도록) - disableAutoBounds가 false일 때만
  useEffect(() => {
    if (map && markers.length > 0 && !disableAutoBounds) {
      const bounds = new (window as any).google.maps.LatLngBounds()
      markers.forEach(marker => bounds.extend(marker.position))
      map.fitBounds(bounds)
    }
  }, [map, markers, disableAutoBounds])

  // GPS 모드별 위치 추적 (profile에서만 가능)
  useEffect(() => {
    const shouldEnableGPS = source === 'profile' && (gpsMode === 'location' || gpsMode === 'compass')

    if (shouldEnableGPS && map && (window as any).google && 'geolocation' in navigator) {
      // 위치 추적 시작
      const watchId = navigator.geolocation.watchPosition(
        (position) => {
          const newLocation = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
          }

          setUserLocation(newLocation)

          // 기존 사용자 위치 마커 제거
          if (userLocationMarker) {
            userLocationMarker.setMap(null)
          }

          // 새 사용자 위치 마커 생성 (방향 표시 화살표)
          const heading = position.coords.heading // 디바이스가 향하는 방향 (도 단위, 북쪽 기준)
          setCurrentHeading(heading)

          const locationMarker = new (window as any).google.maps.Marker({
            position: newLocation,
            map,
            title: `현재 위치${heading !== null && heading !== undefined ? ` (방향: ${Math.round(heading)}°)` : ''}`,
            icon: {
              path: (window as any).google.maps.SymbolPath.FORWARD_CLOSED_ARROW, // 화살표 모양
              scale: 8,
              fillColor: '#4285F4', // 구글 블루
              fillOpacity: 1,
              strokeColor: '#ffffff',
              strokeWeight: 2,
              rotation: heading !== null && heading !== undefined ? heading : 0 // 방향이 있으면 적용, 없으면 북쪽(0도)
            }
          })

          setUserLocationMarker(locationMarker)

          // 모드별 처리
          if (gpsMode === 'location') {
            // 위치 모드: 지도 회전 없이 위치만 업데이트 (사용자가 지도를 움직일 수 있음)
            // 지도 중심을 강제로 이동시키지 않음
          } else if (gpsMode === 'compass') {
            // 나침반 모드: 위치 중앙 고정 + 지도 회전
            map.panTo(newLocation) // 위치를 중앙에 고정
            if (heading !== null && heading !== undefined) {
              map.setHeading(heading) // 지도를 디바이스 방향에 맞춰 회전
            }
          }
        },
        (error) => {
          console.warn('위치 정보를 가져올 수 없습니다:', error)
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000
        }
      )

      setLocationWatchId(watchId)
    } else {
      // GPS 비활성화 - 기존 위치 추적 중지 및 마커 제거
      if (locationWatchId !== null) {
        navigator.geolocation.clearWatch(locationWatchId)
        setLocationWatchId(null)
      }

      if (userLocationMarker) {
        userLocationMarker.setMap(null)
        setUserLocationMarker(null)
      }

      if (gpsMode === 'off') {
        setUserLocation(null)
      }
    }

    // 컴포넌트 언마운트 시 위치 추적 정리
    return () => {
      if (locationWatchId !== null) {
        navigator.geolocation.clearWatch(locationWatchId)
      }
      if (userLocationMarker) {
        userLocationMarker.setMap(null)
      }
    }
  }, [map, source, gpsMode, userLocationMarker, locationWatchId])

  // 지도 드래그 시 GPS 모드 해제
  useEffect(() => {
    if (!map) return

    const dragListener = map.addListener('drag', () => {
      if (gpsMode !== 'off') {
        setGpsMode('off')
        map.setHeading(0) // 지도 회전 초기화
      }
    })

    return () => {
      if (dragListener) {
        dragListener.remove()
      }
    }
  }, [map, gpsMode])

  // GPS 버튼 클릭 핸들러 - 3단계 모드 (off → location → compass → off)
  const handleGpsButtonClick = () => {
    switch (gpsMode) {
      case 'off':
        // 첫 번째 클릭: 현재 위치로 이동
        setGpsMode('location')
        if (userLocation && map) {
          map.panTo(userLocation)
          map.setZoom(16)
        } else if ('geolocation' in navigator && map) {
          navigator.geolocation.getCurrentPosition(
            (position) => {
              const location = {
                lat: position.coords.latitude,
                lng: position.coords.longitude
              }
              map.panTo(location)
              map.setZoom(16)
            },
            (error) => {
              console.warn('위치 정보를 가져올 수 없습니다:', error)
              alert('위치 정보를 가져올 수 없습니다. GPS를 활성화해주세요.')
              setGpsMode('off')
            },
            {
              enableHighAccuracy: true,
              timeout: 10000,
              maximumAge: 60000
            }
          )
        }
        break

      case 'location':
        // 두 번째 클릭: 나침반 모드 활성화
        setGpsMode('compass')
        if (userLocation && map) {
          map.panTo(userLocation)
          map.setZoom(16)
          // 현재 방향이 있으면 지도 회전
          if (currentHeading !== null && currentHeading !== undefined) {
            map.setHeading(currentHeading)
          }
        }
        break

      case 'compass':
        // 세 번째 클릭: 일반 모드로 복귀
        setGpsMode('off')
        if (map) {
          map.setHeading(0) // 지도 회전 초기화 (북쪽)
        }
        break
    }
  }

  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
  
  if (!apiKey || apiKey === '') {
    return (
      <div className={`bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center ${className}`}>
        <div className="text-center text-white/70">
          <div className="text-6xl mb-4">🗺️</div>
          <p className="text-lg font-medium mb-2">Google Maps API Key가 필요합니다</p>
          <p className="text-sm opacity-75">환경변수를 확인해주세요</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`relative ${className}`}>
      <div
        ref={mapRef}
        style={{ width: '100%', height: '100%' }}
        className="rounded-lg"
      />

      {/* GPS 버튼 - profile에서 온 경우에만 표시 */}
      {source === 'profile' && (
        <button
          onClick={handleGpsButtonClick}
          className={`absolute bottom-4 right-4 w-12 h-12 rounded-full shadow-lg flex items-center justify-center transition-all z-10 border ${
            gpsMode === 'off'
              ? 'bg-white border-gray-200 hover:bg-gray-50'
              : gpsMode === 'location'
              ? 'bg-blue-500 border-blue-600 text-white'
              : 'bg-blue-600 border-blue-700 text-white animate-pulse'
          }`}
          title={
            gpsMode === 'off'
              ? '현재 위치로 이동'
              : gpsMode === 'location'
              ? '나침반 모드 활성화'
              : '나침반 모드 (탭해서 해제)'
          }
        >
          {gpsMode === 'compass' ? (
            // 나침반 모드: 나침반 아이콘
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
              />
            </svg>
          ) : (
            // 기본/위치 모드: 위치 아이콘
            <svg
              className={`w-6 h-6 ${gpsMode === 'off' ? 'text-blue-500' : 'text-white'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          )}
        </button>
      )}

      {!isLoaded && (
        <div className="absolute inset-0 bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center rounded-lg">
          <div className="text-center text-white/70">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
            <p className="text-lg font-medium mb-2">지도 로딩 중...</p>
          </div>
        </div>
      )}
    </div>
  )
})

GoogleMapComponent.displayName = 'GoogleMapComponent'

export default GoogleMapComponent