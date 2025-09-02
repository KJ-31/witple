// 'use client'

// import React, { useState, useRef, useEffect } from 'react'
// import { useRouter, useSearchParams } from 'next/navigation'
// import { RECOMMENDED_CITY_SECTIONS } from '../../lib/dummyData'

// type CategoryKey = 'all' | 'tourist' | 'food' | 'culture' | 'nature' | 'shopping'

// interface SelectedPlace {
//   id: string
//   name: string
//   category: string
//   rating: number
//   description: string
// }

// export default function MapPage() {
//   const router = useRouter()
//   const searchParams = useSearchParams()
//   const [searchQuery, setSearchQuery] = useState('')
//   const [selectedCategory, setSelectedCategory] = useState<CategoryKey>('all')
//   const [bottomSheetHeight, setBottomSheetHeight] = useState(320) // 초기 높이
//   const [isDragging, setIsDragging] = useState(false)
//   const [startY, setStartY] = useState(0)
//   const [startHeight, setStartHeight] = useState(0)
//   const [selectedItineraryPlaces, setSelectedItineraryPlaces] = useState<SelectedPlace[]>([])
//   const dragRef = useRef<HTMLDivElement>(null)

//   // URL에서 여행 일정 정보 파싱
//   const placesParam = searchParams.get('places')
//   const startDateParam = searchParams.get('startDate')
//   const endDateParam = searchParams.get('endDate')
//   const daysParam = searchParams.get('days')
//   const baseAttractionParam = searchParams.get('baseAttraction')

//   // 선택된 장소들 로드
//   useEffect(() => {
//     if (placesParam) {
//       const placeIds = placesParam.split(',')
//       const places: SelectedPlace[] = []

//       RECOMMENDED_CITY_SECTIONS.forEach(city => {
//         city.attractions.forEach(attraction => {
//           if (placeIds.includes(attraction.id)) {
//             places.push({
//               id: attraction.id,
//               name: attraction.name,
//               category: attraction.category,
//               rating: attraction.rating,
//               description: attraction.description
//             })
//           }
//         })
//       })

//       setSelectedItineraryPlaces(places)
//     }
//   }, [placesParam])

//   // 카테고리 정의
//   const categories = [
//     { key: 'all' as CategoryKey, name: '전체', icon: '🏠' },
//     { key: 'tourist' as CategoryKey, name: '관광', icon: '🏛️' },
//     { key: 'food' as CategoryKey, name: '맛집', icon: '🍽️' },
//     { key: 'culture' as CategoryKey, name: '문화', icon: '🎭' },
//     { key: 'nature' as CategoryKey, name: '자연', icon: '🌿' },
//     { key: 'shopping' as CategoryKey, name: '쇼핑', icon: '🛍️' }
//   ]

//   // 모든 추천 장소 가져오기
//   const getAllRecommendedPlaces = () => {
//     const allPlaces = RECOMMENDED_CITY_SECTIONS.flatMap(city =>
//       city.attractions.map(attraction => ({
//         ...attraction,
//         cityName: city.cityName
//       }))
//     )
//     return allPlaces
//   }

//   const allPlaces = getAllRecommendedPlaces()

//   // 카테고리별 필터링
//   const getFilteredPlaces = () => {
//     let filtered = allPlaces

//     if (selectedCategory !== 'all') {
//       filtered = filtered.filter(place => place.category === selectedCategory)
//     }

//     if (searchQuery.trim()) {
//       filtered = filtered.filter(place =>
//         place.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
//         place.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
//         place.cityName.toLowerCase().includes(searchQuery.toLowerCase())
//       )
//     }

//     return filtered
//   }

//   const filteredPlaces = getFilteredPlaces()

//   // 드래그 핸들링
//   const handleMouseDown = (e: React.MouseEvent) => {
//     setIsDragging(true)
//     setStartY(e.clientY)
//     setStartHeight(bottomSheetHeight)
//   }

