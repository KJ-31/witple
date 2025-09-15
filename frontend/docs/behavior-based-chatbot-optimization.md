# 🎯 사용자 행동 기반 챗봇 말풍선 최적화 가이드

## 📋 개요

현재 Witple 프로덕트에서 수집하는 사용자 행동 데이터를 활용하여 챗봇 말풍선의 표시 타이밍과 빈도를 개인화하는 방법론입니다.

---

## 📊 현재 수집 중인 데이터

### 1. 실시간 행동 데이터
- **클릭 추적**: 관광지 카드 클릭 패턴
- **좋아요/북마크**: 관심 표시 행동
- **페이지 체류시간**: 각 페이지별 머문 시간
- **스크롤 패턴**: 콘텐츠 탐색 행동

### 2. 세션 메타데이터
```javascript
{
  user_id: "user123",
  session_id: "session_1234567890_abc123",
  page_url: "https://witple.com/",
  timestamp: "2024-01-15T10:30:00Z",
  action_type: "click|like|bookmark",
  place_category: "restaurants|nature|shopping"
}
```

### 3. 기술적 정보
- `user_agent`: 디바이스/브라우저 정보
- `referrer`: 유입 경로
- `page_url`: 현재 위치

---

## 💡 개인화 시나리오

### 시나리오 A: 활동량 기반 타이밍 조절

**🎯 목표**: 활발한 사용자에게는 빠른 응답, 천천히 보는 사용자에게는 여유로운 타이밍

```javascript
// 구현 예시
const getOptimalBubbleInterval = (userId) => {
  const recentClicks = actionTracker.getRecentActions('click', 300000) // 5분간
  const activityLevel = recentClicks.length

  if (activityLevel >= 5) return 120000      // 매우 활발: 2분마다
  if (activityLevel >= 2) return 300000      // 보통: 5분마다
  return 600000                              // 저활동: 10분마다
}
```

**📈 예상 효과**:
- 활발한 사용자: 더 빈번한 도움 제공
- 천천히 보는 사용자: 방해받지 않는 경험

### 시나리오 B: 관심사 기반 메시지 커스터마이징

**🎯 목표**: 사용자의 관심 카테고리에 맞는 맞춤 메시지

```javascript
// 최근 관심사 분석
const getUserInterests = (userId) => {
  const recentActions = actionTracker.getRecentActions('like', 86400000) // 24시간
  const categoryCount = recentActions.reduce((acc, action) => {
    acc[action.place_category] = (acc[action.place_category] || 0) + 1
    return acc
  }, {})

  return Object.keys(categoryCount).sort((a,b) => categoryCount[b] - categoryCount[a])
}

// 맞춤 메시지 생성
const getPersonalizedMessage = (topInterest) => {
  const messages = {
    'restaurants': '맛집 추천을 받아보시겠어요? 🍽️',
    'nature': '힐링 여행지를 찾아드릴까요? 🌿',
    'shopping': '쇼핑 명소를 추천해드릴게요! 🛍️',
    'humanities': '문화 체험지를 알아보실까요? 🏛️'
  }
  return messages[topInterest] || '여행 계획을 도와드릴게요! ✈️'
}
```

### 시나리오 C: 이탈 방지 개입

**🎯 목표**: 사용자가 떠나려 할 때 적절한 도움 제공

```javascript
// 이탈 징후 감지
const detectDisengagement = () => {
  const lastAction = actionTracker.getLastAction()
  const timeSinceLastAction = Date.now() - new Date(lastAction?.timestamp || 0).getTime()

  // 5분간 활동 없음 + 페이지 상단으로 스크롤 → 이탈 징후
  if (timeSinceLastAction > 300000 && window.scrollY < 100) {
    return true
  }

  return false
}

// 이탈 방지 메시지
const engagementMessages = [
  "아직 마음에 드는 곳을 못 찾으셨나요? 🤔",
  "원하는 여행지 스타일을 말씀해보세요!",
  "지역별 숨은 명소를 추천해드릴까요?"
]
```

### 시나리오 D: 시간대별 컨텍스트 인식

**🎯 목표**: 시간대와 사용 패턴을 고려한 메시지

```javascript
const getContextualMessage = () => {
  const hour = new Date().getHours()
  const dayOfWeek = new Date().getDay()
  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6

  if (hour >= 9 && hour <= 11) {
    return isWeekend ? "주말 나들이 계획 세워볼까요? 🌅" : "오늘 점심시간 맛집 추천받으시겠어요?"
  } else if (hour >= 18 && hour <= 21) {
    return "내일 여행 계획을 미리 세워보세요! 🌙"
  }

  return "어떤 여행지를 찾고 계세요? 🗺️"
}
```

---

## 🛠 기술 구현 가이드

### 1. ActionTracker 확장

현재 `actionTracker.ts`에 분석 메서드 추가:

