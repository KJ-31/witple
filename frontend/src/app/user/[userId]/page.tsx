'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { User, MapPin, Calendar, Heart, Users, Globe, Clock, X } from 'lucide-react';
import TripDetailModal from '@/components/TripDetailModal';

interface UserProfile {
  user_id: string;
  email: string;
  name: string;
  age: number | null;
  nationality: string | null;
  profile_image: string | null;
  created_at: string | null;
  persona: string | null;
  priority: string | null;
  accommodation: string | null;
  exploration: string | null;
}

interface SavedLocation {
  id: number;
  user_id: string;
  places: string;
  place_name?: string;
  place_image?: string;
  place_address?: string;
  created_at: string;
  updated_at: string;
}

interface SavedLocationListResponse {
  locations: SavedLocation[];
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
}

interface Trip {
  id: number;
  title: string;
  description?: string;
  places: any[];
  start_date?: string;
  end_date?: string;
  status: string;
  status_display: string;
  created_at: string;
}

interface TripListResponse {
  trips: Trip[];
  total: number;
}

export default function UserProfilePage() {
  const params = useParams();
  const router = useRouter();
  const { data: session } = useSession();
  const userId = params.userId as string;
  
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [savedLocations, setSavedLocations] = useState<SavedLocation[]>([]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTrip, setSelectedTrip] = useState<Trip | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isOwnProfile, setIsOwnProfile] = useState(false);
  const [toast, setToast] = useState<{
    show: boolean
    type: 'success' | 'error' | 'info'
    message: string
  }>({
    show: false,
    type: 'success',
    message: ''
  });

  useEffect(() => {
    if (userId) {
      fetchUserProfile();
      fetchUserSavedLocations();
      fetchUserTrips();
      // 현재 사용자와 비교
      if (session?.user?.id === userId) {
        setIsOwnProfile(true);
      }
    }
  }, [userId, session]);

  const fetchUserProfile = async () => {
    try {
      const headers: HeadersInit = {};
      if (session?.accessToken) {
        headers['Authorization'] = `Bearer ${session.accessToken}`;
      }
      
      const response = await fetch(`/api/proxy/api/v1/profile/${userId}`, {
        headers
      });
      if (!response.ok) {
        throw new Error('사용자 프로필을 불러올 수 없습니다.');
      }
      const data = await response.json();
      setUserProfile(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.');
    }
  };

  const fetchUserSavedLocations = async () => {
    try {
      const headers: HeadersInit = {};
      if (session?.accessToken) {
        headers['Authorization'] = `Bearer ${session.accessToken}`;
      }
      
      const response = await fetch(`/api/proxy/api/v1/saved-locations/user/${userId}?page=0&limit=10`, {
        headers
      });
      if (!response.ok) {
        throw new Error('저장된 장소를 불러올 수 없습니다.');
      }
      const data: SavedLocationListResponse = await response.json();
      setSavedLocations(data.locations);
    } catch (err) {
      console.error('저장된 장소 로딩 오류:', err);
    }
  };

  const fetchUserTrips = async () => {
    try {
      const headers: HeadersInit = {};
      if (session?.accessToken) {
        headers['Authorization'] = `Bearer ${session.accessToken}`;
      }
      
      const response = await fetch(`/api/proxy/api/v1/trips/user/${userId}?limit=10&offset=0`, {
        headers
      });
      if (!response.ok) {
        throw new Error('여행 일정을 불러올 수 없습니다.');
      }
      const data: TripListResponse = await response.json();
      setTrips(data.trips);
    } catch (err) {
      console.error('여행 일정 로딩 오류:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  // 토큰 가져오기 함수
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
    
    // localStorage에서 토큰 확인
    const localToken = localStorage.getItem('access_token')
    if (localToken) {
      return localToken
    }
    
    // localStorage의 다른 키들도 확인
    const localKeys = ['token', 'jwt', 'accessToken']
    for (const key of localKeys) {
      const token = localStorage.getItem(key)
      if (token) {
        return token
      }
    }
    
    return null
  };

  // 토스트 표시 함수
  const showToast = (type: 'success' | 'error' | 'info', message: string) => {
    setToast({ show: true, type, message })
    setTimeout(() => {
      setToast(prev => ({ ...prev, show: false }))
    }, 3000)
  }

  // 일정 복사 함수
  const handleCopyTrip = async (tripId: number) => {
    try {
      const token = getToken();
      if (!token) {
        showToast('error', '로그인이 필요합니다.');
        return;
      }

      const response = await fetch('/api/proxy/api/v1/trips/copy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          trip_id: tripId
        })
      });

      if (!response.ok) {
        throw new Error('일정 복사에 실패했습니다.');
      }

      showToast('success', '일정이 성공적으로 복사되었습니다!');
    } catch (error) {
      console.error('일정 복사 오류:', error);
      showToast('error', '일정 복사 중 오류가 발생했습니다.');
      throw error;
    }
  };

  // 일정 클릭 핸들러
  const handleTripClick = (trip: Trip) => {
    setSelectedTrip(trip);
    setIsModalOpen(true);
  };

  const getPersonaIcon = (persona: string) => {
    switch (persona) {
      case 'adventure': return '🏔️';
      case 'culture': return '🏛️';
      case 'relaxation': return '🏖️';
      case 'food': return '🍽️';
      case 'nightlife': return '🌃';
      default: return '✈️';
    }
  };

  const getPersonaText = (persona: string) => {
    switch (persona) {
      case 'adventure': return '모험가';
      case 'culture': return '문화 탐험가';
      case 'relaxation': return '휴양지 애호가';
      case 'food': return '미식가';
      case 'nightlife': return '야경 애호가';
      default: return '여행자';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-white">프로필을 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error || !userProfile) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-white mb-2">프로필을 찾을 수 없습니다</h2>
          <p className="text-gray-300 mb-4">{error}</p>
          <button
            onClick={() => router.back()}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            돌아가기
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* 헤더 */}
      <div className="bg-gray-800 shadow-sm border-b border-gray-700">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => router.back()}
              className="flex items-center text-gray-300 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              돌아가기
            </button>
            {isOwnProfile && (
              <button
                onClick={() => router.push('/profile')}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                내 프로필로 이동
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* 프로필 정보 */}
        <div className="bg-gray-800 rounded-xl shadow-sm p-6 mb-6">
          <div className="flex items-start space-x-6">
            {/* 프로필 이미지 */}
            <div className="flex-shrink-0">
              {userProfile.profile_image ? (
                <img
                  src={userProfile.profile_image}
                  alt={userProfile.name || '프로필'}
                  className="w-24 h-24 rounded-full object-cover"
                />
              ) : (
                <div className="w-24 h-24 rounded-full bg-gray-200 flex items-center justify-center">
                  <User className="w-12 h-12 text-gray-400" />
                </div>
              )}
            </div>

            {/* 사용자 정보 */}
            <div className="flex-1">
              <div className="flex items-center space-x-3 mb-2">
                <h1 className="text-2xl font-bold text-white">
                  {userProfile.name || '이름 없음'}
                </h1>
                {userProfile.persona && (
                  <span className="flex items-center bg-blue-600 text-white px-3 py-1 rounded-full text-sm">
                    <span className="mr-1">{getPersonaIcon(userProfile.persona)}</span>
                    {getPersonaText(userProfile.persona)}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-300">
                {userProfile.age && (
                  <div className="flex items-center">
                    <Calendar className="w-4 h-4 mr-2" />
                    {userProfile.age}세
                  </div>
                )}
                {userProfile.nationality && (
                  <div className="flex items-center">
                    <Globe className="w-4 h-4 mr-2" />
                    {userProfile.nationality}
                  </div>
                )}
                {userProfile.created_at && (
                  <div className="flex items-center">
                    <Clock className="w-4 h-4 mr-2" />
                    {formatDate(userProfile.created_at)} 가입
                  </div>
                )}
              </div>

              {/* 여행 취향 */}
              {(userProfile.priority || userProfile.accommodation || userProfile.exploration) && (
                <div className="mt-4 p-4 bg-gray-700 rounded-lg">
                  <h3 className="font-semibold text-white mb-2">여행 취향</h3>
                  <div className="space-y-2 text-sm text-gray-300">
                    {userProfile.priority && (
                      <div>
                        <span className="font-medium">우선순위:</span> {userProfile.priority}
                      </div>
                    )}
                    {userProfile.accommodation && (
                      <div>
                        <span className="font-medium">숙박 선호:</span> {userProfile.accommodation}
                      </div>
                    )}
                    {userProfile.exploration && (
                      <div>
                        <span className="font-medium">탐험 스타일:</span> {userProfile.exploration}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 여행 일정 */}
        <div className="bg-gray-800 rounded-xl shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-white flex items-center">
              <Calendar className="w-5 h-5 mr-2" />
              여행 일정
            </h2>
            <span className="text-sm text-gray-400">
              총 {trips.length}개
            </span>
          </div>

                {trips.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {trips.map((trip) => (
                      <div 
                        key={trip.id} 
                        className="border border-gray-600 rounded-lg p-4 hover:shadow-md transition-shadow bg-gray-700 cursor-pointer"
                        onClick={() => handleTripClick(trip)}
                      >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <h3 className="font-medium text-white mb-1">
                        {trip.title}
                      </h3>
                      {trip.description && (
                        <p className="text-sm text-gray-300 mb-2 line-clamp-2">
                          {trip.description}
                        </p>
                      )}
                      <div className="flex items-center space-x-4 text-xs text-gray-400">
                        {trip.start_date && trip.end_date && (
                          <span>
                            {formatDate(trip.start_date)} - {formatDate(trip.end_date)}
                          </span>
                        )}
                        <span className="bg-blue-600 text-white px-2 py-1 rounded-full">
                          {trip.status_display}
                        </span>
                      </div>
                    </div>
                    <Calendar className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  </div>
                  {trip.places && trip.places.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-600">
                      <p className="text-xs text-gray-400 mb-2">
                        {trip.places.length}개 장소
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {trip.places.slice(0, 3).map((place, index) => (
                          <span key={index} className="bg-gray-600 text-gray-200 px-2 py-1 rounded text-xs">
                            {place.name || `장소 ${index + 1}`}
                          </span>
                        ))}
                        {trip.places.length > 3 && (
                          <span className="bg-gray-600 text-gray-200 px-2 py-1 rounded text-xs">
                            +{trip.places.length - 3}개 더
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Calendar className="w-12 h-12 text-gray-500 mx-auto mb-4" />
              <p className="text-gray-400">여행 일정이 없습니다.</p>
            </div>
          )}
        </div>

        {/* 저장된 장소 */}
        <div className="bg-gray-800 rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-white flex items-center">
              <MapPin className="w-5 h-5 mr-2" />
              저장된 장소
            </h2>
            <span className="text-sm text-gray-400">
              총 {savedLocations.length}개
            </span>
          </div>

          {savedLocations.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {savedLocations.map((location) => (
                <div 
                  key={location.id} 
                  className="border border-gray-600 rounded-lg p-4 hover:shadow-md transition-shadow bg-gray-700 cursor-pointer"
                  onClick={() => {
                    // places 필드에서 테이블명과 ID 추출
                    const placeInfo = location.places;
                    if (placeInfo && placeInfo.includes(':')) {
                      const [tableName, placeId] = placeInfo.split(':');
                      // 올바른 URL 형식으로 변환: tableName_placeId
                      router.push(`/attraction/${tableName}_${placeId}`);
                    }
                  }}
                >
                  <div className="flex items-start space-x-4">
                    {/* 장소 이미지 */}
                    <div className="flex-shrink-0">
                      {location.place_image ? (
                        <img
                          src={location.place_image}
                          alt={location.place_name || '장소 이미지'}
                          className="w-16 h-16 rounded-lg object-cover"
                        />
                      ) : (
                        <div className="w-16 h-16 rounded-lg bg-gray-600 flex items-center justify-center">
                          <MapPin className="w-8 h-8 text-gray-400" />
                        </div>
                      )}
                    </div>
                    
                    {/* 장소 정보 */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-white mb-1 truncate">
                        {location.place_name || '장소명 없음'}
                      </h3>
                      {location.place_address && (
                        <p className="text-sm text-gray-300 mb-2 line-clamp-2">
                          {location.place_address}
                        </p>
                      )}
                      <p className="text-xs text-gray-400">
                        {formatDate(location.created_at)} 저장
                      </p>
                    </div>
                    
                    {/* 화살표 아이콘 */}
                    <div className="flex-shrink-0">
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <MapPin className="w-12 h-12 text-gray-500 mx-auto mb-4" />
              <p className="text-gray-400">저장된 장소가 없습니다.</p>
            </div>
          )}
        </div>
      </div>

      {/* Trip Detail Modal */}
      {selectedTrip && (
        <TripDetailModal
          trip={selectedTrip}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedTrip(null);
          }}
          onCopyTrip={handleCopyTrip}
          isOwner={isOwnProfile}
        />
      )}

      {/* Toast 알림 */}
      {toast.show && (
        <div className={`fixed top-20 left-4 right-4 z-[60] p-4 rounded-2xl backdrop-blur-sm transition-all duration-300 transform ${
          toast.show ? 'translate-y-0 opacity-100' : '-translate-y-2 opacity-0'
        } ${
          toast.type === 'success' ? 'bg-green-900/90 text-green-100 border border-green-700/50' :
          toast.type === 'error' ? 'bg-red-900/90 text-red-100 border border-red-700/50' :
          'bg-blue-900/90 text-blue-100 border border-blue-700/50'
        }`}>
          <div className="flex items-center space-x-3">
            {toast.type === 'success' && (
              <div className="flex-shrink-0">
                <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            )}
            {toast.type === 'error' && (
              <div className="flex-shrink-0">
                <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            )}
            {toast.type === 'info' && (
              <div className="flex-shrink-0">
                <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            )}
            <div className="flex-1">
              <p className="text-sm font-medium">{toast.message}</p>
            </div>
            <button
              onClick={() => setToast(prev => ({ ...prev, show: false }))}
              className="flex-shrink-0 text-gray-400 hover:text-gray-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
