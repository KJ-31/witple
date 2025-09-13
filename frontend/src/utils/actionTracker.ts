/**
 * Action Tracker - 사용자 행동 데이터 수집
 * Collection Server로 클릭, 좋아요, 북마크 데이터 전송
 */

interface ActionData {
  user_id: string | null
  place_id: string
  place_category: string
  action_type: 'click' | 'like' | 'bookmark'
  action_value?: number
  action_detail?: Record<string, any>
  session_id: string
  page_url: string
  user_agent: string
  referrer: string
  timestamp: string
}

interface ActionTrackerConfig {
  collectionServerUrl: string
  debug?: boolean
  bufferSize?: number
  flushInterval?: number
}

class ActionTracker {
  private config: ActionTrackerConfig
  private sessionId: string
  private buffer: ActionData[] = []
  private flushTimer: NodeJS.Timeout | null = null
  private currentUserId: string | null = null

  constructor(config: ActionTrackerConfig) {
    this.config = {
      bufferSize: 10,
      flushInterval: 30000, // 30초
      debug: false,
      ...config
    }
    
    this.sessionId = this.generateSessionId()
    this.startFlushTimer()
    
    if (this.config.debug) {
      console.log('🎯 ActionTracker initialized:', { sessionId: this.sessionId })
    }
  }

  /**
   * 세션 ID 생성
   */
  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * 현재 사용자 ID 설정 (ActionTrackerProvider에서 호출)
   */
  setCurrentUserId(userId: string | null) {
    this.currentUserId = userId
    if (this.config.debug) {
      console.log('🎯 ActionTracker user ID updated:', userId)
    }
  }

  /**
   * 현재 사용자 ID 가져오기
   */
  private getCurrentUserId(): string | null {
    // 1. ActionTrackerProvider에서 설정한 사용자 ID (우선순위 최고)
    if (this.currentUserId) {
      return this.currentUserId
    }
    
    // 2. 기존 방식들 (하위 호환성)
    try {
      const accessToken = localStorage.getItem('access_token')
      if (accessToken) {
        const payload = JSON.parse(atob(accessToken.split('.')[1]))
        return payload.sub || payload.user_id || null
      }
    } catch (error) {
      // JWT 토큰 파싱 실패
    }
    
    try {
      const userId = sessionStorage.getItem('user_id')
      if (userId) return userId
    } catch (error) {
      // sessionStorage 접근 실패
    }
    
    return null
  }

  /**
   * place_id에서 카테고리 추출
   */
  private extractCategory(placeId: string): string {
    if (placeId.includes('_')) {
      const lastUnderscoreIndex = placeId.lastIndexOf('_')
      return placeId.substring(0, lastUnderscoreIndex)
    }
    return 'unknown'
  }

  /**
   * 액션 데이터 추가
   */
  private addAction(actionData: Partial<ActionData>) {
    const fullActionData: ActionData = {
      user_id: this.getCurrentUserId(),
      place_id: actionData.place_id!,
      place_category: actionData.place_category || this.extractCategory(actionData.place_id!),
      action_type: actionData.action_type!,
      action_value: actionData.action_value,
      action_detail: actionData.action_detail || {},
      session_id: this.sessionId,
      page_url: typeof window !== 'undefined' ? window.location.href : '',
      user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
      referrer: typeof document !== 'undefined' ? document.referrer : '',
      timestamp: new Date().toISOString()
    }

    this.buffer.push(fullActionData)

    if (this.config.debug) {
      console.log('🎯 Action tracked:', fullActionData)
    }

    // 즉시 전송이 필요한 액션들 (like, bookmark)
    if (['like', 'bookmark'].includes(actionData.action_type!)) {
      this.flushBuffer()
    } else if (this.buffer.length >= this.config.bufferSize!) {
      // 버퍼가 가득 차면 전송
      this.flushBuffer()
    }
  }

