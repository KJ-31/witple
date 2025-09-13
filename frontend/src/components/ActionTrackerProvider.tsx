'use client'

import { useEffect } from 'react'
import { initializeActionTracker } from '../utils/actionTracker'

/**
 * ActionTracker 전역 초기화 컴포넌트
 * 앱이 시작될 때 한 번만 actionTracker를 초기화합니다.
 */
export default function ActionTrackerProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // actionTracker 전역 초기화
    initializeActionTracker({
      collectionServerUrl: process.env.NEXT_PUBLIC_COLLECTION_SERVER_URL || 'http://localhost:8080',
      debug: process.env.NODE_ENV === 'development',
      bufferSize: 10,
      flushInterval: 30000 // 30초
    })
  }, [])

  return <>{children}</>
}