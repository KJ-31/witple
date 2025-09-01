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
  (config) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
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
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('token')
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

export default apiClient
