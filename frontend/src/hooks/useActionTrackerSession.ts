'use client'

import { useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { getActionTracker } from '../utils/actionTracker'

/**
 * ActionTracker와 NextAuth 세션을 동기화하는 훅
 * 각 페이지에서 이 훅을 호출하면 자동으로 사용자 ID가 actionTracker에 설정됩니다.
 */
export function useActionTrackerSession() {
  const { data: session, status } = useSession()

  useEffect(() => {
    // 로딩 중이면 대기
    if (status === 'loading') return
    
    const tracker = getActionTracker()
    if (!tracker) return

    if (session?.user?.id) {
      // 세션이 있으면 사용자 ID 설정
      tracker.setCurrentUserId(session.user.id as string)
    } else {
      // 세션이 없으면 사용자 ID 제거
      tracker.setCurrentUserId(null)
    }
  }, [session, status])

  return { session, status }
}