//   const handleTouchStart = (e: React.TouchEvent) => {
//     setIsDragging(true)
//     setStartY(e.touches[0].clientY)
//     setStartHeight(bottomSheetHeight)
//   }

//   useEffect(() => {
//     const handleMouseMove = (e: MouseEvent) => {
//       if (!isDragging) return

//       const deltaY = startY - e.clientY // 위로 드래그할 때 양수
//       const newHeight = Math.max(200, Math.min(window.innerHeight - 60, startHeight + deltaY))
//       setBottomSheetHeight(newHeight)
//     }

//     const handleTouchMove = (e: TouchEvent) => {
//       if (!isDragging) return

//       const deltaY = startY - e.touches[0].clientY
//       const newHeight = Math.max(200, Math.min(window.innerHeight - 60, startHeight + deltaY))
//       setBottomSheetHeight(newHeight)
//     }

//     const handleMouseUp = () => {
//       setIsDragging(false)

//       // 스냅 기능: 특정 위치로 자동 조정
//       const screenHeight = window.innerHeight
//       const currentHeight = bottomSheetHeight

//       // 카테고리 필터 바로 아래 위치 (뒤로가기 + 검색바 + 카테고리 필터 + 여백)
//       const categoryBottomPosition = screenHeight - 120 // 상단에서 120px 아래 위치

//       if (currentHeight < screenHeight * 0.25) {
//         // 25% 미만이면 최소 높이로
//         setBottomSheetHeight(200)
//       } else if (currentHeight > categoryBottomPosition - 80 && currentHeight < categoryBottomPosition + 30) {
//         // 카테고리 아래 근처면 카테고리 바로 아래로 고정
//         setBottomSheetHeight(categoryBottomPosition)
//       } else if (currentHeight > screenHeight * 0.8) {
//         // 80% 이상이면 카테고리 바로 아래로 (거의 전체)
//         setBottomSheetHeight(categoryBottomPosition)
//       } else if (currentHeight < screenHeight * 0.4) {
//         // 40% 미만이면 기본 크기로
//         setBottomSheetHeight(320)
//       } else if (currentHeight < screenHeight * 0.65) {
//         // 65% 미만이면 중간 크기로
//         setBottomSheetHeight(Math.floor(screenHeight * 0.55))
//       } else {
//         // 그 외는 카테고리 아래로
//         setBottomSheetHeight(categoryBottomPosition)
//       }
//     }

//     if (isDragging) {
//       document.addEventListener('mousemove', handleMouseMove)
//       document.addEventListener('mouseup', handleMouseUp)
//       document.addEventListener('touchmove', handleTouchMove)
//       document.addEventListener('touchend', handleMouseUp)
//     }

//     return () => {
//       document.removeEventListener('mousemove', handleMouseMove)
//       document.removeEventListener('mouseup', handleMouseUp)
//       document.removeEventListener('touchmove', handleTouchMove)
//       document.removeEventListener('touchend', handleMouseUp)
//     }
//   }, [isDragging, startY, startHeight])

//   const handleBack = () => {
//     router.back()
//   }

//   const handleSearch = (e: React.FormEvent) => {
//     e.preventDefault()
//     // 검색 로직은 이미 실시간으로 적용됨
//   }

//   const handlePlaceClick = (placeId: string) => {
//     router.push(`/attraction/${placeId}`)
//   }

//   return (
//     <div className="min-h-screen bg-[#0B1220] text-white relative overflow-hidden">
//       {/* Header with Back Button */}
//       <div className="absolute top-4 left-4 z-50">
//         <button
//           onClick={handleBack}
//           className="p-2 bg-black/30 rounded-full backdrop-blur-sm hover:bg-black/50 transition-colors"
//         >
//           <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
//           </svg>
//         </button>
//       </div>