```javascript
// actionTracker.ts 확장
class ActionTracker {
  // ... 기존 코드

  /**
   * 최근 액션들 가져오기
   */
  getRecentActions(actionType?: string, timeWindow: number = 300000) {
    const cutoffTime = Date.now() - timeWindow
    return this.buffer.filter(action => {
      const actionTime = new Date(action.timestamp).getTime()
      return actionTime >= cutoffTime &&
             (!actionType || action.action_type === actionType)
    })
  }

  /**
   * 사용자 관심사 분석
   */
  analyzeUserInterests(timeWindow: number = 86400000) {
    const actions = this.getRecentActions(undefined, timeWindow)
    const categoryCount = {}

    actions.forEach(action => {
      categoryCount[action.place_category] =
        (categoryCount[action.place_category] || 0) + 1
    })

    return Object.entries(categoryCount)
      .sort(([,a], [,b]) => b - a)
      .map(([category]) => category)
  }

  /**
   * 활동 레벨 측정
   */
  getActivityLevel(timeWindow: number = 300000) {
    return this.getRecentActions(undefined, timeWindow).length
  }
}
```

### 2. BubbleAnimation 컴포넌트 개선

```javascript
// BubbleAnimation.tsx
import { useEffect, useRef, useState } from 'react'
import { useRive } from '@rive-app/react-canvas'
import { useChatbot } from './ChatbotProvider'
import { getActionTracker } from '../utils/actionTracker'

export default function SmartBubbleAnimation() {
  const { setShowChatbot, showChatbot } = useChatbot()
  const [bubbleMessage, setBubbleMessage] = useState('')
  const [bubbleInterval, setBubbleInterval] = useState(300000) // 기본 5분

  const actionTracker = getActionTracker()

  // 사용자 행동 분석 및 최적화
  useEffect(() => {
    if (!actionTracker) return

    const analyzeAndOptimize = () => {
      // 활동량 기반 간격 조정
      const activityLevel = actionTracker.getActivityLevel(300000)
      const newInterval = getOptimalInterval(activityLevel)
      setBubbleInterval(newInterval)

      // 관심사 기반 메시지 설정
      const interests = actionTracker.analyzeUserInterests()
      const personalizedMsg = getPersonalizedMessage(interests[0])
      setBubbleMessage(personalizedMsg)

      console.log('🎯 Bubble optimization:', {
        activityLevel,
        interval: newInterval,
        topInterest: interests[0],
        message: personalizedMsg
      })
    }

    // 초기 분석
    analyzeAndOptimize()

    // 주기적 재분석 (1분마다)
    const analysisInterval = setInterval(analyzeAndOptimize, 60000)

    return () => clearInterval(analysisInterval)
  }, [actionTracker])

  // 나머지 Rive 애니메이션 로직...
}

// 유틸리티 함수들
const getOptimalInterval = (activityLevel) => {
  if (activityLevel >= 5) return 120000      // 2분
  if (activityLevel >= 2) return 300000      // 5분
  return 600000                              // 10분
}

const getPersonalizedMessage = (topInterest) => {
  const messages = {
    'restaurants': '맛집 추천을 받아보시겠어요? 🍽️',
    'nature': '힐링 여행지를 찾아드릴까요? 🌿',
    'shopping': '쇼핑 명소를 추천해드릴게요! 🛍️',
    'humanities': '문화 체험지를 알아보실까요? 🏛️'
  }
  return messages[topInterest] || '여행 계획을 도와드릴게요! ✈️'
}
```

### 3. 성과 측정

```javascript
// 말풍선 효과성 추적
const trackBubbleEffectiveness = (bubbleType, userResponse) => {
  actionTracker.trackCustomEvent('bubble_interaction', {
    bubble_type: bubbleType,
    user_response: userResponse, // 'clicked' | 'ignored' | 'dismissed'
    user_activity_level: actionTracker.getActivityLevel(),
    personalization_applied: true
  })
}
```

---

## 📈 예상 효과

### 정량적 지표
- **챗봇 참여율 증가**: 30-50% 예상
- **이탈률 감소**: 15-20% 예상
- **세션 지속시간 증가**: 20-30% 예상

### 정성적 개선
- 사용자별 최적화된 경험
- 방해받지 않는 자연스러운 상호작용
- 개인 관심사에 맞는 맞춤 제안

---

## 🚀 구현 우선순위

### Phase 1: 기본 개인화 (1-2주)
1. ✅ ActionTracker 분석 메서드 추가
2. ✅ 활동량 기반 간격 조정
3. ✅ 기본 성과 추적

### Phase 2: 고급 개인화 (2-3주)
1. 관심사 기반 메시지 커스터마이징
2. 시간대별 컨텍스트 인식
3. 이탈 방지 로직

### Phase 3: 머신러닝 최적화 (4-6주)
1. 사용자 클러스터링
2. A/B 테스트 프레임워크
3. 자동 최적화 알고리즘

---

## 🔍 모니터링 및 개선

### 핵심 지표
- **CTR (Click Through Rate)**: 말풍선 클릭률
- **Engagement Time**: 상호작용 지속시간
- **Conversion Rate**: 챗봇 → 실제 여행지 선택률
- **User Satisfaction**: 사용자 만족도

### 지속적 개선
- 주간 성과 리포트
- 사용자 피드백 수집
- 알고리즘 튜닝
- 새로운 개인화 패턴 발견

---

*📝 작성일: 2025년 1월*
*🔄 최종 수정: 사용자 행동 패턴 분석 완료 시점*