'use client'

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { GoogleMap } from '@/components'

type CategoryKey = 'all' | 'accommodation' | 'humanities' | 'leisure_sports' | 'nature' | 'restaurants' | 'shopping'
interface SelectedPlace {
  id: string
  name: string
  category: string
  rating: number
  description: string
  dayNumber?: number
  address?: string
  region?: string
  imageUrl?: string
  city?: {
    id: string
    name: string
    region: string
  }
  cityName?: string
  isPinned?: boolean
  latitude?: number
  longitude?: number
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

export default function MapPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey>('all')
  const [bottomSheetHeight, setBottomSheetHeight] = useState(320)
  const [isDragging, setIsDragging] = useState(false)
  const [startY, setStartY] = useState(0)
  const [startHeight, setStartHeight] = useState(0)
  const [viewportHeight, setViewportHeight] = useState<number>(0)
  // URL 파라미터 읽기
  const placesParam = searchParams.get('places')
  const dayNumbersParam = searchParams.get('dayNumbers')
  const sourceTablesParam = searchParams.get('sourceTables')
  const startDateParam = searchParams.get('startDate')
  const endDateParam = searchParams.get('endDate')
  const daysParam = searchParams.get('days')
  
  const [selectedItineraryPlaces, setSelectedItineraryPlaces] = useState<SelectedPlace[]>([])
  const [categoryPlaces, setCategoryPlaces] = useState<AttractionData[]>([])
  const [categoryLoading, setCategoryLoading] = useState(false)
  // 일정이 있으면 처음부터 일정을 보여줌
  const [showItinerary, setShowItinerary] = useState(!!placesParam)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [highlightedDay, setHighlightedDay] = useState<number | null>(null)
  const [directionsRenderers, setDirectionsRenderers] = useState<any[]>([])
  const [sequenceMarkers, setSequenceMarkers] = useState<any[]>([])
  const [routeStatus, setRouteStatus] = useState<{message: string, type: 'loading' | 'success' | 'error'} | null>(null)
  const [routeSegments, setRouteSegments] = useState<{
    origin: {lat: number, lng: number, name: string},
    destination: {lat: number, lng: number, name: string},
    distance: string,
    duration: string,
    transitDetails?: any
  }[]>([])
  const [mapInstance, setMapInstance] = useState<any>(null)
  const [draggedItem, setDraggedItem] = useState<{placeId: string, dayNumber: number, index: number} | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<{day: number, index: number} | null>(null)
  const dragRef = useRef<HTMLDivElement>(null)
  
  // Long press 상태
  const [longPressData, setLongPressData] = useState<{
    isLongPressing: boolean,
    isDragging: boolean,
    startY: number,
    currentY: number,
    dragElement: HTMLElement | null,
    clone: HTMLElement | null,
    timeout: NodeJS.Timeout | null,
    preventClick: boolean
  } | null>(null)
  
  // 최적화 확인 모달 상태
  const [optimizeConfirmModal, setOptimizeConfirmModal] = useState<{
    isOpen: boolean,
    dayNumber: number
  }>({ isOpen: false, dayNumber: 0 })
  
  // 삭제 확인 모달 상태
  const [deleteConfirmModal, setDeleteConfirmModal] = useState<{
    isOpen: boolean,
    place: SelectedPlace | null,
    dayNumber: number
  }>({ isOpen: false, place: null, dayNumber: 0 })
  
  // 장소별 잠금 상태 관리
  const [lockedPlaces, setLockedPlaces] = useState<{[key: string]: boolean}>({})
  
