'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useSession, signOut } from 'next-auth/react'

interface TripCard {
  id: number
  title: string
  dates: string
  status: 'active' | 'completed' | 'planned'
  image?: string
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
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [isUploadingImage, setIsUploadingImage] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 토큰 가져오기 함수 (attraction 페이지와 동일)
  const getToken = () => {
    // 먼저 세션에서 토큰 확인
    if ((session as any)?.backendToken) {
      return (session as any).backendToken
    }
    // 세션에 없으면 localStorage에서 확인
    return localStorage.getItem('access_token')
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

  const router = useRouter()
  const { data: session, status } = useSession()

  // 사용자 프로필 정보 가져오기
  const fetchUserProfile = useCallback(async () => {
    if (!session) {
      console.log('fetchUserProfile: 세션 없음')
      return
    }

    console.log('=== fetchUserProfile 시작 ===')
    console.log('세션 상태:', session)
    console.log('백엔드 토큰:', (session as any)?.backendToken ? '있음' : '없음')

    setIsLoadingProfile(true)
    try {
      const headers: any = {
        'Content-Type': 'application/json',
      }

      if ((session as any)?.backendToken) {
        headers['Authorization'] = `Bearer ${(session as any).backendToken}`
        console.log('Authorization 헤더 추가됨')
      } else {
        console.log('경고: backendToken이 없음')
      }

      console.log('요청 헤더:', headers)

      const response = await fetch('/api/proxy/api/v1/profile/me', {
        headers: headers
      })

      console.log('응답 상태:', response.status)
      console.log('응답 OK:', response.ok)

      if (response.ok) {
        const profileData = await response.json()
        console.log('프로필 데이터:', profileData)
        setUserProfile(profileData)
      } else {
        const errorData = await response.json()
        console.error('프로필 정보 가져오기 실패:', errorData)
      }
    } catch (error) {
      console.error('프로필 정보 가져오기 오류:', error)
    } finally {
      setIsLoadingProfile(false)
      console.log('=== fetchUserProfile 완료 ===')
    }
  }, [session])

  // 사용자 게시글 가져오기
  const fetchUserPosts = useCallback(async () => {
    if (!session) return

    setPostsLoading(true)
    try {
      const response = await fetch('/api/proxy/api/v1/posts/', {
        headers: {
          'Content-Type': 'application/json',
        }
      })

      if (response.ok) {
        const data = await response.json()
        console.log('=== 사용자 게시글 필터링 디버그 ===')
        console.log('현재 세션 사용자 ID:', session.user?.id)
        console.log('현재 세션 사용자 이메일:', session.user?.email)
        console.log('전체 게시글 수:', data.posts?.length || 0)
        console.log('게시글 user_id 샘플:', data.posts?.[0]?.user_id)

        // 현재 사용자의 게시글만 필터링
        const userPosts = data.posts.filter((post: Post) => post.user_id === session.user?.id)
        console.log('필터링된 게시글 수:', userPosts.length)
        console.log('==============================')
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
        console.log('토큰 없음 - 저장된 장소 로딩 건너뛰기')
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
        setSavedLocations(data.locations || [])
      } else {
        console.error('저장된 장소 로딩 실패:', response.status)
      }
    } catch (error) {
      console.error('저장된 장소 로딩 중 오류:', error)
    } finally {
      setSavedLoading(false)
    }
  }, [])

  // 로그인하지 않은 사용자는 로그인 페이지로 리다이렉트
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/auth/login')
    }
  }, [status, router])

  // 세션이 있을 때 프로필 정보와 게시글 가져오기
  useEffect(() => {
    if (session) {
      fetchUserProfile()
      fetchUserPosts()
      loadSavedLocations()
    }
  }, [session, fetchUserProfile, fetchUserPosts, loadSavedLocations])

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
    console.log('=== 프로필 이미지 업로드 시작 ===')

    if (!selectedImage || !session?.user?.id) {
      console.log('업로드 취소: 이미지 또는 세션 없음')
      alert('업로드 취소: 이미지 또는 세션 없음')
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
        console.log('Authorization 헤더 추가됨')
      } else {
        console.log('경고: backendToken이 없음')
      }

      console.log('요청 헤더:', headers)
      console.log('이미지 데이터 길이:', selectedImage.length)

      const response = await fetch('/api/proxy/api/v1/profile/image', {
        method: 'PUT',
        headers: headers,
        body: JSON.stringify({
          image_data: selectedImage
        })
      })

      console.log('응답 상태:', response.status)
      console.log('응답 OK:', response.ok)

      if (!response.ok) {
        const errorData = await response.json()
        console.error('서버 에러 응답:', errorData)
        throw new Error(errorData.detail || '프로필 이미지 업로드 실패')
      }

      const result = await response.json()
      console.log('프로필 이미지 업데이트 성공:', result)

      alert('프로필 이미지가 업데이트되었습니다!')
      setSelectedImage(null)

      // 프로필 데이터 다시 가져오기 (페이지 새로고침 없이)
      await fetchUserProfile()
    } catch (error: any) {
      console.error('프로필 이미지 업데이트 오류:', error)
      alert(`이미지 업데이트에 실패했습니다: ${error.message}`)
    } finally {
      setIsUploadingImage(false)
      console.log('=== 프로필 이미지 업로드 종료 ===')
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
      alert('기본 정보가 업데이트되었습니다!')

    } catch (error: any) {
      console.error('기본 정보 업데이트 오류:', error)
      alert(`기본 정보 업데이트에 실패했습니다: ${error.message}`)
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
      console.log('여행 취향 업데이트 성공:', result)
      alert('여행 취향이 업데이트되었습니다!')

    } catch (error: any) {
      console.error('여행 취향 업데이트 오류:', error)
      alert(`여행 취향 업데이트에 실패했습니다: ${error.message}`)
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

      alert('포스트가 수정되었습니다!')
      handleCancelEdit()

    } catch (error: any) {
      console.error('포스트 수정 오류:', error)
      alert(`포스트 수정에 실패했습니다: ${error.message}`)
    } finally {
      setIsUpdatingPost(false)
    }
  }

  // 포스트 삭제
  const handleDeletePost = async (postId: number) => {
    if (!session) return

    if (!confirm('정말로 이 포스트를 삭제하시겠습니까?')) return

    try {
      const headers: any = {
        'Content-Type': 'application/json',
      }

      if ((session as any)?.backendToken) {
        headers['Authorization'] = `Bearer ${(session as any).backendToken}`
      }

      const response = await fetch(`/api/proxy/api/v1/posts/${postId}`, {
        method: 'DELETE',
        headers: headers
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '포스트 삭제 실패')
      }

      // 포스트 목록에서 제거
      setPosts(prevPosts => prevPosts.filter(post => post.id !== postId))
      alert('포스트가 삭제되었습니다!')

    } catch (error: any) {
      console.error('포스트 삭제 오류:', error)
      alert(`포스트 삭제에 실패했습니다: ${error.message}`)
    }
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

  // 목업 데이터
  const trips: TripCard[] = [
    {
      id: 1,
      title: '서울 시장 여행',
      dates: '2025.08.14(수) - 08.16(금)',
      status: 'active'
    },
    {
      id: 2,
      title: '전주 시장 여행',
      dates: '2025.03.03(월) - 03.04(화)',
      status: 'completed'
    },
    {
      id: 3,
      title: '부산 시장 여행',
      dates: '2024.07.02(화) - 07.04(목)',
      status: 'completed'
    },
    {
      id: 4,
      title: '강릉 시장 여행',
      dates: '2023.07.01(목) - 07.03(토)',
      status: 'completed'
    },
    {
      id: 5,
      title: '제주 시장 여행',
      dates: '2025.08.14(수) - 08.16(금)',
      status: 'planned'
    }
  ]



  // 저장된 장소 삭제 함수
  const handleDeleteSavedLocation = async (locationId: number) => {
    try {
      const token = getToken()
      
      if (!token) {
        alert('로그인이 필요합니다.')
        return
      }
      
      if (!confirm('저장된 장소를 삭제하시겠습니까?')) {
        return
      }
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'
      const response = await fetch(`${API_BASE_URL}/api/v1/saved-locations/${locationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        // 삭제 성공 시 목록에서 해당 장소 제거
        setSavedLocations(prev => prev.filter(location => location.id !== locationId))
      } else {
        alert('삭제에 실패했습니다.')
      }
    } catch (error) {
      console.error('저장된 장소 삭제 중 오류:', error)
      alert('삭제 중 오류가 발생했습니다.')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-blue-500'
      case 'completed': return 'bg-gray-400'
      case 'planned': return 'bg-green-500'
      default: return 'bg-gray-400'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'active': return '여행 중'
      case 'completed': return '완료됨'
      case 'planned': return '예정됨'
      default: return ''
    }
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'trips':
        return (
          <div className="space-y-4">
            {trips.map((trip) => (
              <div
                key={trip.id}
                className={`relative p-4 rounded-2xl ${trip.status === 'active' ? 'bg-blue-500' : 'bg-gray-600'
                  } text-white`}
              >
                {trip.status === 'active' && (
                  <div className="absolute top-4 right-4">
                    <span className="bg-red-500 text-white px-2 py-1 rounded-full text-xs">
                      🚩
                    </span>
                  </div>
                )}
                <h3 className="text-lg font-semibold mb-2">{trip.title}</h3>
                <p className="text-sm opacity-90">{trip.dates}</p>
                <div className="mt-3 flex items-center space-x-2">
                  <span className={`w-2 h-2 rounded-full ${getStatusColor(trip.status)}`}></span>
                  <span className="text-xs">{getStatusText(trip.status)}</span>
                </div>
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
                        onClick={() => handleDeletePost(post.id)}
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
                <div key={location.id} className="bg-gray-800 p-4 rounded-2xl">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <span className="text-xl">📍</span>
                        <h3 className="text-white font-semibold">{location.name}</h3>
                      </div>
                      <p className="text-gray-300 text-sm mb-2">
                        {location.address || '주소 정보 없음'}
                      </p>
                      <p className="text-gray-400 text-xs">
                        {new Date(location.created_at).toLocaleDateString('ko-KR')}에 저장됨
                      </p>
                    </div>
                    <button 
                      onClick={() => handleDeleteSavedLocation(location.id)}
                      className="text-red-400 hover:text-red-300 transition-colors p-1"
                      title="저장된 장소 삭제"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
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
              <>
                <img
                  src={userProfile.profile_image}
                  alt="Profile"
                  className="w-full h-full object-cover"
                />
                {console.log('프로필 이미지 표시 중:', userProfile.profile_image)}
              </>
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