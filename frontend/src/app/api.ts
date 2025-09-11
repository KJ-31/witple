import axios from 'axios'

// 프록시를 통한 백엔드 API 호출
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/proxy'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 요청 인터셉터
apiClient.interceptors.request.use(
  async (config) => {
    if (typeof window !== 'undefined') {
      // 1. localStorage에서 토큰 먼저 확인 (우선순위)
      const localToken = localStorage.getItem('token')
      if (localToken) {
        config.headers.Authorization = `Bearer ${localToken}`
        console.log('Using localStorage token for API request')
        return config
      }
      
      // 2. NextAuth 세션에서 토큰 가져오기 (fallback)
      try {
        const { getSession } = await import('next-auth/react')
        const session = await getSession()
        
        if (session && (session as any).backendToken) {
          config.headers.Authorization = `Bearer ${(session as any).backendToken}`
          console.log('Using NextAuth session token for API request')
        } else {
          console.log('No token found - making request as guest')
        }
      } catch (error) {
        console.log('Error getting NextAuth session:', error)
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 응답 인터셉터
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      console.log('401 Unauthorized - clearing tokens and redirecting to login')
      
      // 모든 토큰 제거
      localStorage.removeItem('token')
      
      // NextAuth 세션도 로그아웃
      try {
        const { signOut } = await import('next-auth/react')
        await signOut({ redirect: false })
      } catch (e) {
        console.log('Error signing out from NextAuth:', e)
      }
      
      // 로그인 페이지로 리다이렉트
      window.location.href = '/auth/login'
    }
    return Promise.reject(error)
  }
)

// 인증 API
export const login = async (email: string, password: string) => {
  const formData = new URLSearchParams()
  formData.append('username', email)
  formData.append('password', password)

  const response = await apiClient.post('/api/v1/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  })
  return response.data
}

export const register = async (email: string, password: string, full_name: string) => {
  const response = await apiClient.post('/api/v1/auth/register', {
    email,
    password,
    full_name,
  })
  return response.data
}

export const getCurrentUser = async () => {
  const response = await apiClient.get('/api/v1/auth/me')
  return response.data
}

// 사용자 API
export const getUsers = async () => {
  const response = await apiClient.get('/api/v1/users/')
  return response.data
}

// 여행 일정 API
export const saveTrip = async (tripData: {
  title: string
  description?: string | null
  places: any[]
  startDate?: string
  endDate?: string
  days?: number
}) => {
  const response = await apiClient.post('/api/v1/trips/', tripData)
  return response.data
}

export const updateTrip = async (tripId: number, tripData: {
  title: string
  description?: string | null
  places: any[]
  start_date?: string
  end_date?: string
  days?: number
}) => {
  const response = await apiClient.put(`/api/v1/trips/${tripId}`, tripData)
  return response.data
}

export default apiClient
