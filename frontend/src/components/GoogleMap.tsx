'use client'

import React, { useEffect, useRef, useState, memo } from 'react'
import { Loader } from '@googlemaps/js-api-loader'

interface GoogleMapProps {
  className?: string
  center?: { lat: number; lng: number }
  zoom?: number
  markers?: Array<{
    position: { lat: number; lng: number }
    title?: string
    id?: string
  }>
  onMapLoad?: (map: any) => void
}

const GoogleMapComponent: React.FC<GoogleMapProps> = memo(({
  className = '',
  center = { lat: 37.5665, lng: 126.9780 },
  zoom = 13,
  markers = [],
  onMapLoad
}) => {
  const mapRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<any>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const markersRef = useRef<any[]>([])

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

  useEffect(() => {
    if (map && (window as any).google) {
      // 기존 마커 제거
      markersRef.current.forEach(marker => marker.setMap(null))
      markersRef.current = []

      if (markers.length > 0) {
        markers.forEach((markerData) => {
          const marker = new (window as any).google.maps.Marker({
            position: markerData.position,
            map,
            title: markerData.title || '',
            icon: {
              path: (window as any).google.maps.SymbolPath.CIRCLE,
              scale: 8,
              fillColor: '#3E68FF',
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

          markersRef.current.push(marker)
        })

        // 마커들이 있을 때만 bounds 조정
        const bounds = new (window as any).google.maps.LatLngBounds()
        markers.forEach(marker => bounds.extend(marker.position))
        map.fitBounds(bounds)
      }
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