//       {/* Search Bar */}
//       <div className="absolute top-4 left-16 right-4 z-40">
//         <form onSubmit={handleSearch}>
//           <div className="relative">
//             <input
//               type="text"
//               placeholder="장소나 도시를 검색하세요"
//               value={searchQuery}
//               onChange={(e) => setSearchQuery(e.target.value)}
//               className="
//                 w-full px-4 pr-12 py-3 text-sm
//                 rounded-2xl
//                 bg-black/30 backdrop-blur-sm
//                 text-white placeholder-gray-300
//                 ring-1 ring-white/20
//                 focus:outline-none focus:ring-2 focus:ring-[#3E68FF]/60
//               "
//             />
//             <button
//               type="submit"
//               className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-300 hover:text-white transition"
//             >
//               <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
//               </svg>
//             </button>
//           </div>
//         </form>
//       </div>

//       {/* Category Filter Buttons */}
//       <div className="absolute top-20 left-4 right-4 z-40">
//         <div className="flex space-x-2 overflow-x-auto no-scrollbar">
//           {categories.map(category => (
//             <button
//               key={category.key}
//               onClick={() => setSelectedCategory(category.key)}
//               className={`
//                 flex-shrink-0 px-3 py-2 rounded-full text-xs font-medium transition-all duration-200 flex items-center space-x-1
//                 backdrop-blur-sm
//                 ${selectedCategory === category.key
//                   ? 'bg-[#3E68FF] text-white shadow-lg'
//                   : 'bg-black/30 text-gray-300 hover:text-white hover:bg-black/50'
//                 }
//               `}
//             >
//               <span>{category.icon}</span>
//               <span>{category.name}</span>
//             </button>
//           ))}
//         </div>
//       </div>

//       {/* Map Area - Fixed Height */}
//       <div className="absolute top-0 left-0 right-0 bottom-0 bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
//         {/* Map Placeholder - 여기에 실제 지도 API가 들어갈 예정 */}
//         <div className="text-center text-white/70">
//           <div className="text-6xl mb-4">🗺️</div>
//           <p className="text-lg font-medium mb-2">지도 영역</p>
//           <p className="text-sm opacity-75">외부 지도 API 연동 예정</p>

//           {/* 여행 일정 정보 표시 */}
//           {selectedItineraryPlaces.length > 0 && startDateParam && daysParam && (
//             <div className="mt-4 bg-black/30 backdrop-blur-sm rounded-lg px-4 py-3">
//               <p className="text-sm mb-1">
//                 <span className="text-[#3E68FF] font-semibold">{selectedItineraryPlaces.length}개 장소</span>로
//                 <span className="text-[#6FA0E6] font-semibold ml-1">{daysParam}일간</span>의 여행
//               </p>
//               <p className="text-xs opacity-75">
//                 {startDateParam} ~ {endDateParam}
//               </p>
//             </div>
//           )}

//           {/* 검색된 장소 수 표시 */}
//           {(searchQuery || selectedCategory !== 'all') && (
//             <div className="mt-4 bg-black/30 backdrop-blur-sm rounded-lg px-4 py-2">
//               <p className="text-sm">
//                 <span className="text-[#3E68FF] font-semibold">{filteredPlaces.length}개</span>의 장소를 찾았습니다
//               </p>
//             </div>
//           )}
//         </div>

//         {/* Route visualization placeholder */}
//         <div className="absolute inset-0 pointer-events-none">
//           {/* 실제 구현 시 여기에 경로 표시 */}
//         </div>
//       </div>

