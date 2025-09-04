'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

export default function AuthCallback() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState('처리 중...')

  useEffect(() => {
    const token = searchParams.get('token')
    const error = searchParams.get('error')

    if (error) {
      setStatus('로그인 실패')
      setTimeout(() => {
        router.push('/auth/register?error=oauth_failed')
      }, 2000)
      return
    }

    if (token) {
      // 토큰을 로컬 스토리지에 저장
      localStorage.setItem('token', token)
      setStatus('로그인 성공! 리다이렉트 중...')
      
      // 대시보드로 리다이렉트
      setTimeout(() => {
        router.push('/dashboard')
      }, 1500)
    } else {
      setStatus('인증 정보가 없습니다')
      setTimeout(() => {
        router.push('/auth/register')
      }, 2000)
    }
  }, [searchParams, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
            인증 처리 중
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            {status}
          </p>
          <div className="mt-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          </div>
        </div>
      </div>
    </div>
  )
}