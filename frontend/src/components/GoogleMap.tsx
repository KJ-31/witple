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
  selectedMarkerIdFromParent = null
}) => {
  const mapRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<any>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const [selectedMarkerId, setSelectedMarkerId] = useState<string | null>(null)
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
        const marker = new (window as any).google.maps.Marker({
          position: markerData.position,
          map,
          title: markerData.title || '',
          icon: {
            path: (window as any).google.maps.SymbolPath.CIRCLE,
            scale: 8,
            fillColor: '#FF6B6B', // 일정 마커는 빨간색
            fillOpacity: 1,
            strokeColor: '#ffffff',
            strokeWeight: 2
          }
        })

        if (markerData.title) {
          const infoWindow = new (window as any).google.maps.InfoWindow({
            content: `<div style="color: #000; font-weight: 500;">${markerData.title}</div>`
          })

          marker.addListener('click', () => {
            infoWindow.open(map, marker)
          })
        }

        itineraryMarkersRef.current.push(marker)
      })
    }
  }, [map, itineraryMarkers])

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
          const prevIcon = getCategoryIcon(prevMarkerInfo.category)
          prevMarkerInfo.marker.setIcon(createMarkerIcon(prevIcon, false))
        }
      }

      // 새로 선택된 마커를 큰 크기로 변경
      if (selectedMarkerIdFromParent) {
        const newMarkerInfo = markerInstancesRef.current.get(selectedMarkerIdFromParent)
        if (newMarkerInfo) {
          const newIcon = getCategoryIcon(newMarkerInfo.category)
          newMarkerInfo.marker.setIcon(createMarkerIcon(newIcon, true))
        }
      }

      setSelectedMarkerId(selectedMarkerIdFromParent)
    }
  }, [selectedMarkerIdFromParent, selectedMarkerId])

  // 지도 영역 조정 (모든 마커가 보이도록)
  useEffect(() => {
    if (map && markers.length > 0) {
      const bounds = new (window as any).google.maps.LatLngBounds()
      markers.forEach(marker => bounds.extend(marker.position))
      map.fitBounds(bounds)
    }
  }, [map, markers])

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
    <div className={className}>
      <div
        ref={mapRef}
        style={{ width: '100%', height: '100%' }}
        className="rounded-lg"
      />
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