//       {/* Draggable Bottom Sheet */}
//       <div
//         className={`absolute bottom-0 left-0 right-0 bg-[#0B1220] z-30 ${
//           bottomSheetHeight > window.innerHeight - 150 ? 'rounded-t-3xl' : 'rounded-t-3xl'
//         } shadow-2xl ${
//           isDragging ? '' : 'transition-all duration-300 ease-out'
//         }`}
//         style={{ height: `${bottomSheetHeight}px` }}
//       >
//         {/* Drag Handle */}
//         <div
//           ref={dragRef}
//           className="w-full flex justify-center py-4 cursor-grab active:cursor-grabbing hover:bg-[#1F3C7A]/20 transition-colors"
//           onMouseDown={handleMouseDown}
//           onTouchStart={handleTouchStart}
//         >
//           <div className={`w-12 h-1.5 rounded-full transition-colors ${
//             isDragging ? 'bg-[#3E68FF]' : 'bg-[#6FA0E6]'
//           }`}></div>
//         </div>

//         {/* Bottom Sheet Content */}
//         <div className="px-4 pb-4 h-full overflow-hidden flex flex-col">
//           {/* 선택된 일정이 있을 때 */}
//           {selectedItineraryPlaces.length > 0 ? (
//             <>
//               <div className="flex items-center justify-between mb-4">
//                 <h2 className="text-lg font-semibold text-[#94A9C9]">
//                   내 여행 일정
//                 </h2>
//                 <span className="text-sm text-[#6FA0E6]">
//                   {selectedItineraryPlaces.length}개 장소
//                 </span>
//               </div>

//               {/* 선택된 장소들 */}
//               <div className="mb-6">
//                 <div className="space-y-3">
//                   {selectedItineraryPlaces.map((place, index) => (
//                     <div
//                       key={place.id}
//                       onClick={() => handlePlaceClick(place.id)}
//                       className="bg-[#3E68FF]/10 border border-[#3E68FF]/30 rounded-xl p-4 cursor-pointer hover:bg-[#3E68FF]/20 transition-all duration-200"
//                     >
//                       <div className="flex items-start justify-between">
//                         <div className="flex-1">
//                           <div className="flex items-center space-x-2 mb-2">
//                             <span className="bg-[#3E68FF] text-white text-xs font-bold px-2 py-1 rounded-full">
//                               {index + 1}
//                             </span>
//                             <h3 className="font-semibold text-white text-lg">{place.name}</h3>
//                             <span className="text-[#6FA0E6] text-xs bg-[#1F3C7A]/50 px-2 py-1 rounded-full">
//                               {getCategoryName(place.category)}
//                             </span>
//                           </div>

//                           <p className="text-[#94A9C9] text-sm mb-3 line-clamp-2">
//                             {place.description}
//                           </p>

//                           <div className="flex items-center">
//                             <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
//                               <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
//                             </svg>
//                             <span className="text-[#6FA0E6] text-sm font-medium">{place.rating}</span>
//                           </div>
//                         </div>

//                         <svg className="w-5 h-5 text-[#3E68FF] ml-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
//                         </svg>
//                       </div>
//                     </div>
//                   ))}
//                 </div>
//               </div>

//               {/* 추가 추천 장소 섹션 */}
//               <div className="border-t border-[#1F3C7A]/30 pt-4">
//                 <div className="flex items-center justify-between mb-4">
//                   <h3 className="text-md font-semibold text-[#94A9C9]">
//                     추가 추천 장소
//                   </h3>
//                   <span className="text-sm text-[#6FA0E6]">
//                     {filteredPlaces.filter(place => !selectedItineraryPlaces.some(selected => selected.id === place.id)).length}개
//                   </span>
//                 </div>
//               </div>
//             </>
//           ) : (
//             <div className="flex items-center justify-between mb-4">
//               <h2 className="text-lg font-semibold text-[#94A9C9]">
//                 추천 여행지
//               </h2>
//               <span className="text-sm text-[#6FA0E6]">
//                 {filteredPlaces.length}개 장소
//               </span>
//             </div>
//           )}

//           {/* Additional Places List (excluding already selected ones) */}
//           <div className="flex-1 overflow-y-auto no-scrollbar space-y-3 pb-4">
//             {(() => {
//               const additionalPlaces = filteredPlaces.filter(place =>
//                 !selectedItineraryPlaces.some(selected => selected.id === place.id)
//               )