  /**
   * 클릭 액션 추적
   */
  trackClick(placeId: string, additionalData?: Record<string, any>) {
    this.addAction({
      place_id: placeId,
      action_type: 'click',
      action_value: 1,
      action_detail: {
        click_type: 'attraction_view',
        ...additionalData
      }
    })
  }

  /**
   * 좋아요 액션 추적
   */
  trackLike(placeId: string, isLiked: boolean, additionalData?: Record<string, any>) {
    this.addAction({
      place_id: placeId,
      action_type: 'like',
      action_value: isLiked ? 1 : 0,
      action_detail: {
        is_liked: isLiked,
        ...additionalData
      }
    })
  }

  /**
   * 북마크 액션 추적
   */
  trackBookmark(placeId: string, isBookmarked: boolean, additionalData?: Record<string, any>) {
    this.addAction({
      place_id: placeId,
      action_type: 'bookmark',
      action_value: isBookmarked ? 1 : 0,
      action_detail: {
        is_bookmarked: isBookmarked,
        ...additionalData
      }
    })
  }

  /**
   * 버퍼 전송
   */
  private async flushBuffer() {
    if (this.buffer.length === 0) return

    const dataToSend = [...this.buffer]
    this.buffer = []

    try {
      const response = await fetch(`${this.config.collectionServerUrl}/collect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          actions: dataToSend
        })
      })

      if (this.config.debug) {
        if (response.ok) {
          console.log('✅ Actions sent successfully:', dataToSend.length)
        } else {
          console.error('❌ Failed to send actions:', response.status)
        }
      }

      if (!response.ok) {
        // 전송 실패시 버퍼에 다시 추가 (재시도)
        this.buffer.unshift(...dataToSend)
      }
    } catch (error) {
      if (this.config.debug) {
        console.error('❌ Error sending actions:', error)
      }
      // 네트워크 오류시 버퍼에 다시 추가
      this.buffer.unshift(...dataToSend)
    }
  }

  /**
   * 주기적 전송 타이머 시작
   */
  private startFlushTimer() {
    if (this.flushTimer) {
      clearInterval(this.flushTimer)
    }

    this.flushTimer = setInterval(() => {
      this.flushBuffer()
    }, this.config.flushInterval!)
  }

  /**
   * 즉시 전송
   */
  flush() {
    this.flushBuffer()
  }

  /**
   * 리소스 정리
   */
  destroy() {
    if (this.flushTimer) {
      clearInterval(this.flushTimer)
      this.flushTimer = null
    }
    this.flushBuffer() // 남은 데이터 전송
  }
}

// 싱글톤 인스턴스
let trackerInstance: ActionTracker | null = null

/**
 * ActionTracker 초기화
 */
export function initializeActionTracker(config?: Partial<ActionTrackerConfig>) {
  const defaultConfig: ActionTrackerConfig = {
    collectionServerUrl: process.env.NEXT_PUBLIC_COLLECTION_SERVER_URL || 'http://localhost:8080',
    debug: process.env.NODE_ENV === 'development'
  }

  trackerInstance = new ActionTracker({
    ...defaultConfig,
    ...config
  })

  return trackerInstance
}

/**
 * ActionTracker 인스턴스 가져오기
 */
export function getActionTracker(): ActionTracker | null {
  return trackerInstance
}

/**
 * 편의 함수들
 */
export const trackClick = (placeId: string, additionalData?: Record<string, any>) => {
  trackerInstance?.trackClick(placeId, additionalData)
}

export const trackLike = (placeId: string, isLiked: boolean, additionalData?: Record<string, any>) => {
  trackerInstance?.trackLike(placeId, isLiked, additionalData)
}

export const trackBookmark = (placeId: string, isBookmarked: boolean, additionalData?: Record<string, any>) => {
  trackerInstance?.trackBookmark(placeId, isBookmarked, additionalData)
}

// 페이지 언로드시 데이터 전송
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    trackerInstance?.flush()
  })

  // 페이지 숨김시에도 전송 (모바일 대응)
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      trackerInstance?.flush()
    }
  })
}

export default ActionTracker