  // 잠금 토글 함수
  const toggleLockPlace = (placeId: string, dayNumber: number) => {
    const key = `${placeId}_${dayNumber}`;
    setLockedPlaces(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };
  
  // 드래그 중일 때 body 스크롤 비활성화
  useEffect(() => {
    if (longPressData?.isDragging) {
      document.body.style.overflow = 'hidden';
      document.body.style.position = 'fixed';
      document.body.style.width = '100%';
    } else {
      document.body.style.overflow = '';
      document.body.style.position = '';
      document.body.style.width = '';
    }
    
    return () => {
      document.body.style.overflow = '';
      document.body.style.position = '';
      document.body.style.width = '';
    };
  }, [longPressData?.isDragging]);

  // 화면 높이 측정
  useEffect(() => {
    const updateViewportHeight = () => {
      setViewportHeight(window.innerHeight)
    }
    updateViewportHeight()
    window.addEventListener('resize', updateViewportHeight)
    return () => window.removeEventListener('resize', updateViewportHeight)
  }, [])

  // 바텀 시트 드래그 핸들러
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true)
    setStartY(e.clientY)
    setStartHeight(bottomSheetHeight)
  }

  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches[0]) {
      setIsDragging(true)
      setStartY(e.touches[0].clientY)
      setStartHeight(bottomSheetHeight)
    }
  }

  // 드래그 이벤트 리스너
  useEffect(() => {
    const handleMove = (clientY: number) => {
      if (!isDragging) return
      const diff = startY - clientY
      // 카테고리 바 아래까지만 확장 가능 (상단 120px 남김)
      const maxHeight = viewportHeight - 120
      const newHeight = Math.max(100, Math.min(startHeight + diff, maxHeight))
      setBottomSheetHeight(newHeight)
    }

    const handleMouseMove = (e: MouseEvent) => handleMove(e.clientY)
    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches[0]) handleMove(e.touches[0].clientY)
    }

    const handleUp = () => {
      setIsDragging(false)
      // 스냅 로직
      const maxHeight = viewportHeight - 120
      if (bottomSheetHeight < 200) {
        setBottomSheetHeight(100)
      } else if (bottomSheetHeight > viewportHeight * 0.7) {
        setBottomSheetHeight(Math.min(maxHeight, viewportHeight - 120))
      }
    }

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleUp)
      document.addEventListener('touchmove', handleTouchMove)
      document.addEventListener('touchend', handleUp)
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleUp)
      document.removeEventListener('touchmove', handleTouchMove)
      document.removeEventListener('touchend', handleUp)
    }
  }, [isDragging, startY, startHeight, viewportHeight, bottomSheetHeight])

  // URL 파라미터에서 선택된 장소들 로드
  useEffect(() => {
    const loadSelectedPlaces = async () => {
      if (!placesParam || !dayNumbersParam) {
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        const placeIds = placesParam.split(',')
        const dayNumbers = dayNumbersParam.split(',').map(Number)
        const sourceTables = sourceTablesParam ? sourceTablesParam.split(',') : []
        
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
        const places: SelectedPlace[] = []
        

        for (let i = 0; i < placeIds.length; i++) {
          try {
            let apiUrl
            if (sourceTables[i] && sourceTables[i] !== 'unknown') {
              // ID에서 숫자 부분만 추출 (예: leisure_sports_577 -> 577)
              const numericId = placeIds[i].split('_').pop()
              if (numericId && !isNaN(Number(numericId))) {
                // 새로운 API 사용: /attractions/{table}/{id}
                apiUrl = `${API_BASE_URL}/api/v1/attractions/${sourceTables[i]}/${numericId}`
              } else {
                // 숫자 부분을 추출할 수 없으면 기존 API 사용
                apiUrl = `${API_BASE_URL}/api/v1/attractions/${placeIds[i]}`
              }
            } else {
              // 기존 API 사용: /attractions/{id}
              apiUrl = `${API_BASE_URL}/api/v1/attractions/${placeIds[i]}`
            }
            
            const response = await fetch(apiUrl)
            if (response.ok) {
              const attraction = await response.json()
              places.push({
                ...attraction,
                dayNumber: dayNumbers[i] || 1,
                isPinned: false
              })
            } else {
            }
          } catch (error) {
          }
        }
        
        setSelectedItineraryPlaces(places)
      } catch (error) {
        setError('선택된 장소들을 불러올 수 없습니다.')
      } finally {
        setLoading(false)
      }
    }

    loadSelectedPlaces()
  }, [placesParam, dayNumbersParam, sourceTablesParam])

  // 카테고리별 장소 가져오기
  const fetchPlacesByCategory = useCallback(async (category: CategoryKey) => {
    try {
      setCategoryLoading(true)
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      let url = `${API_BASE_URL}/api/v1/attractions/search?q=&limit=50`
      
      // category 매개변수 대신 검색어로 카테고리 처리
      if (category !== 'all') {
        // 카테고리별 검색어 매핑
        const categorySearchMap: { [key in CategoryKey]: string } = {
          'all': '',
          'nature': '자연',
          'restaurants': '맛집',
          'shopping': '쇼핑',
          'accommodation': '숙박',
          'humanities': '인문',
          'leisure_sports': '레저'
        }
        
        const searchTerm = categorySearchMap[category] || ''
        if (searchTerm) {
          url = `${API_BASE_URL}/api/v1/attractions/search?q=${encodeURIComponent(searchTerm)}&limit=50`
        }
      }
      
      const response = await fetch(url)
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      
      const data = await response.json()
      setCategoryPlaces(data.attractions || [])
    } catch (error) {
      setCategoryPlaces([])
    } finally {
      setCategoryLoading(false)
    }
  }, [])

  // 카테고리 선택 시 장소 가져오기
  useEffect(() => {
    if (!showItinerary) {
      fetchPlacesByCategory(selectedCategory)
    }
  }, [selectedCategory, showItinerary, fetchPlacesByCategory])

  // 초기 로딩 시 전체 장소 가져오기 (일정 보기 모드가 아닐 때만)
  useEffect(() => {
    if (!placesParam) {
      fetchPlacesByCategory('all')
    }
  }, [placesParam, fetchPlacesByCategory])

  // 카테고리 정의
  const categories = [
    { key: 'all' as CategoryKey, name: '전체', icon: '🏠' },
    { key: 'accommodation' as CategoryKey, name: '숙박', icon: '🏨' },
    { key: 'humanities' as CategoryKey, name: '인문', icon: '🏛️' },
    { key: 'leisure_sports' as CategoryKey, name: '레저', icon: '⚽' },
    { key: 'nature' as CategoryKey, name: '자연', icon: '🌿' },
    { key: 'restaurants' as CategoryKey, name: '맛집', icon: '🍽️' },
    { key: 'shopping' as CategoryKey, name: '쇼핑', icon: '🛍️' }
  ]

  // 일정 관리 함수들
  const handleRemoveFromItinerary = (placeId: string, dayNumber: number) => {
    const updatedPlaces = selectedItineraryPlaces.filter(
      place => !(place.id === placeId && place.dayNumber === dayNumber)
    );
    setSelectedItineraryPlaces(updatedPlaces);
    // 삭제시에도 URL 업데이트하지 않음 (기존 선택된 장소들 유지)
    // updateUrlParameters(updatedPlaces);
  };


  const updateUrlParameters = (places: SelectedPlace[]) => {
    if (places.length === 0) {
      router.replace('/map');
      return;
    }
    
    const placeIds = places.map(p => p.id).join(',');
    const dayNumbers = places.map(p => p.dayNumber || 1).join(',');
    const queryParams = new URLSearchParams();
    
    queryParams.set('places', placeIds);
    queryParams.set('dayNumbers', dayNumbers);
    
    if (startDateParam) queryParams.set('startDate', startDateParam);
    if (endDateParam) queryParams.set('endDate', endDateParam);
    if (daysParam) queryParams.set('days', daysParam);
    
    router.replace(`/map?${queryParams.toString()}`);
  };

  // 드래그 앤 드롭 핸들러들
  const handleDragStart = (e: React.DragEvent, place: SelectedPlace, dayNumber: number, index: number) => {
    console.log('드래그 시작:', place.name, 'day:', dayNumber, 'index:', index);
    setDraggedItem({ placeId: place.id, dayNumber, index });
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', place.id);
    // 드래그 시작 시 약간 투명하게
    (e.target as HTMLElement).style.opacity = '0.5';
  };

  // Long press 이벤트 핸들러
  const handleLongPressStart = (e: React.TouchEvent, place: SelectedPlace, dayNumber: number, index: number) => {
    // 버튼에서는 long press 실행하지 않음 (휴지통 버튼만 제외)
    const target = e.target as HTMLElement;
    if (target.closest('button')) {
      return;
    }
    
    const touch = e.touches[0];
    const element = e.currentTarget as HTMLElement;
    const cardElement = element;

    // Long press 타이머 시작
    const timeout = setTimeout(() => {
      // Long press 확인됨 - 햅틱 피드백 추가
      if (navigator.vibrate) {
        navigator.vibrate(50);
      }
      
      const rect = cardElement.getBoundingClientRect();
      
      // 카드 복사본 생성
      const clone = cardElement.cloneNode(true) as HTMLElement;
      clone.style.position = 'fixed';
      clone.style.zIndex = '9999';
      clone.style.opacity = '0.8';
      clone.style.width = rect.width + 'px';
      clone.style.height = rect.height + 'px';
      clone.style.left = rect.left + 'px';
      clone.style.top = rect.top + 'px';
      clone.style.pointerEvents = 'none';
      clone.style.transform = 'rotate(2deg) scale(1.05)';
      clone.style.boxShadow = '0 15px 35px rgba(62, 104, 255, 0.4)';
      clone.style.border = '2px solid #3E68FF';
      document.body.appendChild(clone);
      
      setDraggedItem({ placeId: place.id, dayNumber, index });
      setLongPressData(prev => ({
        isLongPressing: true,
        isDragging: true,
        startY: touch.clientY,
        currentY: touch.clientY,
        dragElement: cardElement,
        clone,
        timeout: null,
        preventClick: true
      }));
      
      // 원본 요소 스타일 변경 - long press 시각 피드백
      cardElement.style.opacity = '0.3';
      cardElement.style.transform = 'scale(0.95)';
      cardElement.style.transition = 'all 0.2s ease';
    }, 400); // 400ms long press로 단축

    setLongPressData({
      isLongPressing: false,
      isDragging: false,
      startY: touch.clientY,
      currentY: touch.clientY,
      dragElement: cardElement,
      clone: null,
      timeout,
      preventClick: false
    });
  };
  
  const handleLongPressMove = (e: React.TouchEvent) => {
    if (!longPressData) return;
    
    const touch = e.touches[0];
    const moveThreshold = 10; // 10px 이동하면 long press 취소
    
    if (!longPressData.isDragging) {
      // Long press 대기 중 - 너무 많이 움직이면 취소
      const deltaY = Math.abs(touch.clientY - longPressData.startY);
      if (deltaY > moveThreshold && longPressData.timeout) {
        clearTimeout(longPressData.timeout);
        setLongPressData(null);
        return;
      }
    } else {
      // 드래그 중
      if (!longPressData.clone) return;
      
      const deltaY = touch.clientY - longPressData.startY;
      const originalRect = longPressData.dragElement!.getBoundingClientRect();
      longPressData.clone.style.left = originalRect.left + 'px';
      longPressData.clone.style.top = (originalRect.top + deltaY) + 'px';
      
      setLongPressData(prev => prev ? {
        ...prev,
        currentY: touch.clientY
      } : null);
      
      // 드롭 존 감지
      const dropZones = document.querySelectorAll('[data-drop-zone]');
      let targetFound = false;
      
      dropZones.forEach(zone => {
        const zoneRect = zone.getBoundingClientRect();
        if (touch.clientY >= zoneRect.top && touch.clientY <= zoneRect.bottom) {
          const dayNumber = parseInt(zone.getAttribute('data-day') || '0');
          const index = parseInt(zone.getAttribute('data-index') || '0');
          setDragOverIndex({ day: dayNumber, index });
          targetFound = true;
        }
      });
      
      if (!targetFound) {
        setDragOverIndex(null);
      }
    }
  };
  
  const handleLongPressEnd = (e: React.TouchEvent) => {
    if (!longPressData) return;
    
    // Long press 타이머 정리
    if (longPressData.timeout) {
      clearTimeout(longPressData.timeout);
    }
    
    // 복사본 제거
    if (longPressData.clone) {
      document.body.removeChild(longPressData.clone);
    }
    
    // 원본 요소 스타일 복원
    if (longPressData.dragElement) {
      longPressData.dragElement.style.opacity = '1';
      longPressData.dragElement.style.transform = '';
      longPressData.dragElement.style.transition = '';
    }
    
    // 드래그가 진행되었다면 드롭 처리
    if (longPressData.isDragging && dragOverIndex && draggedItem) {
      console.log('Long press 드롭:', dragOverIndex, draggedItem);
      const fakeEvent = {
        preventDefault: () => {},
        dataTransfer: { dropEffect: 'move' }
      } as React.DragEvent;
      handleDrop(fakeEvent, dragOverIndex.index, dragOverIndex.day);
    }
    
    // preventClick을 잠시 유지한 후 초기화 (클릭 이벤트 방지)
    setTimeout(() => {
      setLongPressData(null);
    }, 100);
    
    setDraggedItem(null);
    setDragOverIndex(null);
  };
  
  

  const handleDragEnd = (e: React.DragEvent) => {
    (e.target as HTMLElement).style.opacity = '1';
    setDraggedItem(null);
    setDragOverIndex(null);
  };

  const handleDragOver = (e: React.DragEvent, index: number, dayNumber: number) => {
    e.preventDefault();
    
    // 모든 일차에서 드래그 오버 허용
    if (draggedItem) {
      e.dataTransfer.dropEffect = 'move';
      setDragOverIndex({ day: dayNumber, index: index });
    } else {
      e.dataTransfer.dropEffect = 'none';
      setDragOverIndex(null);
    }
  };

  const handleDragLeave = () => {
    setDragOverIndex(null);
  };

  const handleDrop = (e: React.DragEvent, targetIndex: number, targetDayNumber: number) => {
    e.preventDefault();
    console.log('드롭 이벤트:', targetIndex, targetDayNumber, draggedItem);
    
    if (!draggedItem) {
      console.log('draggedItem이 없음');
      return;
    }
    
    // 같은 위치로 이동하는 경우 무시
    if (draggedItem.dayNumber === targetDayNumber && draggedItem.index === targetIndex) {
      console.log('같은 위치로 이동, 무시');
      return;
    }

    console.log('장소 이동 실행:', `day${draggedItem.dayNumber}[${draggedItem.index}] -> day${targetDayNumber}[${targetIndex}]`);

    // 드래그한 장소를 새 위치로 이동
    setSelectedItineraryPlaces(prev => {
      const result = [...prev];
      
      // 드래그한 아이템 찾기
      const draggedItemIndex = result.findIndex(p => p.id === draggedItem.placeId && p.dayNumber === draggedItem.dayNumber);
      if (draggedItemIndex === -1) return prev;
      
      // 드래그한 아이템 제거
      const [movedItem] = result.splice(draggedItemIndex, 1);
      console.log('이동할 아이템:', movedItem?.name);
      
      // 날짜 변경
      movedItem.dayNumber = targetDayNumber;
      
      // 목적지 날짜의 장소들만 필터링
      const targetDayPlaces = result.filter(p => p.dayNumber === targetDayNumber);
      const otherDayPlaces = result.filter(p => p.dayNumber !== targetDayNumber);
      
      // 새 위치에 삽입 (목적지 날짜의 인덱스 기준)
      targetDayPlaces.splice(targetIndex, 0, movedItem);
      
      const finalResult = [...otherDayPlaces, ...targetDayPlaces];
      console.log('최종 결과:', finalResult.map(p => `${p.name}(day:${p.dayNumber})`));
      
      return finalResult;
    });

    setDraggedItem(null);
    setDragOverIndex(null);
  };

  // 위아래 순서 변경 함수 (드래그로 대체되지만 일단 유지)
  const movePlace = (placeId: string, direction: 'up' | 'down') => {
    setSelectedItineraryPlaces(prev => {
      const currentPlace = prev.find(p => p.id === placeId)
      if (!currentPlace) return prev
      
      // 같은 날짜의 장소들만 필터링
      const sameDayPlaces = prev.filter(p => p.dayNumber === currentPlace.dayNumber)
      const otherDayPlaces = prev.filter(p => p.dayNumber !== currentPlace.dayNumber)
      
      // 현재 장소의 인덱스 찾기
      const currentIndex = sameDayPlaces.findIndex(p => p.id === placeId)
      if (currentIndex === -1) return prev
      
      // 이동할 새 인덱스 계산
      let newIndex = currentIndex
      if (direction === 'up' && currentIndex > 0) {
        newIndex = currentIndex - 1
      } else if (direction === 'down' && currentIndex < sameDayPlaces.length - 1) {
        newIndex = currentIndex + 1
      } else {
        return prev // 이동할 수 없는 경우
      }
      
      // 배열에서 현재 장소 제거하고 새 위치에 삽입
      const updatedSameDayPlaces = [...sameDayPlaces]
      const [movedPlace] = updatedSameDayPlaces.splice(currentIndex, 1)
      updatedSameDayPlaces.splice(newIndex, 0, movedPlace)
      
      // 전체 배열 재구성
      const result = [...otherDayPlaces, ...updatedSameDayPlaces]
      const sortedResult = result.sort((a, b) => {
        if ((a.dayNumber || 0) !== (b.dayNumber || 0)) {
          return (a.dayNumber || 0) - (b.dayNumber || 0)
        }
        // 같은 날짜 내에서는 업데이트된 순서 유지
        if (a.dayNumber === currentPlace.dayNumber) {
          const aIndex = updatedSameDayPlaces.findIndex(p => p.id === a.id)
          const bIndex = updatedSameDayPlaces.findIndex(p => p.id === b.id)
          return aIndex - bIndex
        }
        return 0
      })
      
      // 업데이트된 결과로 URL 파라미터 즉시 업데이트
      setTimeout(() => {
        updateUrlParameters(sortedResult)
      }, 0)
      
      return sortedResult
    })
  };

  // 지도 인스턴스 설정을 useCallback으로 메모화
  const handleMapLoad = useCallback((mapInstanceParam: any) => {
    setMapInstance(mapInstanceParam)
  }, [])

  // 지도 마커 데이터 생성
  const mapMarkers = useMemo(() => {
    if (showItinerary && selectedItineraryPlaces.length > 0) {
      return selectedItineraryPlaces
        .filter(place => place.latitude && place.longitude)
        .map(place => ({
          position: { lat: place.latitude!, lng: place.longitude! },
          title: place.name,
          id: place.id
        }))
    } else if (!showItinerary && categoryPlaces.length > 0) {
      return categoryPlaces
        .filter(place => place.latitude && place.longitude)
        .map(place => ({
          position: { lat: place.latitude!, lng: place.longitude! },
          title: place.name,
          id: place.id
        }))
    }
    return []
  }, [showItinerary, selectedItineraryPlaces, categoryPlaces])

  // 유틸리티 함수
  const handleBack = () => router.back()
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
  }
  const isFullScreen = bottomSheetHeight >= (viewportHeight || 0) - 2

  const getCategoryName = (category: string): string => {
    const categoryMap: { [key: string]: string } = {
      restaurants: '맛집',
      humanities: '인문',
      nature: '자연',
      shopping: '쇼핑',
      accommodation: '숙박',
      leisure_sports: '레저'
    }
    return categoryMap[category] || category
  }

  // 하버사인 공식으로 두 좌표간 거리 계산 (km)
  const calculateDistance = (lat1: number, lng1: number, lat2: number, lng2: number): number => {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  };

  // 좌표 변환 함수
  const getCoordinates = async (placeName: string): Promise<{lat: number, lng: number}> => {
    // 먼저 selectedItineraryPlaces에서 해당 장소의 좌표를 찾기
    const place = selectedItineraryPlaces.find(p => p.name === placeName);
    if (place && place.latitude && place.longitude) {
      return { lat: place.latitude, lng: place.longitude };
    }
    
    // 좌표가 없다면 Geocoding API 사용 (구글 맵이 로드된 후)
    if ((window as any).google?.maps?.Geocoder) {
      const geocoder = new (window as any).google.maps.Geocoder();
      return new Promise((resolve, reject) => {
        geocoder.geocode({ address: placeName }, (results: any, status: any) => {
          if (status === 'OK' && results[0]) {
            resolve({
              lat: results[0].geometry.location.lat(),
              lng: results[0].geometry.location.lng()
            });
          } else {
            reject(new Error(`Geocoding failed: ${status}`));
          }
        });
      });
    }
    
    throw new Error('Coordinates not available');
  };

  // 최적화된 경로 계산 (제약 조건 포함)
  const optimizeRouteOrderWithConstraints = (
    origin: {lat: number, lng: number}, 
    destinations: {lat: number, lng: number}[], 
    destinationNames: string[], 
    constraints: { locked: boolean; order?: number }[]
  ): {
    order: number[],
    totalDistance: number,
    optimizedNames: string[]
  } => {
    if (destinations.length === 0) return { order: [], totalDistance: 0, optimizedNames: [] };
    
    // 최종 결과 배열을 미리 생성 (잠금된 위치는 고정)
    const finalOrder = new Array(destinations.length).fill(-1);
    const finalNames = new Array(destinations.length).fill('');
    const visited = new Array(destinations.length).fill(false);
    
    // 1. 잠금된 장소들을 먼저 고정된 위치에 배치
    constraints.forEach((constraint, index) => {
      if (constraint.locked && constraint.order !== undefined) {
        const fixedPosition = constraint.order - 1; // order는 1부터 시작하므로 -1
        if (fixedPosition >= 0 && fixedPosition < destinations.length) {
          finalOrder[fixedPosition] = index;
          finalNames[fixedPosition] = destinationNames[index];
          visited[index] = true;
        }
      }
    });
    
    // 2. 잠금되지 않은 장소들을 가장 가까운 거리 순으로 배치
    const unlockedIndices = [];
    for (let i = 0; i < destinations.length; i++) {
      if (!visited[i]) {
        unlockedIndices.push(i);
      }
    }
    
    // 3. 빈 슬롯들을 찾기
    const emptySlots = [];
    for (let i = 0; i < finalOrder.length; i++) {
      if (finalOrder[i] === -1) {
        emptySlots.push(i);
      }
    }
    
    // 4. 최적화: 각 빈 슬롯에 대해 가장 적합한 장소 배치
    let currentLocation = origin;
    let totalDistance = 0;
    
    // 순서대로 처리하면서 거리 계산
    for (let slotIndex = 0; slotIndex < emptySlots.length; slotIndex++) {
      const slot = emptySlots[slotIndex];
      
      // 이전 위치까지의 경로를 따라 현재 위치 업데이트
      if (slot > 0) {
        const prevIndex = finalOrder[slot - 1];
        if (prevIndex !== -1) {
          currentLocation = destinations[prevIndex];
        }
      }
      
      // 가장 가까운 미방문 장소 찾기
      let nearestIndex = -1;
      let nearestDistance = Infinity;
      
      for (const unlockedIndex of unlockedIndices) {
        if (!visited[unlockedIndex]) {
          const distance = calculateDistance(
            currentLocation.lat, currentLocation.lng,
            destinations[unlockedIndex].lat, destinations[unlockedIndex].lng
          );
          
          if (distance < nearestDistance) {
            nearestDistance = distance;
            nearestIndex = unlockedIndex;
          }
        }
      }
      
      // 가장 가까운 장소를 현재 슬롯에 배치
      if (nearestIndex !== -1) {
        finalOrder[slot] = nearestIndex;
        finalNames[slot] = destinationNames[nearestIndex];
        visited[nearestIndex] = true;
        totalDistance += nearestDistance;
        currentLocation = destinations[nearestIndex];
      }
    }
    
    // 전체 거리 재계산
    totalDistance = 0;
    let prevLocation = origin;
    for (let i = 0; i < finalOrder.length; i++) {
      const index = finalOrder[i];
      if (index !== -1) {
        const distance = calculateDistance(
          prevLocation.lat, prevLocation.lng,
          destinations[index].lat, destinations[index].lng
        );
        totalDistance += distance;
        prevLocation = destinations[index];
      }
    }

    console.log('제약 조건 최적화 결과:', {
      finalOrder,
      finalNames,
      constraints,
      totalDistance
    });

    return { 
      order: finalOrder.filter(index => index !== -1), 
      totalDistance, 
      optimizedNames: finalNames.filter(name => name !== '')
    };
  };

  // 간단한 최적화 (제약 조건 없음)
  const optimizeRouteOrder = (origin: {lat: number, lng: number}, destinations: {lat: number, lng: number}[], destinationNames: string[]): {
    order: number[],
    totalDistance: number,
    optimizedNames: string[]
  } => {
    const constraints = destinations.map(() => ({ locked: false }));
    return optimizeRouteOrderWithConstraints(origin, destinations, destinationNames, constraints);
  };

  // 상태 업데이트 함수
  const updateStatus = (message: string, type: 'loading' | 'success' | 'error') => {
    setRouteStatus({ message, type });
    setTimeout(() => setRouteStatus(null), 3000);
  };

  // 기존 경로 제거
  const clearRoute = () => {
    // 모든 기존 경로 렌더러 제거
    directionsRenderers.forEach(renderer => {
      if (renderer) {
        renderer.setMap(null);
        renderer.setDirections(null);
      }
    });
    setDirectionsRenderers([]);
    
    // 모든 기존 마커 제거
    sequenceMarkers.forEach(marker => {
      if (marker) {
        marker.setMap(null);
      }
    });
    setSequenceMarkers([]);
    
    // 상태 메시지 제거
    setRouteStatus(null);
    
    // 경로 구간 정보 초기화
    setRouteSegments([]);
    

    console.log('모든 경로와 마커가 제거되었습니다');
  };

  // 특정 일차와 구간에 해당하는 경로 정보 가져오기
  const getRouteSegmentInfo = (dayNumber: number, fromPlaceId: string, toPlaceId: string) => {
    return routeSegments.find(segment => {
      // 일차별 장소들에서 해당 구간 찾기
      const dayPlaces = selectedItineraryPlaces.filter(place => place.dayNumber === dayNumber);
      const fromIndex = dayPlaces.findIndex(place => place.id === fromPlaceId);
      const toIndex = dayPlaces.findIndex(place => place.id === toPlaceId);
      
      return segment.origin.name === dayPlaces[fromIndex]?.name && 
             segment.destination.name === dayPlaces[toIndex]?.name;
    });
  };


  // 순서 마커 생성 (START, 1, 2, 3, END)
  const createSequenceMarkers = async (segments: {origin: {lat: number, lng: number, name: string}, destination: {lat: number, lng: number, name: string}}[], isOptimized: boolean = false) => {
    sequenceMarkers.forEach(marker => marker.setMap(null));
    
    const newSequenceMarkers = [];
    const allPoints = [segments[0].origin, ...segments.map(s => s.destination)];
    
    for (let i = 0; i < allPoints.length; i++) {
      try {
        const coords = { lat: allPoints[i].lat, lng: allPoints[i].lng };
        
        const markerLabel = i === 0 ? 'START' : 
                           i === allPoints.length - 1 ? 'END' : 
                           i.toString();
        
        const markerColor = i === 0 ? '#4CAF50' : 
                           i === allPoints.length - 1 ? '#F44336' : 
                           isOptimized ? '#FF9800' : '#2196F3'; // 최적화된 경로는 주황색
        
        const marker = new (window as any).google.maps.Marker({
          position: coords,
          map: mapInstance,
          icon: {
            url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
              <svg xmlns="http://www.w3.org/2000/svg" width="30" height="40" viewBox="0 0 30 40">
                <path d="M15 0C6.7 0 0 6.7 0 15c0 8.3 15 25 15 25s15-16.7 15-25C30 6.7 23.3 0 15 0z" fill="${markerColor}" stroke="white" stroke-width="2"/>
                <text x="15" y="20" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" font-weight="bold" fill="white">${markerLabel}</text>
              </svg>
            `)}`,
            scaledSize: new (window as any).google.maps.Size(30, 40),
            anchor: new (window as any).google.maps.Point(15, 40)
          },
          title: `${i === 0 ? '출발지' : i === allPoints.length - 1 ? '목적지' : `${i}번째 경유지`}: ${allPoints[i].name}`,
          zIndex: 1000
        });

        const infoWindow = new (window as any).google.maps.InfoWindow({
          content: `
            <div style="padding: 10px; text-align: center;">
              <h4 style="margin: 0 0 5px 0; color: ${markerColor};">
                ${i === 0 ? '🚩 출발지' : i === allPoints.length - 1 ? '🏁 목적지' : `📍 ${i}번째 경유지`}
              </h4>
              <p style="margin: 0; font-weight: bold;">${allPoints[i].name}</p>
              <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">
                ${i === 0 ? '여행의 시작점입니다' : 
                  i === allPoints.length - 1 ? '최종 목적지입니다' : 
                  `${i === 1 ? '첫 번째' : i === 2 ? '두 번째' : i === 3 ? '세 번째' : `${i}번째`} 방문할 장소입니다`}
              </p>
              ${isOptimized && i > 0 && i < allPoints.length - 1 ? '<p style="margin: 5px 0 0 0; font-size: 10px; color: #FF9800; font-weight: bold;">🔄 최적화된 순서</p>' : ''}
            </div>
          `
        });

        marker.addListener('click', () => {
          infoWindow.open(mapInstance, marker);
        });

        newSequenceMarkers.push(marker);
      } catch (error) {
        console.error(`순서 마커 생성 실패: ${allPoints[i].name}`, error);
      }
    }
    
    setSequenceMarkers(newSequenceMarkers);
  };

  // 기본 동선 렌더링 (순서대로)
  const renderBasicRoute = async (dayNumber: number) => {
    const dayPlaces = selectedItineraryPlaces.filter(place => place.dayNumber === dayNumber);
    
    if (dayPlaces.length < 2) {
      updateStatus(`${dayNumber}일차에 경로를 계획할 장소가 충분하지 않습니다 (최소 2개 필요)`, 'error');
      return;
    }

    try {
      // 먼저 모든 기존 경로와 마커 완전히 제거
      clearRoute();
      // 잠깐 기다려서 이전 렌더링이 완전히 정리되도록 함
      await new Promise(resolve => setTimeout(resolve, 100));
      
      updateStatus(`${dayNumber}일차 기본 동선 표시 중...`, 'loading');

      // 순서대로 경로 구간 생성
      const segments = [];
      for (let i = 0; i < dayPlaces.length - 1; i++) {
        const current = dayPlaces[i];
        const next = dayPlaces[i + 1];
        
        if (!current.latitude || !current.longitude || !next.latitude || !next.longitude) {
          continue;
        }
        
        segments.push({
          origin: { 
            lat: current.latitude, 
            lng: current.longitude, 
            name: current.name 
          },
          destination: { 
            lat: next.latitude, 
            lng: next.longitude, 
            name: next.name 
          }
        });
      }

      if (segments.length === 0) {
        updateStatus('좌표 정보가 없어서 경로를 표시할 수 없습니다', 'error');
        return;
      }

      console.log(`${dayNumber}일차 기본 동선:`, segments);
      await renderRoute(segments, false); // 기본 동선

    } catch (error) {
      console.error(`${dayNumber}일차 Basic route error:`, error);
      updateStatus(`${dayNumber}일차 기본 동선 표시 중 오류가 발생했습니다.`, 'error');
    }
  };

  // 경로 렌더링 (기본 동선 또는 최적화 경로)
  const renderRoute = async (segments: {origin: {lat: number, lng: number, name: string}, destination: {lat: number, lng: number, name: string}}[], isOptimized: boolean = false) => {
    if (!(window as any).google?.maps?.DirectionsService) {
      console.error('Google Maps DirectionsService not available');
      return;
    }

    const directionsService = new (window as any).google.maps.DirectionsService();

    let allResults = [];
    let totalDistance = 0;
    let totalDuration = 0;
    let segmentDetails = [];

    try {
      for (let i = 0; i < segments.length; i++) {
        const segment = segments[i];
        
        const request = {
          origin: { lat: segment.origin.lat, lng: segment.origin.lng },
          destination: { lat: segment.destination.lat, lng: segment.destination.lng },
          waypoints: [],
          travelMode: (window as any).google.maps.TravelMode.TRANSIT,
          region: 'KR',
          language: 'ko'
        };

        const result = await new Promise<any>((resolve, reject) => {
          directionsService.route(request, (result: any, status: any) => {
            console.log(`${segment.origin.name} -> ${segment.destination.name}:`, status);
            if (status === 'OK' && result) {
              resolve(result);
            } else {
              reject(new Error(`Directions failed: ${status}`));
            }
          });
        });

        allResults.push(result);
        
        const leg = result.routes[0].legs[0];
        const distance = leg.distance?.value || 0;
        const duration = leg.duration?.value || 0;
        
        totalDistance += distance;
        totalDuration += duration;

        // 구간 정보 저장
        segmentDetails.push({
          origin: segment.origin,
          destination: segment.destination,
          distance: leg.distance?.text || '알 수 없음',
          duration: leg.duration?.text || '알 수 없음',
          transitDetails: leg.steps?.map((step: any) => ({
            instruction: step.instructions?.replace(/<[^>]*>/g, ''), // HTML 태그 제거
            mode: step.travel_mode,
            distance: step.distance?.text,
            duration: step.duration?.text,
            transitDetails: step.transit ? {
              line: step.transit.line?.name,
              vehicle: step.transit.line?.vehicle?.name,
              departure_stop: step.transit.departure_stop?.name,
              arrival_stop: step.transit.arrival_stop?.name,
              departure_time: step.transit.departure_time?.text,
              arrival_time: step.transit.arrival_time?.text
            } : null
          }))
        });
      }
    } catch (err) {
      console.log('경로 계산 실패:', err);
      throw err;
    }

    if (allResults.length === 0) {
      throw new Error('경로를 찾을 수 없습니다.');
    }

    const newRenderers = [];

    for (let i = 0; i < allResults.length; i++) {
      const result = allResults[i];
      
      const renderer = new (window as any).google.maps.DirectionsRenderer({
        draggable: false,
        polylineOptions: {
          strokeColor: isOptimized ? '#FF9800' : '#34A853', // 최적화는 주황색, 기본은 초록색
          strokeWeight: 6,
          strokeOpacity: 0.8
        },
        suppressMarkers: i > 0,
        preserveViewport: i > 0
      });

      renderer.setDirections(result);
      if (mapInstance) {
        renderer.setMap(mapInstance);
      }
      newRenderers.push(renderer);
    }

    setDirectionsRenderers(newRenderers);
    await createSequenceMarkers(segments, isOptimized);

    // 구간 정보를 상태에 저장
    setRouteSegments(segmentDetails);

    const distanceText = totalDistance > 0 ? `${(totalDistance / 1000).toFixed(1)}km` : '알 수 없음';
    const durationText = totalDuration > 0 ? `${Math.round(totalDuration / 60)}분` : '알 수 없음';
    
    const routeTypeText = isOptimized ? '최적화된 경로!' : '기본 동선 표시 완료!';
    updateStatus(
      `${routeTypeText} (${segments.length}개 구간) - 총 거리: ${distanceText}, 총 시간: ${durationText}`,
      'success'
    );
  };

  // UI에서 장소 순서를 최적화된 순서로 변경
  const updatePlacesOrder = (dayNumber: number, optimizedPlaces: SelectedPlace[]) => {
    setSelectedItineraryPlaces(prev => {
      // 다른 날짜의 장소들
      const otherDayPlaces = prev.filter(p => p.dayNumber !== dayNumber);
      
      // 최적화된 장소들과 다른 날짜 장소들을 합쳐서 반환
      const result = [...otherDayPlaces, ...optimizedPlaces];
      
      // 날짜순으로 정렬
      return result.sort((a, b) => {
        if ((a.dayNumber || 0) !== (b.dayNumber || 0)) {
          return (a.dayNumber || 0) - (b.dayNumber || 0);
        }
        return 0;
      });
    });
  };

  // 최적화 확인 모달 열기
  const openOptimizeConfirm = (dayNumber: number) => {
    setOptimizeConfirmModal({ isOpen: true, dayNumber });
  };

  // 최적화 확인 모달 닫기
  const closeOptimizeConfirm = () => {
    setOptimizeConfirmModal({ isOpen: false, dayNumber: 0 });
  };

  // 삭제 확인 모달 열기
  const openDeleteConfirm = (place: SelectedPlace, dayNumber: number) => {
    setDeleteConfirmModal({ isOpen: true, place, dayNumber });
  };

  // 삭제 확인 모달 닫기
  const closeDeleteConfirm = () => {
    setDeleteConfirmModal({ isOpen: false, place: null, dayNumber: 0 });
  };

  // 실제 삭제 실행
  const confirmDelete = () => {
    if (deleteConfirmModal.place) {
      handleRemoveFromItinerary(deleteConfirmModal.place.id, deleteConfirmModal.dayNumber);
      closeDeleteConfirm();
    }
  };

  // 일차별 경로 최적화 실행 (제약 조건 포함)
  const optimizeRouteForDay = async (dayNumber: number) => {
    const dayPlaces = selectedItineraryPlaces.filter(place => place.dayNumber === dayNumber);
    
    if (dayPlaces.length < 2) {
      updateStatus(`${dayNumber}일차에 경로를 계획할 장소가 충분하지 않습니다 (최소 2개 필요)`, 'error');
      return;
    }

    try {
      // 먼저 모든 기존 경로와 마커 완전히 제거
      clearRoute();
      // 잠깐 기다려서 이전 렌더링이 완전히 정리되도록 함
      await new Promise(resolve => setTimeout(resolve, 100));
      
      updateStatus(`${dayNumber}일차 경로 최적화 중...`, 'loading');

      // 첫 번째 장소를 출발지로, 나머지를 목적지로 설정
      const [firstPlace, ...restPlaces] = dayPlaces;
      
      if (!firstPlace.latitude || !firstPlace.longitude) {
        updateStatus('출발지의 좌표 정보가 없습니다', 'error');
        return;
      }

      const originCoords = { lat: firstPlace.latitude, lng: firstPlace.longitude };
      const destinationCoords = restPlaces
        .filter(place => place.latitude && place.longitude)
        .map(place => ({ lat: place.latitude!, lng: place.longitude! }));
      const destinationNames = restPlaces
        .filter(place => place.latitude && place.longitude)
        .map(place => place.name);

      if (destinationCoords.length === 0) {
        updateStatus('경유지의 좌표 정보가 없습니다', 'error');
        return;
      }

      // 잠금 제약 조건 생성 (현재 순서 기준)
      const constraints = restPlaces
        .filter(place => place.latitude && place.longitude)
        .map((place, index) => {
          const key = `${place.id}_${dayNumber}`;
          const isLocked = lockedPlaces[key] || false;
          return {
            locked: isLocked,
            order: isLocked ? index + 1 : undefined // 잠금된 경우 현재 순서를 유지 (첫번째 장소 제외하고 1부터 시작)
          };
        });

      const lockedCount = constraints.filter(c => c.locked).length;

      console.log(`${dayNumber}일차 최적화 시작:`, {
        origin: firstPlace.name,
        destinations: destinationNames,
        constraints: constraints,
        lockedCount: lockedCount,
        lockedPlaces: lockedPlaces
      });

      // 제약 조건이 있는 최적화 실행
      const optimized = optimizeRouteOrderWithConstraints(originCoords, destinationCoords, destinationNames, constraints);
      
      console.log(`${dayNumber}일차 최적화된 순서:`, optimized.optimizedNames);
      console.log(`${dayNumber}일차 예상 총 거리:`, optimized.totalDistance.toFixed(1), 'km');

      updateStatus(`${dayNumber}일차 경로 최적화 완료! (${lockedCount}개 순서 고정) 예상 거리: ${optimized.totalDistance.toFixed(1)}km. 실제 경로를 계산 중...`, 'loading');

      // 최적화된 순서대로 장소 객체 재구성
      const optimizedPlaces = [firstPlace];
      for (const name of optimized.optimizedNames) {
        const place = restPlaces.find(p => p.name === name);
        if (place) optimizedPlaces.push(place);
      }

      // UI에서 장소 순서 업데이트
      updatePlacesOrder(dayNumber, optimizedPlaces);

      const segments = [];
      for (let i = 0; i < optimizedPlaces.length - 1; i++) {
        const current = optimizedPlaces[i];
        const next = optimizedPlaces[i + 1];
        segments.push({
          origin: { 
            lat: current.latitude!, 
            lng: current.longitude!, 
            name: current.name 
          },
          destination: { 
            lat: next.latitude!, 
            lng: next.longitude!, 
            name: next.name 
          }
        });
      }

      console.log(`${dayNumber}일차 최적화된 경로 구간:`, segments);
      await renderRoute(segments, true);

    } catch (error) {
      console.error(`${dayNumber}일차 Route optimization error:`, error);
      updateStatus(
        `${dayNumber}일차 경로 최적화 중 오류가 발생했습니다.`, 
        'error'
      );
    }
  };

  // 로딩 상태
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF] mx-auto mb-4"></div>
          <p className="text-[#94A9C9]">지도를 준비하는 중...</p>
        </div>
      </div>
    )
  }

  // 에러 상태
  if (error) {
    return (
      <div className="min-h-screen bg-[#0B1220] text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-[#94A9C9] text-lg mb-4">{error}</p>
          <button 
            onClick={() => router.back()}
            className="text-[#3E68FF] hover:text-[#6FA0E6] transition-colors"
          >
            돌아가기
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-white relative">
      {/* Header Back */}
      <div className="absolute top-4 left-4 z-50">
        <button
          onClick={handleBack}
          className="p-2 bg-black/30 rounded-full backdrop-blur-sm hover:bg-black/50 transition-colors"
        >
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Search Bar */}
      <div className="absolute top-4 left-16 right-4 z-40">
        <form onSubmit={handleSearch} className="relative">
          <div className="relative">
            <input
              type="text"
              placeholder="장소나 도시를 검색하세요"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 pr-12 py-3 text-sm rounded-2xl bg-black/30 backdrop-blur-sm text-white placeholder-gray-300 ring-1 ring-white/20 focus:outline-none focus:ring-2 focus:ring-[#3E68FF]/60"
            />
            <button
              type="submit"
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-300 hover:text-white transition"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
          </div>
        </form>
      </div>

      {/* Category Filter */}
      <div className="absolute top-20 left-4 right-4 z-40">
        <div className="flex space-x-2 overflow-x-auto no-scrollbar">
          {categories.map(category => (
            <button
              key={category.key}
              onClick={() => {
                setSelectedCategory(category.key)
                setShowItinerary(false)
              }}
              className={`flex-shrink-0 px-3 py-2 rounded-full text-xs font-medium transition-all duration-200 flex items-center space-x-1 backdrop-blur-sm ${
                selectedCategory === category.key
                  ? 'bg-[#3E68FF] text-white shadow-lg'
                  : 'bg-black/30 text-gray-300 hover:text-white hover:bg-black/50'
              }`}
            >
              <span>{category.icon}</span>
              <span>{category.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Route Status Toast */}
      {routeStatus && (
        <div className={`absolute top-32 left-4 right-4 z-50 p-3 rounded-lg backdrop-blur-sm transition-all duration-300 ${
          routeStatus.type === 'loading' ? 'bg-blue-900/80 text-blue-100' :
          routeStatus.type === 'success' ? 'bg-green-900/80 text-green-100' :
          'bg-red-900/80 text-red-100'
        }`}>
          <div className="flex items-center space-x-2">
            {routeStatus.type === 'loading' && (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current"></div>
            )}
            {routeStatus.type === 'success' && (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            )}
            {routeStatus.type === 'error' && (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            )}
            <span className="text-sm font-medium">{routeStatus.message}</span>
          </div>
        </div>
      )}


      {/* Map Area */}
      <div className="absolute top-0 left-0 right-0" style={{ bottom: `${bottomSheetHeight}px` }}>
        <GoogleMap
          className="w-full h-full"
          center={{ lat: 37.5665, lng: 126.9780 }}
          zoom={13}
          markers={mapMarkers}
          onMapLoad={handleMapLoad}
        />
      </div>

      {/* Bottom Sheet */}
      <div
        className={`absolute bottom-0 left-0 right-0 bg-[#0B1220] z-30 shadow-2xl border-t border-[#1F3C7A]/30 ${
          isDragging ? '' : 'transition-all duration-300 ease-out'
        } ${isFullScreen ? 'rounded-none' : 'rounded-t-3xl'}`}
        style={{ 
          height: `${bottomSheetHeight}px`,
          minHeight: '100px',
          maxHeight: `${viewportHeight || 800}px`
        }}
      >
        {/* Drag Handle */}
        <div
          ref={dragRef}
          className="w-full flex justify-center py-4 cursor-grab active:cursor-grabbing hover:bg-[#1F3C7A]/20 transition-colors flex-shrink-0"
          onMouseDown={handleMouseDown}
          onTouchStart={handleTouchStart}
        >
          <div className={`w-12 h-1.5 rounded-full transition-colors ${isDragging ? 'bg-[#3E68FF]' : 'bg-[#6FA0E6]'}`} />
        </div>

        {/* Content */}
        <div 
          className="overflow-y-auto overflow-x-hidden no-scrollbar relative"
          style={{ 
            height: `${bottomSheetHeight - 60}px`,
            maxHeight: `${bottomSheetHeight - 60}px`
          }}
        >
          {showItinerary && selectedItineraryPlaces.length > 0 ? (
            /* 일정 보기 모드 */
            <div className="px-4 py-4">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-[#3E68FF]">내 일정</h2>
                <div className="flex items-center space-x-2">
                  {(directionsRenderers.length > 0 || sequenceMarkers.length > 0) && (
                    <button
                      onClick={clearRoute}
                      className="px-3 py-1.5 bg-red-900/30 hover:bg-red-900/50 rounded-full text-sm text-red-400 hover:text-red-300 transition-colors flex items-center space-x-1"
                      title="경로 지우기"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      <span>경로 지우기</span>
                    </button>
                  )}
                  <button
                    onClick={() => setShowItinerary(false)}
                    className="px-3 py-1.5 bg-[#1F3C7A]/30 hover:bg-[#3E68FF]/30 rounded-full text-sm text-[#6FA0E6] hover:text-white transition-colors"
                  >
                    장소 찾기
                  </button>
                </div>
              </div>
              
              {/* 여행 정보 */}
              {startDateParam && endDateParam && daysParam && (
                <div className="bg-[#12345D]/50 rounded-2xl p-4 mb-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[#6FA0E6] text-sm mb-1">여행 기간</p>
                      <p className="text-white font-semibold">
                        {new Date(startDateParam).toLocaleDateString('ko-KR', { 
                          month: 'long', 
                          day: 'numeric' 
                        })} - {new Date(endDateParam).toLocaleDateString('ko-KR', { 
                          month: 'long', 
                          day: 'numeric' 
                        })}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[#6FA0E6] text-sm mb-1">총 일수</p>
                      <p className="text-white font-semibold">{daysParam}일</p>
                    </div>
                  </div>
                </div>
              )}

              {/* 날짜별 일정 */}
              {(() => {
                const groupedPlaces = selectedItineraryPlaces.reduce<{[key: number]: SelectedPlace[]}>((acc, place) => {
                  const day = place.dayNumber || 1;
                  if (!acc[day]) acc[day] = [];
                  acc[day].push(place);
                  return acc;
                }, {});

                const sortedDays = Object.keys(groupedPlaces).map(Number).sort((a, b) => a - b);

                return sortedDays.map(day => (
                  <div key={day} className={`mb-6 rounded-2xl transition-all duration-300 ${
                    highlightedDay === day ? 'bg-[#3E68FF]/10 border-2 border-[#3E68FF]/30 p-4' : 'p-2'
                  }`}>
                    <div 
                      className="flex items-center justify-between mb-3 cursor-pointer hover:bg-[#1F3C7A]/20 rounded-xl p-2 transition-colors"
                      onClick={() => {
                        setHighlightedDay(highlightedDay === day ? null : day);
                      }}
                    >
                      <div className="flex items-center">
                        <div className={`rounded-full w-8 h-8 flex items-center justify-center mr-3 transition-all duration-200 ${
                          highlightedDay === day ? 'bg-[#3E68FF] shadow-lg scale-110' : 'bg-[#3E68FF]'
                        }`}>
                          <span className="text-white text-sm font-bold">{day}</span>
                        </div>
                        <h3 className={`text-lg font-semibold transition-colors duration-200 ${
                          highlightedDay === day ? 'text-[#3E68FF]' : 'text-white'
                        }`}>
                          {day}일차
                          {startDateParam && (
                            <span className="text-sm text-[#94A9C9] ml-2">
                              ({new Date(new Date(startDateParam).getTime() + (day - 1) * 24 * 60 * 60 * 1000).toLocaleDateString('ko-KR', { 
                                month: 'short', 
                                day: 'numeric' 
                              })})
                            </span>
                          )}
                        </h3>
                      </div>
                      
                      {/* 경로 버튼들 (2개 이상일 때만 표시) */}
                      {groupedPlaces[day].length >= 2 && (
                        <div className="flex items-center space-x-2" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setHighlightedDay(day);
                              renderBasicRoute(day);
                            }}
                            className="flex items-center space-x-1 px-2 py-1 bg-[#34A853]/10 hover:bg-[#34A853]/20 border border-[#34A853]/30 hover:border-[#34A853]/50 rounded-lg transition-all duration-200 group"
                            title="순서대로 기본 동선 보기"
                          >
                            <svg className="w-3 h-3 text-[#34A853] group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                            </svg>
                            <span className="text-[#34A853] group-hover:text-[#4CAF50] text-xs font-medium transition-colors">기본 동선</span>
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setHighlightedDay(day);
                              openOptimizeConfirm(day);
                            }}
                            className="flex items-center space-x-1 px-2 py-1 bg-[#FF9800]/10 hover:bg-[#FF9800]/20 border border-[#FF9800]/30 hover:border-[#FF9800]/50 rounded-lg transition-all duration-200 group"
                            title="최적화된 경로 보기"
                          >
                            <svg className="w-3 h-3 text-[#FF9800] group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            <span className="text-[#FF9800] group-hover:text-[#FFA726] text-xs font-medium transition-colors">최적화 경로</span>
                          </button>
                        </div>
                      )}
                    </div>
                    
                    <div className="space-y-3 ml-5">
                      {groupedPlaces[day].map((place, index) => (
                        <React.Fragment key={`place-container-${place.id}-${day}-${index}`}>
                        <div>
                          {/* 드롭 존 - 위쪽 */}
                          <div
                            data-drop-zone="true"
                            data-day={day}
                            data-index={index}
                            onDragOver={(e) => handleDragOver(e, index, day)}
                            onDragLeave={handleDragLeave}
                            onDrop={(e) => handleDrop(e, index, day)}
                            className={`h-2 w-full transition-all duration-200 ${
                              dragOverIndex?.day === day && dragOverIndex?.index === index && draggedItem 
                                ? 'border-t-4 border-[#3E68FF] bg-[#3E68FF]/10 mb-2' 
                                : ''
                            }`}
                          />
                          
                          {/* 장소 카드 */}
                          <div
                            data-place-card="true"
                            className="bg-[#1F3C7A]/20 border border-[#1F3C7A]/40 rounded-xl p-4 hover:bg-[#1F3C7A]/30 transition-colors relative cursor-pointer select-none group"
                            onTouchStart={(e) => {
                              handleLongPressStart(e, place, day, index);
                            }}
                            onTouchMove={(e) => {
                              handleLongPressMove(e);
                            }}
                            onTouchEnd={(e) => {
                              handleLongPressEnd(e);
                            }}
                            onTouchCancel={(e) => {
                              handleLongPressEnd(e);
                            }}
                            style={{ 
                              touchAction: 'none',
                              userSelect: 'none',
                              WebkitUserSelect: 'none',
                              WebkitTouchCallout: 'none'
                            } as React.CSSProperties}
                          >
                            {/* Long press 말풍선 힌트 */}
                            <div className="absolute -top-3 -left-3 opacity-0 group-hover:opacity-100 transition-all duration-300 pointer-events-none z-20">
                              <div className="relative bg-[#0B1220] text-white text-xs px-3 py-2 rounded-xl shadow-xl whitespace-nowrap border border-gray-300/60">
                                꾹 눌러 이동
                              </div>
                            </div>
                            
                            {/* 잠금 버튼 - 휴지통 왼쪽 */}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleLockPlace(place.id, day);
                              }}
                              className={`absolute -top-2 right-8 w-8 h-8 border rounded-full flex items-center justify-center shadow-lg transition-all duration-200 group hover:scale-110 z-10 ${
                                lockedPlaces[`${place.id}_${day}`] 
                                  ? 'bg-[#FF9800]/80 hover:bg-[#FF9800] border-[#FF9800]/30 hover:border-[#FF9800]/50' 
                                  : 'bg-[#1F3C7A]/80 hover:bg-[#1F3C7A] border-[#3E68FF]/30 hover:border-[#3E68FF]/50'
                              }`}
                              title={lockedPlaces[`${place.id}_${day}`] ? "순서 고정 해제" : "순서 고정"}
                            >
                              {lockedPlaces[`${place.id}_${day}`] ? (
                                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                </svg>
                              ) : (
                                <svg className="w-4 h-4 text-[#94A9C9] group-hover:text-[#FF9800]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                                </svg>
                              )}
                            </button>

                            {/* 휴지통 버튼 - 오른쪽 상단 모서리 */}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                openDeleteConfirm(place, day);
                              }}
                              className="absolute -top-2 -right-2 w-8 h-8 bg-[#1F3C7A]/80 hover:bg-[#1F3C7A] border border-[#3E68FF]/30 hover:border-[#3E68FF]/50 rounded-full flex items-center justify-center shadow-lg transition-all duration-200 group hover:scale-110 z-10"
                              title="일정에서 제거"
                            >
                              <svg className="w-4 h-4 text-[#94A9C9] group-hover:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
                            </button>

                            <div className="flex items-start justify-between">
                              <div 
                                className="flex-1 cursor-pointer pr-4" 
                                onClick={(e) => {
                                  // Long press 중이거나 preventClick이 true면 클릭 무시
                                  if (longPressData?.preventClick || longPressData?.isLongPressing || longPressData?.isDragging) {
                                    e.stopPropagation();
                                    e.preventDefault();
                                    return;
                                  }
                                  e.stopPropagation();
                                  e.preventDefault();
                                  router.push(`/attraction/${place.id}`);
                                }}
                                onMouseDown={(e) => e.stopPropagation()}
                              >
                                <div className="mb-1">
                                  <h4 className="font-semibold text-white mb-1">{place.name}</h4>
                                  <span className="text-[#6FA0E6] text-[10px] bg-[#1F3C7A]/50 px-2 py-0.5 rounded-full">
                                    {getCategoryName(place.category)}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* 구간 정보 (마지막 장소가 아닐 때만 표시) */}
                        {index < groupedPlaces[day].length - 1 && (
                          (() => {
                            const nextPlace = groupedPlaces[day][index + 1];
                            const segmentInfo = getRouteSegmentInfo(day, place.id, nextPlace.id);
                            
                            if (segmentInfo) {
                              return (
                                <div className="my-4">
                                  <div className="flex items-center justify-center mb-3">
                                    <div className="flex-1 h-px bg-gradient-to-r from-transparent via-[#3E68FF]/30 to-transparent"></div>
                                    <div className="mx-4 flex items-center space-x-2 text-sm">
                                      <span className="text-[#60A5FA] font-medium">{segmentInfo.distance}</span>
                                      <span className="text-[#94A9C9]">·</span>
                                      <span className="text-[#34D399] font-medium">{segmentInfo.duration}</span>
                                    </div>
                                    <div className="flex-1 h-px bg-gradient-to-r from-[#3E68FF]/30 via-transparent to-transparent"></div>
                                  </div>
                                  
                                  {/* 상세 교통수단 정보 */}
                                  {segmentInfo.transitDetails && segmentInfo.transitDetails.length > 0 && (
                                    <div className="bg-[#0B1220]/90 backdrop-blur-sm border border-[#3E68FF]/20 rounded-xl p-4 mx-2">
                                      <div className="space-y-3">
                                        {segmentInfo.transitDetails.map((step: any, stepIndex: number) => (
                                          <div key={stepIndex}>
                                            {step.transitDetails ? (
                                              // 대중교통 구간
                                              <div className="flex items-center space-x-3">
                                                <div className="flex-shrink-0">
                                                  <div className="bg-[#3E68FF] text-white px-3 py-1 rounded-full text-xs font-bold min-w-0">
                                                    {step.transitDetails.line || step.transitDetails.vehicle}
                                                  </div>
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                  <div className="flex items-center space-x-2 text-sm">
                                                    <span className="text-[#94A9C9] truncate">
                                                      {step.transitDetails.departure_stop}
                                                    </span>
                                                    <svg className="w-4 h-4 text-[#3E68FF] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                                                    </svg>
                                                    <span className="text-[#94A9C9] truncate">
                                                      {step.transitDetails.arrival_stop}
                                                    </span>
                                                  </div>
                                                  {step.transitDetails.departure_time && (
                                                    <div className="flex items-center space-x-3 text-xs text-[#6FA0E6] mt-1">
                                                      <span>출발: {step.transitDetails.departure_time}</span>
                                                      {step.transitDetails.arrival_time && (
                                                        <span>도착: {step.transitDetails.arrival_time}</span>
                                                      )}
                                                    </div>
                                                  )}
                                                </div>
                                                <div className="flex-shrink-0 text-xs text-[#94A9C9]">
                                                  {step.duration}
                                                </div>
                                              </div>
                                            ) : step.mode === 'WALKING' ? (
                                              // 도보 구간
                                              <div className="flex items-center space-x-3">
                                                <div className="flex-shrink-0">
                                                  <div className="w-8 h-8 bg-[#34D399]/20 rounded-full flex items-center justify-center">
                                                    <span className="text-sm">🚶</span>
                                                  </div>
                                                </div>
                                                <div className="flex-1 text-sm text-[#94A9C9]">
                                                  <div className="truncate">
                                                    {step.instruction || '도보 이동'}
                                                  </div>
                                                  <div className="text-xs text-[#6FA0E6] mt-1">
                                                    {step.distance} · {step.duration}
                                                  </div>
                                                </div>
                                              </div>
                                            ) : (
                                              // 기타 교통수단
                                              <div className="flex items-center space-x-3">
                                                <div className="flex-shrink-0 text-xs text-[#94A9C9] bg-[#1F3C7A]/30 px-2 py-1 rounded">
                                                  {step.mode}
                                                </div>
                                                <div className="flex-1 text-sm text-[#94A9C9] truncate">
                                                  {step.instruction}
                                                </div>
                                                <div className="flex-shrink-0 text-xs text-[#6FA0E6]">
                                                  {step.duration}
                                                </div>
                                              </div>
                                            )}
                                            
                                            {/* 구간 사이 구분선 (마지막이 아닐 때) */}
                                            {stepIndex < segmentInfo.transitDetails.length - 1 && (
                                              <div className="h-px bg-[#3E68FF]/10 my-2 mx-4"></div>
                                            )}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            }
                            return null;
                          })()
                        )}
                        </React.Fragment>
                      ))}
                      
                      {/* 마지막 드롭 존 */}
                      <div
                        data-drop-zone="true"
                        data-day={day}
                        data-index={groupedPlaces[day].length}
                        onDragOver={(e) => handleDragOver(e, groupedPlaces[day].length, day)}
                        onDragLeave={handleDragLeave}
                        onDrop={(e) => handleDrop(e, groupedPlaces[day].length, day)}
                        className={`h-2 w-full transition-all duration-200 ${
                          dragOverIndex?.day === day && dragOverIndex?.index === groupedPlaces[day].length && draggedItem 
                            ? 'border-t-4 border-[#3E68FF] bg-[#3E68FF]/10 mt-2' 
                            : ''
                        }`}
                      />
                    </div>
                  </div>
                ));
              })()}

              {/* 일정 없음 메시지 */}
              {selectedItineraryPlaces.length === 0 && (
                <div className="text-center py-8">
                  <div className="text-6xl mb-4">📝</div>
                  <p className="text-[#94A9C9] text-lg mb-2">아직 선택된 장소가 없습니다</p>
                  <p className="text-[#6FA0E6] text-sm">장소를 찾아서 일정에 추가해보세요</p>
                </div>
              )}
            </div>
          ) : (
            /* 카테고리 보기 모드 */
            <div className="px-4 py-4">
              {/* 카테고리 헤더 */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xl font-bold text-[#3E68FF]">
                    {getCategoryName(selectedCategory)} 장소
                  </h2>
                  {selectedItineraryPlaces.length > 0 && (
                    <button
                      onClick={() => setShowItinerary(true)}
                      className="flex items-center space-x-1 px-3 py-1.5 bg-[#1F3C7A]/30 hover:bg-[#3E68FF]/30 rounded-full transition-colors text-sm text-[#6FA0E6] hover:text-white"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3a1 1 0 011-1h6a1 1 0 011 1v4M8 7h8M8 7H6a2 2 0 00-2 2v8a2 2 0 002-2V9a2 2 0 00-2-2h-2m-6 4v4m-4-2h8" />
                      </svg>
                      <span>내 일정</span>
                    </button>
                  )}
                </div>
                <p className="text-[#94A9C9] text-sm">
                  {categoryLoading ? '로딩 중...' : `${categoryPlaces.length}개의 장소를 찾았습니다`}
                </p>
              </div>
              
              {/* 카테고리 장소 목록 */}
              {categoryLoading ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3E68FF]"></div>
                </div>
              ) : categoryPlaces.length > 0 ? (
                <div className="space-y-3">
                  {categoryPlaces.map(place => (
                    <div
                      key={place.id}
                      className="bg-[#1F3C7A]/20 border border-[#1F3C7A]/40 rounded-xl p-4 hover:bg-[#1F3C7A]/30 transition-colors cursor-pointer"
                      onClick={() => router.push(`/attraction/${place.id}`)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="mb-3">
                            <h3 className="font-semibold text-white text-lg mb-1">{place.name}</h3>
                            <span className="text-[#6FA0E6] text-[10px] bg-[#1F3C7A]/50 px-2 py-0.5 rounded-full">
                              {getCategoryName(place.category)}
                            </span>
                          </div>
                          <p className="text-[#94A9C9] text-sm mb-2">📍 {place.city.name}</p>
                          <p className="text-[#94A9C9] text-sm mb-3 line-clamp-2">{place.description}</p>
                          <div className="flex items-center">
                            <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                            </svg>
                            <span className="text-[#6FA0E6] text-sm font-medium">{place.rating}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-[#94A9C9] text-lg mb-2">해당 카테고리의 장소가 없습니다</p>
                  <p className="text-[#6FA0E6] text-sm">다른 카테고리를 선택해보세요</p>
                </div>
              )}
            </div>
          )}
          
          {/* 하단 여백 */}
          <div className="h-20"></div>
        </div>
      </div>

      {/* 최적화 확인 모달 */}
      {optimizeConfirmModal.isOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center">
          {/* 배경 오버레이 */}
          <div 
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={closeOptimizeConfirm}
          />
          
          {/* 모달 컨텐츠 */}
          <div className="relative bg-[#0B1220] border border-[#1F3C7A]/50 rounded-2xl p-6 mx-4 max-w-sm w-full shadow-2xl">
            <div className="text-center">
              {/* 경고 아이콘 */}
              <div className="mx-auto w-12 h-12 bg-[#FF9800]/20 rounded-full flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-[#FF9800]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.732 18.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              
              {/* 제목 */}
              <h3 className="text-lg font-semibold text-white mb-2">
                경로 최적화 확인
              </h3>
              
              {/* 설명 */}
              <p className="text-[#94A9C9] text-sm mb-6 leading-relaxed">
                최적화 경로를 실행하면
                <br/>
                <span className="text-[#FF9800] font-medium">{optimizeConfirmModal.dayNumber}일차</span>의 장소 순서가 변경될 수 있습니다.
                <br/>
                <span className="text-[#6FA0E6] text-xs mt-2 block">변경된 순서는 되돌릴 수 없습니다.</span>
              </p>
              
              {/* 버튼들 */}
              <div className="flex space-x-3">
                <button
                  onClick={closeOptimizeConfirm}
                  className="flex-1 py-2.5 px-4 bg-[#1F3C7A]/30 hover:bg-[#1F3C7A]/50 border border-[#1F3C7A]/50 hover:border-[#1F3C7A]/70 rounded-xl text-[#94A9C9] hover:text-white transition-all duration-200"
                >
                  취소
                </button>
                <button
                  onClick={() => {
                    closeOptimizeConfirm();
                    optimizeRouteForDay(optimizeConfirmModal.dayNumber);
                  }}
                  className="flex-1 py-2.5 px-4 bg-[#FF9800]/20 hover:bg-[#FF9800]/30 border border-[#FF9800]/50 hover:border-[#FF9800]/70 rounded-xl text-[#FF9800] hover:text-[#FFA726] transition-all duration-200 font-medium"
                >
                  확인
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 삭제 확인 모달 */}
      {deleteConfirmModal.isOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center">
          {/* 배경 오버레이 */}
          <div 
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={closeDeleteConfirm}
          />
          
          {/* 모달 컨텐츠 */}
          <div className="relative bg-[#0B1220] border border-[#1F3C7A]/50 rounded-2xl p-6 mx-4 max-w-sm w-full shadow-2xl">
            <div className="text-center">
              {/* 삭제 아이콘 */}
              <div className="mx-auto w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              
              {/* 제목 */}
              <h3 className="text-lg font-semibold text-white mb-2">
                장소 삭제 확인
              </h3>
              
              {/* 설명 */}
              <p className="text-[#94A9C9] text-sm mb-6 leading-relaxed">
                <span className="text-white font-medium">&ldquo;{deleteConfirmModal.place?.name}&rdquo;</span>을(를)
                <br/>
                일정에서 삭제하시겠습니까?
                <br/>
                <span className="text-[#6FA0E6] text-xs mt-2 block">삭제된 장소는 복구할 수 없습니다.</span>
              </p>
              
              {/* 버튼들 */}
              <div className="flex space-x-3">
                <button
                  onClick={closeDeleteConfirm}
                  className="flex-1 py-2.5 px-4 bg-[#1F3C7A]/30 hover:bg-[#1F3C7A]/50 border border-[#1F3C7A]/50 hover:border-[#1F3C7A]/70 rounded-xl text-[#94A9C9] hover:text-white transition-all duration-200"
                >
                  취소
                </button>
                <button
                  onClick={confirmDelete}
                  className="flex-1 py-2.5 px-4 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 hover:border-red-500/70 rounded-xl text-red-400 hover:text-red-300 transition-all duration-200 font-medium"
                >
                  삭제
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}