//               if (additionalPlaces.length === 0) {
//                 return (
//                   <div className="text-center py-8">
//                     <p className="text-[#6FA0E6] text-lg mb-2">
//                       {selectedItineraryPlaces.length > 0 ? '추가 추천 장소가 없습니다' : '검색 결과가 없습니다'}
//                     </p>
//                     <p className="text-[#94A9C9] text-sm">
//                       {selectedItineraryPlaces.length > 0 ? '다른 카테고리를 확인해보세요' : '다른 검색어나 카테고리를 시도해보세요'}
//                     </p>
//                   </div>
//                 )
//               }

//               return additionalPlaces.map(place => (
//                 <div
//                   key={place.id}
//                   onClick={() => handlePlaceClick(place.id)}
//                   className="bg-[#0F1A31]/50 rounded-xl p-4 cursor-pointer hover:bg-[#12345D]/50 transition-all duration-200"
//                 >
//                   <div className="flex items-start justify-between">
//                     <div className="flex-1">
//                       <div className="flex items-center space-x-2 mb-2">
//                         <h3 className="font-semibold text-white text-lg">{place.name}</h3>
//                         <span className="text-[#6FA0E6] text-xs bg-[#1F3C7A]/50 px-2 py-1 rounded-full">
//                           {getCategoryName(place.category)}
//                         </span>
//                       </div>

//                       <p className="text-[#94A9C9] text-sm mb-2">
//                         📍 {place.cityName}
//                       </p>

//                       <p className="text-[#94A9C9] text-sm mb-3 line-clamp-2">
//                         {place.description}
//                       </p>

//                       <div className="flex items-center">
//                         <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
//                           <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
//                         </svg>
//                         <span className="text-[#6FA0E6] text-sm font-medium">{place.rating}</span>
//                       </div>
//                     </div>

//                     <svg className="w-5 h-5 text-[#6FA0E6] ml-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                       <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
//                     </svg>
//                   </div>
//                 </div>
//               ))
//             })()}
//           </div>
//         </div>
//       </div>
//     </div>
//   )
// }

// // 카테고리 한국어 변환 함수
// function getCategoryName(category: string): string {
//   const categoryMap: { [key: string]: string } = {
//     tourist: '관광',
//     food: '맛집',
//     culture: '문화',
//     nature: '자연',
//     shopping: '쇼핑'
//   }
//   return categoryMap[category] || category
// }

'use client'

