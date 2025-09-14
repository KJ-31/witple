'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useSession, signOut } from 'next-auth/react'

// 여행 상태를 날짜 기준으로 계산하는 함수
const getTripStatus = (startDate: string, endDate: string): 'planned' | 'active' | 'completed' => {
  const today = new Date()
  today.setHours(0, 0, 0, 0) // 시간 부분을 00:00:00으로 설정

  const start = new Date(startDate)
  start.setHours(0, 0, 0, 0)

  const end = new Date(endDate)
  end.setHours(23, 59, 59, 999) // 끝나는 날의 마지막 시간으로 설정

  if (today < start) return 'planned'      // 준비중
  if (today >= start && today <= end) return 'active'  // 여행중
  return 'completed'                       // 발자취
}


interface TripPlace {
  table_name: string
  id: string
  dayNumber: number
  order: number
  name?: string
  category?: string
  rating?: number
  description?: string
  latitude?: string | number
  longitude?: string | number
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
  isLocked?: boolean
}

interface Trip {
  id: number
  user_id: string
  title: string
  places?: TripPlace[]
  start_date: string
  end_date: string
  status: 'active' | 'completed' | 'planned'
  total_budget?: number
  cover_image?: string
  description?: string
  created_at: string
  updated_at?: string
}

interface Post {
  id: number
  user_id: string
  caption: string
  image_url: string
  location?: string
  likes_count: number
  comments_count: number
  created_at: string
}

interface SavedLocation {
  id: number
  user_id: string
  name: string
  address?: string
  latitude?: string
  longitude?: string
  image?: string
  imageUrl?: string
  description?: string
  category?: string
  rating?: number
  created_at: string
  updated_at?: string
}

