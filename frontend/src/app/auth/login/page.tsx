'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { signIn, useSession } from 'next-auth/react'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const router = useRouter()
  const { data: session, status } = useSession()
  const searchParams = useSearchParams()

  // URL 파라미터에서 성공 메시지 확인
  useEffect(() => {
    const message = searchParams.get('message')
    if (message === 'registration_success') {
      setSuccessMessage('회원가입이 완료되었습니다! 로그인해주세요.')
    }
  }, [searchParams])

  // 이미 로그인된 사용자는 메인 페이지로 리다이렉트
  useEffect(() => {
    if (status === 'authenticated' && session) {
      router.push('/')
    }
  }, [status, session, router])

  // 로딩 중이거나 이미 인증된 경우 로딩 표시
  if (status === 'loading' || status === 'authenticated') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">로그인 중...</p>
        </div>
      </div>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
      })

      if (result?.ok) {
        router.push('/')
      } else {
        setError('로그인에 실패했습니다. 이메일과 비밀번호를 확인해주세요.')
      }
    } catch (err) {
      setError('로그인에 실패했습니다. 이메일과 비밀번호를 확인해주세요.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0B1220] text-white">
      {/* Header with back button */}
      <div className="relative p-4">
        <button
          onClick={() => router.back()}
          className="absolute left-4 top-4 text-[#3E68FF] text-2xl hover:text-[#4C7DFF] transition-colors"
        >
          ‹
        </button>
      </div>

      <div className="flex items-center justify-center px-6 pb-20 pt-20">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            <h2 className="text-3xl font-bold text-[#3E68FF] mb-2">
              로그인
            </h2>
            <p className="text-[#94A9C9] text-sm">
              또는{' '}
              <Link href="/auth/register" className="font-medium text-[#3E68FF] hover:text-[#4C7DFF]">
                새 계정 만들기
              </Link>
            </p>
          </div>

          <form className="space-y-6" onSubmit={handleSubmit}>
            {successMessage && (
              <div className="bg-green-500/20 border border-green-500/30 text-green-400 px-4 py-3 rounded-2xl">
                {successMessage}
              </div>
            )}
            {error && (
              <div className="bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-3 rounded-2xl">
                {error}
              </div>
            )}

            <div>
              <input
                id="email"
                name="email"
                type="email"
                required
                className="w-full px-4 py-3 bg-[#12345D]/50 border border-[#1F3C7A] rounded-2xl text-white placeholder-[#6FA0E6] focus:outline-none focus:ring-2 focus:ring-[#3E68FF] focus:border-transparent"
                placeholder="이메일"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div>
              <input
                id="password"
                name="password"
                type="password"
                required
                className="w-full px-4 py-3 bg-[#12345D]/50 border border-[#1F3C7A] rounded-2xl text-white placeholder-[#6FA0E6] focus:outline-none focus:ring-2 focus:ring-[#3E68FF] focus:border-transparent"
                placeholder="비밀번호"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <div className="space-y-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-[#3E68FF] hover:bg-[#4C7DFF] disabled:opacity-50 rounded-2xl text-white font-semibold transition-colors"
              >
                {loading ? '로그인 중...' : '로그인'}
              </button>

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-[#1F3C7A]" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-[#0B1220] text-[#6FA0E6]">또는</span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => signIn('google', { callbackUrl: '/' })}
                className="w-full flex justify-center items-center py-3 bg-[#12345D]/50 hover:bg-[#1F3C7A]/50 border border-[#1F3C7A] rounded-2xl text-[#94A9C9] font-medium transition-colors"
              >
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Google로 로그인
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