import React, { useState, useRef, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { RECOMMENDED_CITY_SECTIONS } from '../../lib/dummyData'

type CategoryKey = 'all' | 'tourist' | 'food' | 'culture' | 'nature' | 'shopping'

interface SelectedPlace {
  id: string
  name: string
  category: string
  rating: number
  description: string
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
  const [viewportHeight, setViewportHeight] = useState<number>(0) // ✅ 화면 높이 저장
  const [selectedItineraryPlaces, setSelectedItineraryPlaces] = useState<SelectedPlace[]>([])
  const dragRef = useRef<HTMLDivElement>(null)

  // URL 파라미터
  const placesParam = searchParams.get('places')
  const startDateParam = searchParams.get('startDate')
  const endDateParam = searchParams.get('endDate')
  const daysParam = searchParams.get('days')
  const baseAttractionParam = searchParams.get('baseAttraction')

  // ✅ 최초/리사이즈 시 화면 높이 갱신
  useEffect(() => {
    const setH = () => setViewportHeight(window.innerHeight)
    setH()
    window.addEventListener('resize', setH)
    return () => window.removeEventListener('resize', setH)
  }, [])

  // 선택된 장소 로드
  useEffect(() => {
    if (placesParam) {
      const placeIds = placesParam.split(',')
      const places: SelectedPlace[] = []
      RECOMMENDED_CITY_SECTIONS.forEach(city => {
        city.attractions.forEach(attraction => {
          if (placeIds.includes(attraction.id)) {
            places.push({
              id: attraction.id,
              name: attraction.name,
              category: attraction.category,
              rating: attraction.rating,
              description: attraction.description
            })
          }
        })
      })
      setSelectedItineraryPlaces(places)
    }
  }, [placesParam])

  const categories = [
    { key: 'all' as CategoryKey, name: '전체', icon: '🏠' },
    { key: 'tourist' as CategoryKey, name: '관광', icon: '🏛️' },
    { key: 'food' as CategoryKey, name: '맛집', icon: '🍽️' },
    { key: 'culture' as CategoryKey, name: '문화', icon: '🎭' },
    { key: 'nature' as CategoryKey, name: '자연', icon: '🌿' },
    { key: 'shopping' as CategoryKey, name: '쇼핑', icon: '🛍️' }
  ]

  const getAllRecommendedPlaces = () => {
    const allPlaces = RECOMMENDED_CITY_SECTIONS.flatMap(city =>
      city.attractions.map(attraction => ({
        ...attraction,
        cityName: city.cityName
      }))
    )
    return allPlaces
  }

  const allPlaces = getAllRecommendedPlaces()

  const getFilteredPlaces = () => {
    let filtered = allPlaces
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(place => place.category === selectedCategory)
    }
    if (searchQuery.trim()) {
      filtered = filtered.filter(place =>
        place.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        place.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        place.cityName.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    return filtered
  }

  const filteredPlaces = getFilteredPlaces()

  // 드래그 시작
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true)
    setStartY(e.clientY)
    setStartHeight(bottomSheetHeight)
  }
  const handleTouchStart = (e: React.TouchEvent) => {
    setIsDragging(true)
    setStartY(e.touches[0].clientY)
    setStartHeight(bottomSheetHeight)
  }

  useEffect(() => {
    const screenH = viewportHeight || window.innerHeight

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return
      const deltaY = startY - e.clientY // 위로 드래그 양수
      // ✅ 최대 높이를 '전체 화면 높이'로 허용
      const newHeight = Math.max(200, Math.min(screenH, startHeight + deltaY))
      setBottomSheetHeight(newHeight)
    }

    const handleTouchMove = (e: TouchEvent) => {
      if (!isDragging) return
      const deltaY = startY - e.touches[0].clientY
      const newHeight = Math.max(200, Math.min(screenH, startHeight + deltaY))
      setBottomSheetHeight(newHeight)
    }

    const handleUp = () => {
      setIsDragging(false)

      // ✅ 스냅 포인트: [최소 200, 중간(55%), 카테고리 아래, 전체(풀스크린)]
      const MIN = 200
      const MID = Math.floor(screenH * 0.55)
      const CATEGORY_BELOW = screenH - 120
      const FULL = screenH

      const points = [MIN, MID, CATEGORY_BELOW, FULL]
      const current = bottomSheetHeight

      // 가장 가까운 포인트로 스냅
      let nearest = points[0]
      let minDist = Math.abs(points[0] - current)
      for (let i = 1; i < points.length; i++) {
        const d = Math.abs(points[i] - current)
        if (d < minDist) {
          minDist = d
          nearest = points[i]
        }
      }
      setBottomSheetHeight(nearest)
    }

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleUp)
      document.addEventListener('touchmove', handleTouchMove, { passive: false })
      document.addEventListener('touchend', handleUp)
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleUp)
      document.removeEventListener('touchmove', handleTouchMove)
      document.removeEventListener('touchend', handleUp)
    }
    // ✅ bottomSheetHeight를 의존성에 포함해 최신 값으로 스냅 계산
  }, [isDragging, startY, startHeight, viewportHeight, bottomSheetHeight])

  const handleBack = () => router.back()

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
  }

  const handlePlaceClick = (placeId: string) => {
    router.push(`/attraction/${placeId}`)
  }

  // ✅ 풀스크린 여부에 따라 라운드 제거
  const isFullScreen = bottomSheetHeight >= (viewportHeight || 0) - 2

  return (
    <div className="min-h-screen bg-[#0B1220] text-white relative overflow-hidden">
      {/* Header Back */}
      <div className="absolute top-4 left-4 z-50">
        <button
          onClick={handleBack}
          className="p-2 bg:black/30 bg-black/30 rounded-full backdrop-blur-sm hover:bg-black/50 transition-colors"
        >
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Search Bar */}
      <div className="absolute top-4 left-16 right-4 z-40">
        <form onSubmit={handleSearch}>
          <div className="relative">
            <input
              type="text"
              placeholder="장소나 도시를 검색하세요"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="
                w-full px-4 pr-12 py-3 text-sm
                rounded-2xl
                bg-black/30 backdrop-blur-sm
                text-white placeholder-gray-300
                ring-1 ring-white/20
                focus:outline-none focus:ring-2 focus:ring-[#3E68FF]/60
              "
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
              onClick={() => setSelectedCategory(category.key)}
              className={`
                flex-shrink-0 px-3 py-2 rounded-full text-xs font-medium transition-all duration-200 flex items-center space-x-1
                backdrop-blur-sm
                ${selectedCategory === category.key
                  ? 'bg-[#3E68FF] text-white shadow-lg'
                  : 'bg-black/30 text-gray-300 hover:text-white hover:bg-black/50'
                }
              `}
            >
              <span>{category.icon}</span>
              <span>{category.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Map Area */}
      <div className="absolute top-0 left-0 right-0 bottom-0 bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
        <div className="text-center text-white/70">
          <div className="text-6xl mb-4">🗺️</div>
          <p className="text-lg font-medium mb-2">지도 영역</p>
          <p className="text-sm opacity-75">외부 지도 API 연동 예정</p>

          {selectedItineraryPlaces.length > 0 && startDateParam && daysParam && (
            <div className="mt-4 bg-black/30 backdrop-blur-sm rounded-lg px-4 py-3">
              <p className="text-sm mb-1">
                <span className="text-[#3E68FF] font-semibold">{selectedItineraryPlaces.length}개 장소</span>로
                <span className="text-[#6FA0E6] font-semibold ml-1">{daysParam}일간</span>의 여행
              </p>
              <p className="text-xs opacity-75">
                {startDateParam} ~ {endDateParam}
              </p>
            </div>
          )}

          {(searchQuery || selectedCategory !== 'all') && (
            <div className="mt-4 bg-black/30 backdrop-blur-sm rounded-lg px-4 py-2">
              <p className="text-sm">
                <span className="text-[#3E68FF] font-semibold">{filteredPlaces.length}개</span>의 장소를 찾았습니다
              </p>
            </div>
          )}
        </div>
        <div className="absolute inset-0 pointer-events-none" />
      </div>

      {/* Bottom Sheet */}
      <div
        className={`
          absolute bottom-0 left-0 right-0 bg-[#0B1220] z-30 shadow-2xl
          ${isDragging ? '' : 'transition-all duration-300 ease-out'}
          ${isFullScreen ? 'rounded-none' : 'rounded-t-3xl'}   /* ✅ 풀스크린이면 라운드 제거 */
        `}
        style={{ height: `${bottomSheetHeight}px` }}
      >
        {/* Drag Handle */}
        <div
          ref={dragRef}
          className="w-full flex justify-center py-4 cursor-grab active:cursor-grabbing hover:bg-[#1F3C7A]/20 transition-colors touch-none" /* ✅ 모바일 드래그 안정성 */
          onMouseDown={handleMouseDown}
          onTouchStart={handleTouchStart}
        >
          <div className={`w-12 h-1.5 rounded-full transition-colors ${isDragging ? 'bg-[#3E68FF]' : 'bg-[#6FA0E6]'}`} />
        </div>

        {/* Sheet Content */}
        <div className="px-4 pb-4 h-full overflow-hidden flex flex-col">
          {selectedItineraryPlaces.length > 0 ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-[#94A9C9]">내 여행 일정</h2>
                <span className="text-sm text-[#6FA0E6]">{selectedItineraryPlaces.length}개 장소</span>
              </div>

              <div className="mb-6">
                <div className="space-y-3">
                  {selectedItineraryPlaces.map((place, index) => (
                    <div
                      key={place.id}
                      onClick={() => handlePlaceClick(place.id)}
                      className="bg-[#3E68FF]/10 border border-[#3E68FF]/30 rounded-xl p-4 cursor-pointer hover:bg-[#3E68FF]/20 transition-all duration-200"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            <span className="bg-[#3E68FF] text-white text-xs font-bold px-2 py-1 rounded-full">{index + 1}</span>
                            <h3 className="font-semibold text-white text-lg">{place.name}</h3>
                            <span className="text-[#6FA0E6] text-xs bg-[#1F3C7A]/50 px-2 py-1 rounded-full">{getCategoryName(place.category)}</span>
                          </div>
                          <p className="text-[#94A9C9] text-sm mb-3 line-clamp-2">{place.description}</p>
                          <div className="flex items-center">
                            <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                            </svg>
                            <span className="text-[#6FA0E6] text-sm font-medium">{place.rating}</span>
                          </div>
                        </div>
                        <svg className="w-5 h-5 text-[#3E68FF] ml-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="border-t border-[#1F3C7A]/30 pt-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-md font-semibold text-[#94A9C9]">추가 추천 장소</h3>
                  <span className="text-sm text-[#6FA0E6]">
                    {filteredPlaces.filter(place => !selectedItineraryPlaces.some(selected => selected.id === place.id)).length}개
                  </span>
                </div>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-[#94A9C9]">추천 여행지</h2>
              <span className="text-sm text-[#6FA0E6]">{filteredPlaces.length}개 장소</span>
            </div>
          )}

          {/* 리스트 스크롤 영역 */}
          <div className="flex-1 overflow-y-auto no-scrollbar space-y-3 pb-4">
            {(() => {
              const additionalPlaces = filteredPlaces.filter(place =>
                !selectedItineraryPlaces.some(selected => selected.id === place.id)
              )
              if (additionalPlaces.length === 0) {
                return (
                  <div className="text-center py-8">
                    <p className="text-[#6FA0E6] text-lg mb-2">
                      {selectedItineraryPlaces.length > 0 ? '추가 추천 장소가 없습니다' : '검색 결과가 없습니다'}
                    </p>
                    <p className="text-[#94A9C9] text-sm">
                      {selectedItineraryPlaces.length > 0 ? '다른 카테고리를 확인해보세요' : '다른 검색어나 카테고리를 시도해보세요'}
                    </p>
                  </div>
                )
              }
              return additionalPlaces.map(place => (
                <div
                  key={place.id}
                  onClick={() => handlePlaceClick(place.id)}
                  className="bg-[#0F1A31]/50 rounded-xl p-4 cursor-pointer hover:bg-[#12345D]/50 transition-all duration-200"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <h3 className="font-semibold text-white text-lg">{place.name}</h3>
                        <span className="text-[#6FA0E6] text-xs bg-[#1F3C7A]/50 px-2 py-1 rounded-full">
                          {getCategoryName(place.category)}
                        </span>
                      </div>
                      <p className="text-[#94A9C9] text-sm mb-2">📍 {place.cityName}</p>
                      <p className="text-[#94A9C9] text-sm mb-3 line-clamp-2">{place.description}</p>
                      <div className="flex items-center">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span className="text-[#6FA0E6] text-sm font-medium">{place.rating}</span>
                      </div>
                    </div>
                    <svg className="w-5 h-5 text-[#6FA0E6] ml-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              ))
            })()}
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