export default function ProfilePage() {
  const [activeTab, setActiveTab] = useState<'trips' | 'posts' | 'saved'>('trips')
  const [editTab, setEditTab] = useState<'basic' | 'travel'>('basic')
  const [isEditing, setIsEditing] = useState(false)
  const [posts, setPosts] = useState<Post[]>([])
  const [postsLoading, setPostsLoading] = useState(false)
  const [savedLocations, setSavedLocations] = useState<SavedLocation[]>([])
  const [savedLoading, setSavedLoading] = useState(false)
  const [trips, setTrips] = useState<Trip[]>([])
  const [tripsLoading, setTripsLoading] = useState(false)
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [isUploadingImage, setIsUploadingImage] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 토큰 가져오기 함수 (attraction 페이지와 동일)
  const getToken = () => {
    // 먼저 세션에서 토큰 확인
    if ((session as any)?.backendToken) {
      return (session as any).backendToken
    }
    
    // 다른 가능한 토큰 키들 확인
    const possibleTokenKeys = ['accessToken', 'access_token', 'token', 'jwt']
    for (const key of possibleTokenKeys) {
      if ((session as any)?.[key]) {
        return (session as any)[key]
      }
    }
    
    // 세션에 없으면 localStorage에서 확인
    const localToken = localStorage.getItem('access_token')
    
    // localStorage의 다른 키들도 확인
    const localKeys = ['token', 'jwt', 'accessToken']
    for (const key of localKeys) {
      const token = localStorage.getItem(key)
      if (token) {
        return token
      }
    }
    
    return localToken
  }

  // 기본 정보 폼 상태
  const [basicInfo, setBasicInfo] = useState({
    name: '',
    age: '',
    nationality: ''
  })
  const [isUpdatingBasicInfo, setIsUpdatingBasicInfo] = useState(false)

  // 여행 취향 폼 상태
  const [travelPreferences, setTravelPreferences] = useState({
    persona: '',
    priority: '',
    accommodation: '',
    exploration: ''
  })
  const [isUpdatingPreferences, setIsUpdatingPreferences] = useState(false)

  // 사용자 프로필 데이터 상태
  const [userProfile, setUserProfile] = useState<any>(null)
  const [isLoadingProfile, setIsLoadingProfile] = useState(false)

  // 포스트 수정 관련 상태
  const [editingPost, setEditingPost] = useState<Post | null>(null)
  const [editCaption, setEditCaption] = useState('')
  const [editLocation, setEditLocation] = useState('')
  const [editImage, setEditImage] = useState<string | null>(null)
  const [isUpdatingPost, setIsUpdatingPost] = useState(false)
  const editFileInputRef = useRef<HTMLInputElement>(null)

  // 여행 삭제 관련 상태
  const [deletingTripId, setDeletingTripId] = useState<number | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  // 포스트 삭제 확인 모달 상태
  const [deletingPostId, setDeletingPostId] = useState<number | null>(null)
  const [showPostDeleteModal, setShowPostDeleteModal] = useState(false)

  // 저장된 장소 삭제 확인 모달 상태
  const [deletingSavedLocationId, setDeletingSavedLocationId] = useState<number | null>(null)
  const [showSavedLocationDeleteModal, setShowSavedLocationDeleteModal] = useState(false)

  // 토스트 메시지 상태
  const [toast, setToast] = useState<{
    show: boolean
    message: string
    type: 'success' | 'error' | 'info'
  }>({
    show: false,
    message: '',
    type: 'info'
  })

  const router = useRouter()
  const { data: session, status } = useSession()

  // 토스트 메시지 함수들
  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ show: true, message, type })
    setTimeout(() => {
      setToast({ show: false, message: '', type: 'info' })
    }, 2000) // 3초 후 자동 사라짐
  }

  const hideToast = () => {
    setToast({ show: false, message: '', type: 'info' })
  }

  // 사용자 프로필 정보 가져오기
  const fetchUserProfile = useCallback(async () => {
    setIsLoadingProfile(true)
    try {
      const token = getToken()
      
      if (!token) {
        return
      }
      
      const headers: any = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }

      const response = await fetch('/api/proxy/api/v1/profile/me', {
        headers: headers
      })

      if (response.ok) {
        const profileData = await response.json()
        setUserProfile(profileData)
        
        // 여행 취향 정보가 있으면 상태에 설정
        if (profileData.persona || profileData.priority || profileData.accommodation || profileData.exploration) {
          setTravelPreferences({
            persona: profileData.persona || '',
            priority: profileData.priority || '',
            accommodation: profileData.accommodation || '',
            exploration: profileData.exploration || ''
          })
        }
      } else {
        const errorData = await response.json()
        console.error('프로필 정보 가져오기 실패:', errorData)
      }
    } catch (error) {
      console.error('프로필 정보 가져오기 오류:', error)
    } finally {
      setIsLoadingProfile(false)
    }
  }, [session])

  // 사용자 게시글 가져오기
  const fetchUserPosts = useCallback(async () => {
    setPostsLoading(true)
    try {
      const token = getToken()
      
      if (!token) {
        return
      }
      
      const response = await fetch('/api/proxy/api/v1/posts/', {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        const data = await response.json()
        // 현재 사용자의 게시글만 필터링
        const userPosts = data.posts.filter((post: Post) => post.user_id === session?.user?.id)
        setPosts(userPosts)
      } else {
        console.error('게시글 가져오기 실패')
        setPosts([])
      }
    } catch (error) {
      console.error('게시글 가져오기 오류:', error)
      setPosts([])
    } finally {
      setPostsLoading(false)
    }
  }, [session])

  // 저장된 장소 로딩 함수
  const loadSavedLocations = useCallback(async () => {
    try {
      setSavedLoading(true)
      const token = getToken()
      
      if (!token) {
        return
      }
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/saved-locations/`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        const savedLocationIds = data.locations || []
        
        // 저장된 장소 ID들이 있으면 실제 장소 정보 가져오기
        if (savedLocationIds.length > 0) {
          const enrichedLocations = await Promise.all(
            savedLocationIds.map(async (savedLocation: any) => {
              try {
                // places 필드에서 table_name:table_id 파싱
                const places = savedLocation.places
                if (!places || !places.includes(':')) {
                  console.error('Invalid places format:', places)
                  return null
                }
                
                const [tableName, tableId] = places.split(':')
                
                // table_name과 table_id로 실제 장소 정보 가져오기
                const attractionResponse = await fetch(
                  `${API_BASE_URL}/api/v1/attractions/${tableName}/${tableId}`
                )
                
                if (attractionResponse.ok) {
                  const attractionData = await attractionResponse.json()
                  
                  // 실제 장소 정보와 저장된 장소 정보 결합
                  return {
                    id: savedLocation.id,
                    places: savedLocation.places,
                    name: attractionData.name || '이름 없음',
                    address: attractionData.address || attractionData.location || '주소 정보 없음',
                    image: attractionData.imageUrl || attractionData.image,
                    imageUrl: attractionData.imageUrl || attractionData.image,
                    description: attractionData.description || attractionData.address,
                    category: attractionData.category,
                    rating: attractionData.rating,
                    latitude: attractionData.latitude,
                    longitude: attractionData.longitude,
                    created_at: savedLocation.created_at
                  }
                }
              } catch (error) {
                console.error(`장소 ${savedLocation.places} 정보 가져오기 실패:`, error)
              }
              
              return null
            })
          ).then(results => results.filter(Boolean)) // null 값 제거
          
          setSavedLocations(enrichedLocations)
        } else {
          setSavedLocations([])
        }
      } else {
        console.error('저장된 장소 로딩 실패:', response.status)
        setSavedLocations([])
      }
    } catch (error) {
      console.error('저장된 장소 로딩 중 오류:', error)
      setSavedLocations([])
    } finally {
      setSavedLoading(false)
    }
  }, [session])

  // 여행 목록 로딩 함수
  const loadTrips = useCallback(async () => {
    try {
      setTripsLoading(true)
      const token = getToken()
      
      if (!token) {
        return
      }
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/trips/`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        const trips = data.trips || []
        setTrips(trips)
      } else {
        console.error('여행 목록 로딩 실패:', response.status)
      }
    } catch (error) {
      console.error('여행 목록 로딩 중 오류:', error)
    } finally {
      setTripsLoading(false)
    }
  }, [session])

  // 로그인하지 않은 사용자는 로그인 페이지로 리다이렉트
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/auth/login')
    }
  }, [status, router])

  // 세션이 있을 때 프로필 정보와 게시글 가져오기
  useEffect(() => {
    if (status === 'loading') {
      return
    }
    
    if (status === 'unauthenticated') {
      return
    }
    
    if (session && status === 'authenticated') {
      // 각 함수를 직접 호출하여 최신 session과 status 사용
      const loadData = async () => {
        await fetchUserProfile() // 프로필 정보에 여행 취향도 포함됨
        await fetchUserPosts()
        await loadSavedLocations()
        await loadTrips()
      }
      
      loadData()
    }
  }, [session, status])

  // 세션에서 초기 폼 데이터 설정
  useEffect(() => {
    if (session?.user) {
      setBasicInfo({
        name: session.user.name || '',
        age: (session.user as any).age || '',
        nationality: (session.user as any).nationality || ''
      })
    }
  }, [session])

  // 로딩 중이면 로딩 화면 표시
  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-400">프로필을 불러오는 중...</p>
        </div>
      </div>
    )
  }

  // 로그인하지 않은 경우 아무것도 렌더링하지 않음 (리다이렉트 처리됨)
  if (!session) {
    return null
  }

  // 이미지 파일 선택 핸들러
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

  // 프로필 이미지 업로드
  const handleProfileImageUpload = async () => {
    if (!selectedImage || !session?.user?.id) {
      showToast('업로드 취소: 이미지 또는 세션 없음', 'error')
      return
    }

    setIsUploadingImage(true)
    try {
      const headers: any = {
        'Content-Type': 'application/json',
      }

      // 백엔드 토큰이 있으면 Authorization 헤더 추가
      if ((session as any)?.backendToken) {
        headers['Authorization'] = `Bearer ${(session as any).backendToken}`
      }

      const response = await fetch('/api/proxy/api/v1/profile/image', {
        method: 'PUT',
        headers: headers,
        body: JSON.stringify({
          image_data: selectedImage
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '프로필 이미지 업로드 실패')
      }

      const result = await response.json()

      showToast('프로필 이미지가 업데이트되었습니다!', 'success')
      setSelectedImage(null)

      // 프로필 데이터 다시 가져오기 (페이지 새로고침 없이)
      await fetchUserProfile()
    } catch (error: any) {
      console.error('프로필 이미지 업데이트 오류:', error)
      showToast(`이미지 업데이트에 실패했습니다: ${error.message}`, 'error')
    } finally {
      setIsUploadingImage(false)
    }
  }

  // 기본 정보 업데이트
  const handleBasicInfoUpdate = async () => {
    setIsUpdatingBasicInfo(true)
    try {
      const headers: any = {
        'Content-Type': 'application/json',
      }

      if ((session as any)?.backendToken) {
        headers['Authorization'] = `Bearer ${(session as any).backendToken}`
      }

      const response = await fetch('/api/proxy/api/v1/profile/info', {
        method: 'PUT',
        headers: headers,
        body: JSON.stringify({
          name: basicInfo.name || null,
          age: basicInfo.age ? parseInt(basicInfo.age) : null,
          nationality: basicInfo.nationality || null
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '기본 정보 업데이트 실패')
      }

      const result = await response.json()
      console.log('기본 정보 업데이트 성공:', result)
      showToast('기본 정보가 업데이트되었습니다!', 'success')

    } catch (error: any) {
      console.error('기본 정보 업데이트 오류:', error)
      showToast(`기본 정보 업데이트에 실패했습니다: ${error.message}`, 'error')
    } finally {
      setIsUpdatingBasicInfo(false)
    }
  }

  // 여행 취향 업데이트
  const handleTravelPreferencesUpdate = async () => {
    setIsUpdatingPreferences(true)
    try {
      const headers: any = {
        'Content-Type': 'application/json',
      }

      if ((session as any)?.backendToken) {
        headers['Authorization'] = `Bearer ${(session as any).backendToken}`
      }

      const response = await fetch('/api/proxy/api/v1/profile/preferences', {
        method: 'PUT',
        headers: headers,
        body: JSON.stringify({
          persona: travelPreferences.persona || null,
          priority: travelPreferences.priority || null,
          accommodation: travelPreferences.accommodation || null,
          exploration: travelPreferences.exploration || null
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '여행 취향 업데이트 실패')
      }

      const result = await response.json()
      showToast('여행 취향이 업데이트되었습니다!', 'success')

      // 프로필 정보 다시 가져오기 (여행 취향 정보 포함)
      await fetchUserProfile()

    } catch (error: any) {
      console.error('여행 취향 업데이트 오류:', error)
      showToast(`여행 취향 업데이트에 실패했습니다: ${error.message}`, 'error')
    } finally {
      setIsUpdatingPreferences(false)
    }
  }

  // 포스트 수정 시작
  const handleEditPost = (post: Post) => {
    setEditingPost(post)
    setEditCaption(post.caption)
    setEditLocation(post.location || '')
    setEditImage(null)
  }

  // 포스트 수정 취소
  const handleCancelEdit = () => {
    setEditingPost(null)
    setEditCaption('')
    setEditLocation('')
    setEditImage(null)
  }

  // 포스트 수정용 이미지 선택
  const handleEditImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        setEditImage(e.target?.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  // 포스트 수정 저장
  const handleSavePost = async () => {
    if (!editingPost || !session) return

    setIsUpdatingPost(true)
    try {
      const headers: any = {
        'Content-Type': 'application/json',
      }

      if ((session as any)?.backendToken) {
        headers['Authorization'] = `Bearer ${(session as any).backendToken}`
      }

      const updateData: any = {
        caption: editCaption,
        location: editLocation
      }

      // 새로운 이미지가 선택된 경우에만 image_data 포함
      if (editImage) {
        updateData.image_data = editImage
      }

      const response = await fetch(`/api/proxy/api/v1/posts/${editingPost.id}`, {
        method: 'PUT',
        headers: headers,
        body: JSON.stringify(updateData)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '포스트 수정 실패')
      }

      const updatedPost = await response.json()

      // 포스트 목록 업데이트
      setPosts(prevPosts =>
        prevPosts.map(post =>
          post.id === updatedPost.id ? updatedPost : post
        )
      )

      showToast('포스트가 수정되었습니다!', 'success')
      handleCancelEdit()

    } catch (error: any) {
      console.error('포스트 수정 오류:', error)
      showToast(`포스트 수정에 실패했습니다: ${error.message}`, 'error')
    } finally {
      setIsUpdatingPost(false)
    }
  }

  // 포스트 삭제 확인 함수
  const confirmDeletePost = (postId: number) => {
    setDeletingPostId(postId)
    setShowPostDeleteModal(true)
  }

  // 포스트 삭제 실행 함수
  const executeDeletePost = async () => {
    if (!deletingPostId || !session) return

    try {
      const headers: any = {
        'Content-Type': 'application/json',
      }

      if ((session as any)?.backendToken) {
        headers['Authorization'] = `Bearer ${(session as any).backendToken}`
      }

      const response = await fetch(`/api/proxy/api/v1/posts/${deletingPostId}`, {
        method: 'DELETE',
        headers: headers
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '포스트 삭제 실패')
      }

      // 포스트 목록에서 제거
      setPosts(prevPosts => prevPosts.filter(post => post.id !== deletingPostId))
      showToast('포스트가 삭제되었습니다!', 'success')

    } catch (error: any) {
      console.error('포스트 삭제 오류:', error)
      showToast(`포스트 삭제에 실패했습니다: ${error.message}`, 'error')
    } finally {
      setShowPostDeleteModal(false)
      setDeletingPostId(null)
    }
  }

  // 포스트 삭제 취소 함수
  const cancelDeletePost = () => {
    setShowPostDeleteModal(false)
    setDeletingPostId(null)
  }

  // 로그아웃 핸들러
  const handleLogout = async () => {
    try {
      await signOut({
        callbackUrl: '/', // 로그아웃 후 메인 페이지로 이동
        redirect: true
      })
    } catch (error) {
      console.error('로그아웃 오류:', error)
    }
  }

  // 여행 카드 클릭 핸들러 (보기 모드)
  const handleTripClick = (trip: Trip) => {
    if (!trip.places || trip.places.length === 0) {
      showToast('이 여행에는 저장된 장소가 없습니다.', 'info')
      return
    }

    // DB 구조에 맞게 데이터 변환: table_name + "_" + id 형태로 조합
    const placeIds = trip.places.map(place => `${place.table_name}_${place.id}`)
    const dayNumbers = trip.places.map(place => place.dayNumber.toString())
    const sourceTables = trip.places.map(place => place.table_name)
    
    // 잠금 상태 정보 (전체 식별자_dayNumber 형태로 잠금된 장소들의 키)
    const lockedPlaceKeys = trip.places
      .filter(place => place.isLocked)
      .map(place => `${place.table_name}_${place.id}_${place.dayNumber}`)
    
    // 안전한 날짜 생성 및 포맷팅 함수
    const createSafeDate = (dateString: string) => {
      if (!dateString) return null
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
        const [year, month, day] = dateString.split('-').map(Number)
        return new Date(year, month - 1, day)
      }
      const date = new Date(dateString)
      return isNaN(date.getTime()) ? null : date
    }
    
    const formatDateForURL = (date: Date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    // 날짜 처리
    const startDate = createSafeDate(trip.start_date)
    const endDate = createSafeDate(trip.end_date)
    
    if (!startDate || !endDate) {
      console.error('Invalid date format:', trip.start_date, trip.end_date)
      return
    }
    
    const daysDiff = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)) + 1
    
    // URL 파라미터 생성 (보기 모드)
    const params = new URLSearchParams({
      places: placeIds.join(','),
      dayNumbers: dayNumbers.join(','),
      sourceTables: sourceTables.join(','),
      startDate: formatDateForURL(startDate),
      endDate: formatDateForURL(endDate),
      days: daysDiff.toString(),
      baseAttraction: 'general',
      source: 'profile',
      tripTitle: trip.title,
      tripDescription: trip.description || '',
      tripId: trip.id.toString(),
      ...(lockedPlaceKeys.length > 0 && { lockedPlaces: lockedPlaceKeys.join(',') })
    })
    
    // map 페이지로 이동 (보기 모드 - long press 불가)
    router.push(`/map?${params.toString()}`)
  }

  // 여행 편집 버튼 클릭 핸들러 (편집 모드)
  const handleEditTripClick = (trip: Trip) => {
    if (!trip.places || trip.places.length === 0) {
      showToast('이 여행에는 저장된 장소가 없습니다.', 'info')
      return
    }

    // DB 구조에 맞게 데이터 변환: table_name + "_" + id 형태로 조합
    const placeIds = trip.places.map(place => `${place.table_name}_${place.id}`)
    const dayNumbers = trip.places.map(place => place.dayNumber.toString())
    const sourceTables = trip.places.map(place => place.table_name)
    
    // 잠금 상태 정보 (전체 식별자_dayNumber 형태로 잠금된 장소들의 키)
    const lockedPlaceKeys = trip.places
      .filter(place => place.isLocked)
      .map(place => `${place.table_name}_${place.id}_${place.dayNumber}`)
    
    // 안전한 날짜 생성 및 포맷팅 함수 (동일한 로직)
    const createSafeDate = (dateString: string) => {
      if (!dateString) return null
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
        const [year, month, day] = dateString.split('-').map(Number)
        return new Date(year, month - 1, day)
      }
      const date = new Date(dateString)
      return isNaN(date.getTime()) ? null : date
    }
    
    const formatDateForURL = (date: Date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    // 날짜 처리
    const startDate = createSafeDate(trip.start_date)
    const endDate = createSafeDate(trip.end_date)
    
    if (!startDate || !endDate) {
      console.error('Invalid date format:', trip.start_date, trip.end_date)
      return
    }
    
    const daysDiff = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)) + 1
    
    // URL 파라미터 생성 (편집 모드)
    const params = new URLSearchParams({
      places: placeIds.join(','),
      dayNumbers: dayNumbers.join(','),
      sourceTables: sourceTables.join(','),
      startDate: formatDateForURL(startDate),
      endDate: formatDateForURL(endDate),
      days: daysDiff.toString(),
      baseAttraction: 'general',
      source: 'profile',
      tripTitle: trip.title,
      tripDescription: trip.description || '',
      tripId: trip.id.toString(),
      editMode: 'true', // 편집 모드 플래그 추가
      ...(lockedPlaceKeys.length > 0 && { lockedPlaces: lockedPlaceKeys.join(',') })
    })
    
    // map 페이지로 이동 (편집 모드 - long press 가능)
    router.push(`/map?${params.toString()}`)
  }

  // 날짜 포맷 함수
  const formatDateRange = (startDate: string, endDate: string) => {
    // 안전한 날짜 생성 함수
    const createSafeDate = (dateString: string) => {
      if (!dateString) return null
      
      // YYYY-MM-DD 형식인 경우 로컬 시간으로 생성
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
        const [year, month, day] = dateString.split('-').map(Number)
        return new Date(year, month - 1, day)
      }
      
      // 다른 형식인 경우 기본 Date 생성자 사용
      const date = new Date(dateString)
      return isNaN(date.getTime()) ? null : date
    }
    
    const start = createSafeDate(startDate)
    const end = createSafeDate(endDate)
    
    if (!start || !end) {
      return '날짜 정보 없음'
    }
    
    const formatDate = (date: Date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const weekdays = ['일', '월', '화', '수', '목', '금', '토']
      const weekday = weekdays[date.getDay()]
      
      return `${year}.${month}.${day}(${weekday})`
    }
    
    return `${formatDate(start)} - ${formatDate(end)}`
  }



  // 저장된 장소 삭제 확인 함수
  const confirmDeleteSavedLocation = (locationId: number) => {
    setDeletingSavedLocationId(locationId)
    setShowSavedLocationDeleteModal(true)
  }

  // 저장된 장소 삭제 실행 함수
  const executeDeleteSavedLocation = async () => {
    if (!deletingSavedLocationId) return

    try {
      const token = getToken()
      
      if (!token) {
        showToast('로그인이 필요합니다.', 'error')
        return
      }
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/saved-locations/${deletingSavedLocationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        // 삭제 성공 시 목록에서 해당 장소 제거
        setSavedLocations(prev => prev.filter(location => location.id !== deletingSavedLocationId))
        showToast('저장된 장소가 삭제되었습니다.', 'success')
      } else {
        showToast('삭제에 실패했습니다.', 'error')
      }
    } catch (error) {
      console.error('저장된 장소 삭제 중 오류:', error)
      showToast('삭제 중 오류가 발생했습니다.', 'error')
    } finally {
      setShowSavedLocationDeleteModal(false)
      setDeletingSavedLocationId(null)
    }
  }

  // 저장된 장소 삭제 취소 함수
  const cancelDeleteSavedLocation = () => {
    setShowSavedLocationDeleteModal(false)
    setDeletingSavedLocationId(null)
  }

  // 저장된 장소 클릭 핸들러
  const handleSavedLocationClick = (location: any) => {
    // places 필드에서 table_name:table_id 파싱
    const [tableName, id] = location.places.split(':')
    
    // attraction 페이지에서 지원하는 모든 카테고리
    const supportedCategories = [
      'attractions', 'nature', 'restaurants', 'shopping', 
      'accommodation', 'humanities', 'leisure_sports'
    ]
    
    if (supportedCategories.includes(tableName)) {
      router.push(`/attraction/${tableName}_${id}`)
    } else {
      showToast('해당 장소의 상세 정보를 찾을 수 없습니다.', 'error')
    }
  }

  // 여행 삭제 함수
  const handleDeleteTrip = async (tripId: number) => {
    try {
      const token = getToken()
      
      if (!token) {
        showToast('로그인이 필요합니다.', 'error')
        return
      }
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/trips/${tripId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        // 삭제 성공 시 목록에서 해당 여행 제거
        setTrips(prev => prev.filter(trip => trip.id !== tripId))
        showToast('여행 일정이 삭제되었습니다.', 'success')
      } else {
        showToast('삭제에 실패했습니다.', 'error')
      }
    } catch (error) {
      console.error('여행 삭제 중 오류:', error)
      showToast('삭제 중 오류가 발생했습니다.', 'error')
    }
  }

  // 여행 삭제 확인 함수
  const confirmDeleteTrip = (tripId: number) => {
    setDeletingTripId(tripId)
    setShowDeleteModal(true)
  }

  // 여행 삭제 실행 함수
  const executeDeleteTrip = async () => {
    if (deletingTripId) {
      await handleDeleteTrip(deletingTripId)
      setShowDeleteModal(false)
      setDeletingTripId(null)
    }
  }

  // 여행 삭제 취소 함수
  const cancelDeleteTrip = () => {
    setShowDeleteModal(false)
    setDeletingTripId(null)
  }

  // 카테고리 한국어 변환 함수
  const getCategoryName = (category: string): string => {
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


  const renderTabContent = () => {
    switch (activeTab) {
      case 'trips':
        if (tripsLoading) {
          return (
            <div className="flex justify-center items-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
              <span className="ml-2 text-gray-400">여행 목록을 불러오는 중...</span>
            </div>
          )
        }
        
        if (trips.length === 0) {
          return (
            <div className="text-center py-8">
              <div className="text-6xl mb-4">✈️</div>
              <p className="text-gray-400 text-lg mb-2">계획된 여행이 없습니다</p>
              <p className="text-gray-500 text-sm">새로운 여행을 계획해보세요!</p>
            </div>
          )
        }
        
        return (
          <div className="space-y-4">
            {trips.map((trip) => (
              <div 
                key={trip.id} 
                className="bg-gray-800 p-4 rounded-2xl relative cursor-pointer hover:bg-gray-750 transition-colors"
                onClick={() => handleTripClick(trip)}
              >
                {/* 상태 표시와 버튼들 - 오른쪽 상단 */}
                <div className="absolute top-4 right-4 flex items-center space-x-2">
                  <span className={`px-2 py-1 rounded-full text-xs flex items-center text-white ${
                    getTripStatus(trip.start_date, trip.end_date) === 'active' ? 'bg-red-500' :
                    getTripStatus(trip.start_date, trip.end_date) === 'completed' ? 'bg-gray-500' :
                    'bg-green-500'
                  }`}>
                    {getTripStatus(trip.start_date, trip.end_date) === 'planned' && '📋 준비중'}
                    {getTripStatus(trip.start_date, trip.end_date) === 'active' && '🗺️ 여행중'}
                    {getTripStatus(trip.start_date, trip.end_date) === 'completed' && '👣 발자취'}
                  </span>
                  
                  {/* 휴지통 버튼 */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation() // 카드 클릭 이벤트 방지
                      confirmDeleteTrip(trip.id)
                    }}
                    className="text-red-400 hover:text-red-300 transition-colors p-1 hover:bg-red-900 rounded"
                    title="일정 삭제"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
                
                {/* 여행 제목 */}
                <div className="mb-3">
                  <h3 className="text-white text-lg font-semibold mb-1">{trip.title}</h3>
                  <div className="flex items-center text-sm text-gray-400">
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <span>{formatDateRange(trip.start_date, trip.end_date)}</span>
                  </div>
                </div>

                {/* 설명 */}
                {trip.description && (
                  <p className="text-gray-300 text-sm mb-3">{trip.description}</p>
                )}

                {/* 방문 장소 */}
                {trip.places && trip.places.length > 0 && (
                  <div className="mb-3">
                    <div className="flex items-center mb-2">
                      <svg className="w-4 h-4 mr-1 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span className="text-sm text-gray-400">방문 장소</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {trip.places.slice(0, 3).map((place, index) => (
                        <span key={index} className="inline-flex items-center text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                          <span className="w-4 h-4 mr-1 flex items-center justify-center bg-blue-500 text-white rounded-full text-xs font-bold">
                            {place.order}
                          </span>
                          {place.name}
                        </span>
                      ))}
                      {trip.places.length > 3 && (
                        <span className="text-xs text-gray-400 flex items-center">
                          +{trip.places.length - 3}개 더
                        </span>
                      )}
                    </div>
                  </div>
                )}

              </div>
            ))}
          </div>
        )

      case 'posts':
        if (postsLoading) {
          return (
            <div className="flex justify-center items-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
              <span className="ml-2 text-gray-400">게시글을 불러오는 중...</span>
            </div>
          )
        }

        if (posts.length === 0) {
          return (
            <div className="text-center py-8">
              <p className="text-gray-400">작성한 게시글이 없습니다.</p>
              <Link href="/feed/create">
                <button className="mt-4 px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors">
                  첫 게시글 작성하기
                </button>
              </Link>
            </div>
          )
        }

        return (
          <div className="space-y-4">
            {posts.map((post) => (
              <div key={post.id} className="bg-gray-800 p-4 rounded-2xl">
                {/* 이미지가 있으면 표시 */}
                {post.image_url && (
                  <div className="mb-3 rounded-lg overflow-hidden">
                    <img
                      src={post.image_url}
                      alt="Post image"
                      className="w-full h-48 object-cover"
                    />
                  </div>
                )}

                <p className="text-white text-base mb-3">{post.caption}</p>

                {/* 위치 정보가 있으면 표시 */}
                {post.location && (
                  <div className="flex items-center mb-2 text-sm text-gray-400">
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span>{post.location}</span>
                  </div>
                )}

                <div className="flex items-center justify-between text-sm text-gray-400">
                  <span>{new Date(post.created_at).toLocaleDateString('ko-KR')}</span>
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-1">
                      <span>❤️</span>
                      <span>{post.likes_count}</span>
                    </div>
                    {/* <div className="flex items-center space-x-1">
                      <span>💬</span>
                      <span>{post.comments_count}</span>
                    </div> */}
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleEditPost(post)}
                        className="text-blue-400 hover:text-blue-300 transition-colors"
                        title="수정"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => confirmDeletePost(post.id)}
                        className="text-red-400 hover:text-red-300 transition-colors"
                        title="삭제"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )

      case 'saved':
        return (
          <div className="space-y-4">
            {savedLoading ? (
              <div className="flex justify-center items-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
              </div>
            ) : savedLocations.length === 0 ? (
              <div className="text-center py-8">
                <div className="text-6xl mb-4">📍</div>
                <p className="text-gray-400 text-lg mb-2">저장된 장소가 없습니다</p>
                <p className="text-gray-500 text-sm">관심있는 장소를 북마크해보세요!</p>
              </div>
            ) : (
              savedLocations.map((location) => (
                <div key={location.id} className="bg-gray-800 overflow-hidden">
                  <div className="flex h-24 cursor-pointer hover:bg-gray-700 transition-colors" onClick={() => handleSavedLocationClick(location)}>
                    {/* 썸네일 이미지 */}
                    <div className="w-24 h-24 flex-shrink-0 bg-gray-700">
                      {(location.image || location.imageUrl) ? (
                        <img 
                          src={location.image || location.imageUrl} 
                          alt={location.name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            // 이미지 로드 실패시 기본 이미지 표시
                            e.currentTarget.style.display = 'none';
                            e.currentTarget.parentElement!.innerHTML = `
                              <div class="w-full h-full flex items-center justify-center text-gray-500">
                                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                              </div>
                            `;
                          }}
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-500">
                          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                      )}
                    </div>
                    
                    {/* 콘텐츠 영역 */}
                    <div className="flex-1 p-3 flex items-center justify-between min-w-0">
                      <div className="flex-1 min-w-0 pr-2">
                        <h3 className="text-white font-semibold mb-0.5 truncate text-sm">{location.name}</h3>
                        <p className="text-gray-300 text-xs mb-1 truncate">
                          {location.address || '주소 정보 없음'}
                        </p>
                        
                        {/* 카테고리와 평점, 날짜 */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            {location.category && (
                              <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-1 rounded-full">
                                {getCategoryName(location.category)}
                              </span>
                            )}
                            {location.rating && (
                              <div className="flex items-center">
                                <svg className="w-3 h-3 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                <span className="text-yellow-400 text-xs font-medium">{location.rating}</span>
                              </div>
                            )}
                          </div>
                          
                          <p className="text-gray-400 text-xs">
                            {(() => {
                              const date = new Date(location.created_at)
                              const year = date.getFullYear().toString().slice(-2)
                              const month = String(date.getMonth() + 1).padStart(2, '0')
                              const day = String(date.getDate()).padStart(2, '0')
                              return `${year}.${month}.${day}에 저장`
                            })()}
                          </p>
                        </div>
                      </div>
                      
                      {/* 삭제 버튼 */}
                      <button 
                        onClick={(e) => {
                          e.stopPropagation()
                          confirmDeleteSavedLocation(location.id)
                        }}
                        className="text-red-400 hover:text-red-300 transition-colors p-1 flex-shrink-0"
                        title="저장된 장소 삭제"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="relative p-4">
        <button
          onClick={() => router.back()}
          className="absolute left-4 top-4 text-blue-400 text-2xl"
        >
          ‹
        </button>
      </div>

      {/* Profile Section */}
      <div className="flex flex-col items-center px-4 pb-8">
        <div className="relative w-24 h-24 mb-4">
          <div className="w-full h-full rounded-full bg-gray-300 overflow-hidden">
            {selectedImage ? (
              <img
                src={selectedImage}
                alt="Selected Profile"
                className="w-full h-full object-cover"
              />
            ) : userProfile?.profile_image ? (
              <img
                src={userProfile.profile_image}
                alt="Profile"
                className="w-full h-full object-cover"
              />
            ) : session.user?.image ? (
              <img
                src={session.user.image}
                alt="Profile"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-blue-500 text-white text-2xl font-bold">
                {(session.user?.name || session.user?.email || 'U')[0].toUpperCase()}
              </div>
            )}
          </div>

          {/* 카메라 아이콘 - 편집 모드일 때 오른쪽 하단에 표시 (프로필 사진 위에) */}
          {isEditing && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="absolute -bottom-1 -right-1 bg-blue-500 hover:bg-blue-600 text-white rounded-full p-2 transition-colors shadow-lg"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          )}
        </div>

        {/* 이미지 선택 후 업로드 버튼 - 편집 모드일 때만 표시 */}
        {selectedImage && isEditing && (
          <div className="flex space-x-2 mb-4">
            <button
              onClick={handleProfileImageUpload}
              disabled={isUploadingImage}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
            >
              {isUploadingImage ? '업로드 중...' : '저장'}
            </button>
            <button
              onClick={() => setSelectedImage(null)}
              className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600"
            >
              취소
            </button>
          </div>
        )}

        {/* 숨겨진 파일 입력 */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleImageSelect}
          className="hidden"
        />

        <h1 className="text-2xl font-bold text-blue-400 mb-2">
          {session.user?.name || session.user?.email || '사용자'}
        </h1>

        <div className="flex items-center space-x-1 mb-6">
          <span className="text-green-400">🍃</span>
          <span className="text-green-400 font-semibold">555</span>
        </div>

        {/* 편집 모드 토글 버튼 */}
        <button
          onClick={() => {
            setIsEditing(!isEditing)
            // 편집 모드 종료시 선택된 이미지 초기화
            if (isEditing) {
              setSelectedImage(null)
            }
          }}
          className="w-64 bg-gray-200 text-gray-800 py-3 rounded-2xl font-medium hover:bg-gray-100 transition-colors mb-4"
        >
          {isEditing ? '편집 완료' : '프로필 편집'}
        </button>

        {/* 기본정보/여행취향 탭 (편집 모드일 때만 표시) */}
        {isEditing && (
          <div className="w-full max-w-sm mb-6">
            <div className="flex space-x-2 bg-gray-800 p-1 rounded-xl">
              <button
                onClick={() => setEditTab('basic')}
                className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${editTab === 'basic'
                    ? 'bg-blue-500 text-white'
                    : 'text-gray-300 hover:text-white'
                  }`}
              >
                기본정보
              </button>
              <button
                onClick={() => setEditTab('travel')}
                className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${editTab === 'travel'
                    ? 'bg-blue-500 text-white'
                    : 'text-gray-300 hover:text-white'
                  }`}
              >
                여행취향
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 편집 모드 콘텐츠 */}
      {isEditing && (
        <div className="px-4 mb-8">
          {editTab === 'basic' ? (
            <div className="bg-gray-800 p-6 rounded-2xl">
              <h3 className="text-lg font-semibold text-white mb-4">기본정보</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">이름</label>
                  <input
                    type="text"
                    value={basicInfo.name}
                    onChange={(e) => setBasicInfo({ ...basicInfo, name: e.target.value })}
                    className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white"
                    placeholder="이름을 입력하세요"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">이메일</label>
                  <input
                    type="email"
                    value={session.user?.email || ''}
                    className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white"
                    placeholder="이메일을 입력하세요"
                    disabled
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">나이</label>
                  <input
                    type="number"
                    value={basicInfo.age}
                    onChange={(e) => setBasicInfo({ ...basicInfo, age: e.target.value })}
                    className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white"
                    placeholder="나이를 입력하세요"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">국적</label>
                  <input
                    type="text"
                    value={basicInfo.nationality}
                    onChange={(e) => setBasicInfo({ ...basicInfo, nationality: e.target.value })}
                    className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white"
                    placeholder="국적을 입력하세요"
                  />
                </div>
                <button
                  onClick={handleBasicInfoUpdate}
                  disabled={isUpdatingBasicInfo}
                  className="w-full mt-6 bg-blue-500 text-white py-3 rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
                >
                  {isUpdatingBasicInfo ? '업데이트 중...' : '기본정보 저장'}
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-gray-800 p-6 rounded-2xl">
              <h3 className="text-lg font-semibold text-white mb-4">여행취향</h3>
              <div className="space-y-6">
                <div>
                  <label className="block text-sm text-gray-400 mb-3">여행 스타일</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: '럭셔리', value: 'luxury' },
                      { label: '모던', value: 'modern' },
                      { label: '자연활동', value: 'nature_activity' },
                      { label: '맛집탐방', value: 'foodie' }
                    ].map((style) => (
                      <button
                        key={style.value}
                        onClick={() => setTravelPreferences({ ...travelPreferences, persona: style.value })}
                        className={`p-3 border rounded-lg text-white transition-colors ${travelPreferences.persona === style.value
                            ? 'bg-blue-600 border-blue-500'
                            : 'bg-gray-700 border-gray-600 hover:bg-blue-600'
                          }`}
                      >
                        {style.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-3">여행 우선순위</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: '숙박', value: 'accommodation' },
                      { label: '맛집', value: 'restaurants' },
                      { label: '체험', value: 'experience' },
                      { label: '쇼핑', value: 'shopping' }
                    ].map((priority) => (
                      <button
                        key={priority.value}
                        onClick={() => setTravelPreferences({ ...travelPreferences, priority: priority.value })}
                        className={`p-3 border rounded-lg text-white transition-colors ${travelPreferences.priority === priority.value
                            ? 'bg-blue-600 border-blue-500'
                            : 'bg-gray-700 border-gray-600 hover:bg-blue-600'
                          }`}
                      >
                        {priority.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-3">숙박 스타일</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: '편안함', value: 'comfort' },
                      { label: '힐링', value: 'healing' },
                      { label: '전통', value: 'traditional' },
                      { label: '커뮤니티', value: 'community' }
                    ].map((accommodation) => (
                      <button
                        key={accommodation.value}
                        onClick={() => setTravelPreferences({ ...travelPreferences, accommodation: accommodation.value })}
                        className={`p-3 border rounded-lg text-white transition-colors ${travelPreferences.accommodation === accommodation.value
                            ? 'bg-blue-600 border-blue-500'
                            : 'bg-gray-700 border-gray-600 hover:bg-blue-600'
                          }`}
                      >
                        {accommodation.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-3">탐험 스타일</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: '핫플레이스', value: 'hot' },
                      { label: '로컬', value: 'local' },
                      { label: '밸런스', value: 'balance' },
                      { label: '진정한 경험', value: 'authentic_experience' }
                    ].map((exploration) => (
                      <button
                        key={exploration.value}
                        onClick={() => setTravelPreferences({ ...travelPreferences, exploration: exploration.value })}
                        className={`p-3 border rounded-lg text-white transition-colors ${travelPreferences.exploration === exploration.value
                            ? 'bg-blue-600 border-blue-500'
                            : 'bg-gray-700 border-gray-600 hover:bg-blue-600'
                          }`}
                      >
                        {exploration.label}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  onClick={handleTravelPreferencesUpdate}
                  disabled={isUpdatingPreferences}
                  className="w-full mt-6 bg-blue-500 text-white py-3 rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
                >
                  {isUpdatingPreferences ? '업데이트 중...' : '여행 취향 저장'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab Navigation - 프로필 편집 모드일 때 숨기기 */}
      {!isEditing && (
        <div className="px-4 mb-6">
          <div className="flex space-x-4">
            {(['trips', 'posts', 'saved'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 py-3 px-6 rounded-2xl font-medium transition-colors ${activeTab === tab
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-800 text-gray-300 border border-gray-700'
                  }`}
              >
                {tab === 'trips' ? 'Trips' :
                  tab === 'posts' ? 'Posts' :
                    'Saved'}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Tab Content - 프로필 편집 모드일 때 숨기기 */}
      {!isEditing && (
        <div className="px-4 pb-8">
          {renderTabContent()}
        </div>
      )}

      {/* Post Edit Modal */}
      {editingPost && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-2xl w-full max-w-md max-h-[80vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-white">포스트 수정</h3>
                <button
                  onClick={handleCancelEdit}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Current Image */}
              <div className="mb-4">
                <p className="text-sm text-gray-400 mb-2">현재 이미지</p>
                <div className="aspect-square rounded-lg overflow-hidden bg-gray-700">
                  <img
                    src={editImage || editingPost.image_url}
                    alt="Post image"
                    className="w-full h-full object-cover"
                  />
                </div>
              </div>

              {/* Image Change Button */}
              <div className="mb-4">
                <button
                  onClick={() => editFileInputRef.current?.click()}
                  className="w-full py-2 px-4 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                >
                  이미지 변경
                </button>
                <input
                  ref={editFileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleEditImageSelect}
                  className="hidden"
                />
              </div>

              {/* Caption */}
              <div className="mb-4">
                <label className="block text-sm text-gray-400 mb-2">설명</label>
                <textarea
                  value={editCaption}
                  onChange={(e) => setEditCaption(e.target.value)}
                  className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 resize-none"
                  rows={4}
                  placeholder="포스트에 대해 설명해주세요..."
                />
              </div>

              {/* Location */}
              <div className="mb-6">
                <label className="block text-sm text-gray-400 mb-2">위치 (선택사항)</label>
                <input
                  type="text"
                  value={editLocation}
                  onChange={(e) => setEditLocation(e.target.value)}
                  className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400"
                  placeholder="예: 서울특별시 강남구"
                />
              </div>

              {/* Buttons */}
              <div className="flex space-x-3">
                <button
                  onClick={handleCancelEdit}
                  className="flex-1 py-3 px-4 bg-gray-600 text-white rounded-lg hover:bg-gray-500 transition-colors"
                >
                  취소
                </button>
                <button
                  onClick={handleSavePost}
                  disabled={isUpdatingPost}
                  className="flex-1 py-3 px-4 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
                >
                  {isUpdatingPost ? '저장 중...' : '저장'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Trip Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="relative bg-[#0B1220] border border-[#1F3C7A]/50 rounded-2xl p-6 mx-4 max-w-sm w-full shadow-2xl">
            <div className="text-center">
              <div className="mx-auto w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">여행 일정 삭제 확인</h3>
              <p className="text-[#94A9C9] text-sm mb-6 leading-relaxed">
                여행 일정을 삭제하시겠습니까?<br/>
                <span className="text-[#6FA0E6] text-xs mt-2 block">삭제된 일정은 복구할 수 없습니다.</span>
              </p>
              <div className="flex space-x-3">
                <button
                  onClick={cancelDeleteTrip}
                  className="flex-1 py-2.5 px-4 bg-[#1F3C7A]/30 hover:bg-[#1F3C7A]/50 border border-[#1F3C7A]/50 hover:border-[#1F3C7A]/70 rounded-xl text-[#94A9C9] hover:text-white transition-all duration-200"
                >
                  취소
                </button>
                <button
                  onClick={executeDeleteTrip}
                  className="flex-1 py-2.5 px-4 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 hover:border-red-500/70 rounded-xl text-red-400 hover:text-red-300 transition-all duration-200 font-medium"
                >
                  삭제
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Post Delete Confirmation Modal */}
      {showPostDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="relative bg-[#0B1220] border border-[#1F3C7A]/50 rounded-2xl p-6 mx-4 max-w-sm w-full shadow-2xl">
            <div className="text-center">
              <div className="mx-auto w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">포스트 삭제 확인</h3>
              <p className="text-[#94A9C9] text-sm mb-6 leading-relaxed">
                포스트를 삭제하시겠습니까?<br/>
                <span className="text-[#6FA0E6] text-xs mt-2 block">삭제된 포스트는 복구할 수 없습니다.</span>
              </p>
              <div className="flex space-x-3">
                <button
                  onClick={cancelDeletePost}
                  className="flex-1 py-2.5 px-4 bg-[#1F3C7A]/30 hover:bg-[#1F3C7A]/50 border border-[#1F3C7A]/50 hover:border-[#1F3C7A]/70 rounded-xl text-[#94A9C9] hover:text-white transition-all duration-200"
                >
                  취소
                </button>
                <button
                  onClick={executeDeletePost}
                  className="flex-1 py-2.5 px-4 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 hover:border-red-500/70 rounded-xl text-red-400 hover:text-red-300 transition-all duration-200 font-medium"
                >
                  삭제
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Saved Location Delete Confirmation Modal */}
      {showSavedLocationDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="relative bg-[#0B1220] border border-[#1F3C7A]/50 rounded-2xl p-6 mx-4 max-w-sm w-full shadow-2xl">
            <div className="text-center">
              <div className="mx-auto w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">저장된 장소 삭제 확인</h3>
              <p className="text-[#94A9C9] text-sm mb-6 leading-relaxed">
                저장된 장소를 삭제하시겠습니까?<br/>
                <span className="text-[#6FA0E6] text-xs mt-2 block">삭제된 장소는 복구할 수 없습니다.</span>
              </p>
              <div className="flex space-x-3">
                <button
                  onClick={cancelDeleteSavedLocation}
                  className="flex-1 py-2.5 px-4 bg-[#1F3C7A]/30 hover:bg-[#1F3C7A]/50 border border-[#1F3C7A]/50 hover:border-[#1F3C7A]/70 rounded-xl text-[#94A9C9] hover:text-white transition-all duration-200"
                >
                  취소
                </button>
                <button
                  onClick={executeDeleteSavedLocation}
                  className="flex-1 py-2.5 px-4 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 hover:border-red-500/70 rounded-xl text-red-400 hover:text-red-300 transition-all duration-200 font-medium"
                >
                  삭제
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toast.show && (
        <div className="fixed top-4 left-4 right-4 z-50 flex justify-center">
          <div className={`
            flex items-center px-6 py-3 rounded-lg shadow-lg text-white font-medium max-w-sm
            transform transition-all duration-300 ease-in-out
            ${toast.type === 'success' ? 'bg-green-600' : 
              toast.type === 'error' ? 'bg-red-600' : 
              'bg-blue-600'}
            animate-in slide-in-from-top-4 fade-in
          `}>
            <div className="mr-3">
              {toast.type === 'success' && (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              )}
              {toast.type === 'error' && (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              {toast.type === 'info' && (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
            </div>
            <span className="flex-1 text-sm">{toast.message}</span>
            <button
              onClick={hideToast}
              className="ml-3 text-white hover:text-gray-200 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Logout Button at Bottom */}
      <div className="px-4 pb-8">
        <button
          onClick={handleLogout}
          className="w-full bg-red-500 text-white py-4 rounded-2xl font-medium hover:bg-red-600 transition-colors"
        >
          로그아웃
        </button>
      </div>
    </div>
  )
}