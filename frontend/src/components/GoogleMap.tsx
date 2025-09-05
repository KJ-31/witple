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
}

const GoogleMapComponent: React.FC<GoogleMapProps> = memo(({
  className = '',
  center = { lat: 37.5665, lng: 126.9780 },
  zoom = 13,
  markers = []
}) => {
  const mapRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<any>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const markersRef = useRef<any[]>([])

  useEffect(() => {
    const initMap = async () => {
      console.log('All process.env NEXT_PUBLIC_* variables:')
      Object.keys(process.env).filter(key => key.startsWith('NEXT_PUBLIC_')).forEach(key => {
        console.log(`${key}:`, process.env[key])
      })
      
      const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
      
      console.log('Google Maps API Key:', apiKey ? 'Key loaded' : 'Key missing')
      console.log('Raw API Key:', apiKey)
      console.log('API Key type:', typeof apiKey)
      console.log('API Key length:', apiKey?.length)
      
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
            disableDefaultUI: true, // 모든 기본 UI 컨트롤 비활성화
            styles: [
              {
                featureType: 'all',
                elementType: 'geometry',
                stylers: [{ color: '#f5f5f5' }]
              },
              {
                featureType: 'water',
                elementType: 'all',
                stylers: [{ color: '#667eea' }]
              },
              {
                featureType: 'road',
                elementType: 'all',
                stylers: [{ color: '#ffffff' }]
              }
            ]
          })

          setMap(mapInstance)
          setIsLoaded(true)
        }
      } catch (error) {
        console.error('Google Maps 로드 실패:', error)
      }
    }

    initMap()
  }, [center, zoom])

  useEffect(() => {
    if (map && markers.length > 0 && (window as any).google) {
      markersRef.current.forEach(marker => marker.setMap(null))
      markersRef.current = []

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

      if (markers.length > 0) {
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