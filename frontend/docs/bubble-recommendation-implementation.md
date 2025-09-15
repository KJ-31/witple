# 말풍선 추천 기반 메시지 구현 가이드

## 🎯 **개요**

기존 정적 말풍선 메시지를 **추천 알고리즘 기반 개인화 메시지**로 개선하여 사용자 참여도와 클릭률을 향상시키는 구현 가이드입니다.

### **핵심 컨셉**
- **기존**: "안녕하세요" (모든 사용자 동일)
- **개선**: "명동교자 맛집 어떠세요? 🥟" (사용자 취향 맞춤)

### **구현 방식**
**하이브리드 2단계 로딩**: 빠른 응답(기본 메시지) + 개인화(추천 메시지)

---

## 🚀 **1단계: 백엔드 구현**

### 1.1 추천 기반 말풍선 메시지 함수 추가

**파일**: `backend/vectorization.py`

```python
async def get_bubble_recommendation_message(self, user_id: str) -> Dict[str, Any]:
    """추천 기반 말풍선 메시지 생성"""
    try:
        # 1. 사용자 상위 추천 장소 1개 가져오기 (빠른 조회)
        top_place = await self.get_single_top_recommendation(user_id)

        if not top_place:
            return {
                "message": "새로운 여행지 발견해보세요! 🌟",
                "type": "default",
                "place_info": None
            }

        # 2. 장소 기반 메시지 템플릿
        place_name = top_place.get('name', '').split()[0]  # 첫 단어만 (길이 제한)
        category = top_place.get('table_name', '')
        region = top_place.get('region', '')

        # 3. 카테고리별 메시지 템플릿
        message_templates = {
            'restaurants': [
                f"{place_name} 맛집 어떠세요? 🍽️",
                f"{region} 맛집 탐방 어때요? 🥘",
                f"새로운 맛집 발견해볼까요? 👨‍🍳"
            ],
            'accommodation': [
                f"{place_name} 숙소 어떠세요? 🏨",
                f"{region} 휴양지 어때요? 🛏️",
                f"완벽한 숙소 찾아드릴까요? ✨"
            ],
            'nature': [
                f"{place_name} 힐링 어때요? 🌿",
                f"{region} 자연여행 어떠세요? 🏔️",
                f"자연 속 힐링 떠나볼까요? 🌳"
            ],
            'shopping': [
                f"{place_name} 쇼핑 어떠세요? 🛍️",
                f"{region} 쇼핑투어 어때요? 🎁",
                f"쇼핑 명소 둘러볼까요? 🏬"
            ],
            'humanities': [
                f"{place_name} 구경 어때요? 🏛️",
                f"{region} 문화여행 어떠세요? 🎭",
                f"역사 탐방 떠나볼까요? 📚"
            ],
            'leisure_sports': [
                f"{place_name} 체험 어떠세요? 🎢",
                f"{region} 액티비티 어때요? 🏄‍♂️",
                f"신나는 체험 떠나볼까요? 🎯"
            ]
        }

        # 4. 메시지 선택 (사용자 ID 기반 일관성)
        templates = message_templates.get(category, [f"{place_name} 어떠세요? ✨"])
        selected_message = templates[hash(user_id) % len(templates)]

        # 5. 길이 제한 (15자 이내)
        if len(selected_message) > 15:
            selected_message = f"{region} 여행 어때요? {self._get_category_emoji(category)}"

        return {
            "message": selected_message,
            "type": "personalized",
            "place_info": {
                "place_id": top_place.get('place_id'),
                "table_name": top_place.get('table_name'),
                "name": top_place.get('name'),
                "region": top_place.get('region')
            }
        }

    except Exception as e:
        logger.error(f"Error generating bubble recommendation message: {e}")
        return {
            "message": "맞춤 여행지 추천받아보세요! 🎯",
            "type": "fallback",
            "place_info": None
        }

async def get_single_top_recommendation(self, user_id: str) -> Dict:
    """빠른 단일 추천 장소 조회"""
    try:
        # 캐시 먼저 확인 (30분)
        cache_key = f"top_rec:{user_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 개인화 추천에서 상위 1개만
        recommendations = await self.get_personalized_recommendations(
            user_id=user_id, limit=3  # 3개 가져와서 다양성 확보
        )

        if recommendations:
            # 가장 높은 점수의 장소 선택
            top_place = recommendations[0]
            cache.set(cache_key, top_place, expire=1800)  # 30분 캐시
            return top_place

        return None

    except Exception as e:
        logger.error(f"Error getting single top recommendation: {e}")
        return None

def _get_category_emoji(self, category: str) -> str:
    """카테고리별 이모지"""
    emoji_map = {
        'restaurants': '🍽️',
        'accommodation': '🏨',
        'nature': '🌿',
        'shopping': '🛍️',
        'humanities': '🏛️',
        'leisure_sports': '🎢'
    }
    return emoji_map.get(category, '✨')
```

### 1.2 API 엔드포인트 수정

**파일**: `backend/routers/recommendations.py`

기존 `/bubble-message` 엔드포인트를 다음과 같이 수정:

```python
@router.get("/bubble-message")
async def get_bubble_message(
    current_user = Depends(get_current_user_optional)
):
    """
    추천 기반 개인화 말풍선 메시지
    """
    try:
        if current_user and hasattr(current_user, 'user_id'):
            user_id = str(current_user.user_id)

            # 캐시 확인 (15분 - 말풍선은 자주 변경되어야 함)
            cache_key = f"bubble_rec_msg:{user_id}"
            cached_result = cache.get(cache_key)

            if cached_result:
                return {
                    **cached_result,
                    "cached": True
                }

            # 추천 기반 메시지 생성 (타임아웃 3초)
            try:
                import asyncio
                bubble_data = await asyncio.wait_for(
                    recommendation_engine.get_bubble_recommendation_message(user_id),
                    timeout=3.0
                )

                # 캐시에 저장 (15분)
                cache.set(cache_key, bubble_data, expire=900)

                return {
                    **bubble_data,
                    "cached": False
                }

            except asyncio.TimeoutError:
                # 타임아웃 시 기본 개인화 메시지
                user_prefs = await recommendation_engine.get_user_preferences(user_id)
                priority = user_prefs.get('basic', {}).get('priority') if user_prefs else None

                fallback_messages = {
                    'restaurants': "맛집 탐방 어떠세요? 🍽️",
                    'accommodation': "완벽한 숙소 찾아드릴까요? 🏨",
                    'shopping': "쇼핑 명소 어떠세요? 🛍️",
                    'experience': "신나는 체험 어떠세요? 🎢"
                }

                fallback_msg = fallback_messages.get(priority, "맞춤 여행지 추천받아보세요! 🎯")

                return {
                    "message": fallback_msg,
                    "type": "priority_fallback",
                    "place_info": None,
                    "cached": False
                }

        else:
            # 비로그인 사용자 - 시간대별 메시지
            return get_time_based_default_message()

    except Exception as e:
        logger.error(f"Error getting bubble recommendation message: {e}")
        return {
            "message": "여행 계획 도움이 필요하시면 클릭하세요! 🗺️",
            "type": "error",
            "place_info": None,
            "cached": False
        }

def get_time_based_default_message():
    """시간대별 기본 메시지"""
    import datetime
    hour = datetime.datetime.now().hour

    if 6 <= hour < 12:
        messages = ["좋은 아침! 여행 계획 어떠세요? 🌅", "새로운 하루, 어디로 떠날까요? ☀️"]
    elif 18 <= hour < 22:
        messages = ["오늘 하루 수고하셨어요! 여행은? 🌙", "휴식 겸 여행 어떠세요? 🌆"]
    else:
        messages = ["어디로 떠나고 싶으신가요? ✈️", "새로운 여행지 찾아보세요! 🌟"]

    selected = messages[hour % len(messages)]

    return {
        "message": selected,
        "type": "time_based",
        "place_info": None,
        "cached": False
    }
```

---

## 🎨 **2단계: 프론트엔드 구현**

### 2.1 BubbleAnimation.tsx 개선

**파일**: `frontend/src/components/BubbleAnimation.tsx`

```typescript
'use client'

import { useEffect, useRef, useState } from 'react'
import { useRive, useStateMachineInput } from '@rive-app/react-canvas'
import { useChatbot } from './ChatbotProvider'

interface BubbleMessageData {
  message: string
  type: 'personalized' | 'priority_fallback' | 'time_based' | 'error'
  place_info?: {
    place_id: number
    table_name: string
    name: string
    region: string
  }
  cached: boolean
}

export default function BubbleAnimation() {
  const { setShowChatbot, showChatbot, setChatContext } = useChatbot()

  const { rive, RiveComponent } = useRive({
    src: '/rive/bubble_2.riv',
    stateMachines: 'State Machine 1',
    autoplay: true,
    autoBind: true as any,
  })

  const showTrigger = useStateMachineInput(rive, 'State Machine 1', 'show')

  const firstTimeout = useRef<number | null>(null)
  const textInterval = useRef<number | null>(null)
  const messagesFetched = useRef(false)
  const startedRef = useRef(false)

  const [visible, setVisible] = useState(false)
  const [messages, setMessages] = useState<string[]>(['여행 계획 도움이 필요하신가요? 🗺️'])
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0)
  const [placeInfo, setPlaceInfo] = useState<BubbleMessageData['place_info'] | null>(null)

  // 즉시 표시용 기본 메시지
  const getDefaultMessages = (): string[] => {
    const hour = new Date().getHours()

    if (6 <= hour < 12) {
      return ['좋은 아침! 여행 계획 어떠세요? 🌅', '새로운 하루, 어디로 떠날까요? ☀️']
    } else if (18 <= hour < 22) {
      return ['오늘 하루 수고하셨어요! 🌙', '휴식 겸 여행 어떠세요? 🌆']
    } else {
      return [
        '어디로 떠나고 싶으신가요? ✈️',
        '새로운 여행지 찾아보세요! 🌟',
        '맞춤 여행지 추천받아보세요! 🎯'
      ]
    }
  }

  // 추천 기반 개인화 메시지 로드
  const fetchRecommendationMessages = async () => {
    if (messagesFetched.current) return

    try {
      const response = await fetch('/api/v1/recommendations/bubble-message', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}` || ''
        }
      })

      if (response.ok) {
        const data: BubbleMessageData = await response.json()
        console.log('🎯 추천 기반 메시지 로드:', data)

        if (data.message && data.type === 'personalized') {
          // 추천 메시지를 첫 번째로, 기본 메시지들을 추가
          const defaultMsgs = getDefaultMessages()
          const newMessages = [data.message, ...defaultMsgs.slice(0, 2)]
          setMessages(newMessages)
          setPlaceInfo(data.place_info || null)
          console.log('✨ 개인화 추천 메시지 적용:', data.message)
        } else if (data.type === 'priority_fallback') {
          // 우선순위 기반 폴백 메시지
          const defaultMsgs = getDefaultMessages()
          const newMessages = [data.message, ...defaultMsgs.slice(0, 2)]
          setMessages(newMessages)
          console.log('⚡ 우선순위 폴백 메시지 적용:', data.message)
        }
      }

      messagesFetched.current = true

    } catch (error) {
      console.log('추천 메시지 로드 중 오류:', error)
      messagesFetched.current = true
    }
  }

  // Rive 텍스트 설정
  function setSpeech(text: string) {
    if (!rive) return

    try {
      const vmi = (rive as any)?.viewModelInstance ?? (rive as any)?.defaultViewModelInstance
      const stringProp = vmi?.string?.('sentence')
      if (stringProp) {
        stringProp.value = text
        return
      }
    } catch {}

    try {
      (rive as any)?.setTextRunValue?.('sentence', text)
    } catch {}
  }

  // 트리거 발사
  function triggerSpeakOnce() {
    if (!rive || !showTrigger || document.visibilityState !== 'visible' || showChatbot) return

    try {
      rive.play && rive.play('State Machine 1')
    } catch {}

    showTrigger.fire()
  }

  // 메시지 순환
  const rotateMessage = () => {
    setCurrentMessageIndex((prevIndex) => {
      const nextIndex = (prevIndex + 1) % messages.length
      const nextMessage = messages[nextIndex]
      setSpeech(nextMessage)

      requestAnimationFrame(() => triggerSpeakOnce())

      return nextIndex
    })
  }

  // 말풍선 클릭 핸들러
  const handleBubbleClick = () => {
    // 추천된 장소 정보가 있으면 챗봇 컨텍스트에 설정
    if (placeInfo && currentMessageIndex === 0) {
      setChatContext({
        type: 'recommended_place',
        place: placeInfo,
        message: `${placeInfo.name}에 대해 더 알려주세요!`
      })
      console.log('🎯 추천 장소 컨텍스트 설정:', placeInfo)
    }

    setShowChatbot(true)
  }

  useEffect(() => {
    if (!rive || startedRef.current) return
    startedRef.current = true

    setVisible(true)

    // 1. 즉시 기본 메시지 설정
    const defaultMessages = getDefaultMessages()
    setMessages(defaultMessages)
    setSpeech(defaultMessages[0])

    // 2. 개인화 메시지 비동기 로드 (1초 후)
    setTimeout(() => {
      fetchRecommendationMessages()
    }, 1000)

    // 3. 첫 트리거 발사
    firstTimeout.current = window.setTimeout(() => {
      try {
        rive.play && rive.play('State Machine 1')
      } catch {}
      triggerSpeakOnce()
    }, 800)

    // 4. 메시지 순환 (6초 간격 - 추천 메시지를 더 오래 노출)
    textInterval.current = window.setInterval(rotateMessage, 6000)

    return () => {
      if (firstTimeout.current) clearTimeout(firstTimeout.current)
      if (textInterval.current) clearInterval(textInterval.current)
      startedRef.current = false
    }
  }, [rive, showChatbot, showTrigger])

  useEffect(() => {
    if (messages.length > 0) {
      const currentMessage = messages[currentMessageIndex % messages.length]
      setSpeech(currentMessage)
    }
  }, [messages, currentMessageIndex])

  return (
    <div className="fixed" style={{ top: '-110px', right: '35px', zIndex: 9999 }}>
      <div style={{ visibility: visible ? 'visible' : 'hidden' }}>
        <div className="relative">
          <RiveComponent style={{ width: 400, height: 400 }} />
          <div
            onClick={handleBubbleClick}
            className="absolute cursor-pointer hover:bg-blue-100 hover:bg-opacity-20 rounded-full transition-colors"
            style={{ top: '25%', left: '50%', width: '80%', height: '25%' }}
            title={placeInfo && currentMessageIndex === 0 ? `${placeInfo.name} 자세히 보기` : '여행 도우미 열기'}
          />
        </div>
      </div>
    </div>
  )
}
```

### 2.2 챗봇 컨텍스트 확장

**파일**: `frontend/src/components/ChatbotProvider.tsx`

기존 파일에 다음 타입과 기능 추가:

```typescript
interface ChatContext {
  type?: 'recommended_place' | 'general'
  place?: {
    place_id: number
    table_name: string
    name: string
    region: string
  }
  message?: string
}

interface ChatbotContextType {
  showChatbot: boolean
  setShowChatbot: (show: boolean) => void
  chatContext: ChatContext | null
  setChatContext: (context: ChatContext | null) => void
}

export function ChatbotProvider({ children }: { children: React.ReactNode }) {
  const [showChatbot, setShowChatbot] = useState(false)
  const [chatContext, setChatContext] = useState<ChatContext | null>(null)

  return (
    <ChatbotContext.Provider value={{
      showChatbot,
      setShowChatbot,
      chatContext,
      setChatContext
    }}>
      {children}
    </ChatbotContext.Provider>
  )
}
```

---

## 🎯 **3단계: 성능 최적화**

### 3.1 캐싱 전략

#### 다층 캐싱 구조
```python
# Level 1: 추천 결과 캐시 (30분) - 빠른 장소 조회
cache_key = f"top_rec:{user_id}"
cache.set(cache_key, top_place, expire=1800)

# Level 2: 메시지 결과 캐시 (15분) - 완성된 메시지
cache_key = f"bubble_rec_msg:{user_id}"
cache.set(cache_key, bubble_data, expire=900)

# Level 3: 사용자 선호도 캐시 (2시간) - 기본 정보
# 기존 추천 시스템에서 이미 적용됨
```

### 3.2 타임아웃 및 폴백 시스템

```python
# 3단계 폴백 시스템
try:
    # 1. 추천 기반 개인화 메시지 (3초 타임아웃)
    bubble_data = await asyncio.wait_for(
        recommendation_engine.get_bubble_recommendation_message(user_id),
        timeout=3.0
    )
except asyncio.TimeoutError:
    # 2. 우선순위 기반 폴백 메시지
    fallback_msg = get_priority_based_message(user_id)
except Exception:
    # 3. 기본 시간대별 메시지
    fallback_msg = get_time_based_default_message()
```

### 3.3 성능 모니터링

```python
# 메시지 생성 성능 로깅
import time

start_time = time.time()
bubble_data = await get_bubble_recommendation_message(user_id)
generation_time = time.time() - start_time

logger.info(f"Bubble message generated for {user_id}: {generation_time:.3f}s")
```

---

## 📊 **4단계: 테스트 및 검증**

### 4.1 기능 테스트 체크리스트

- [ ] **비로그인 사용자**: 시간대별 기본 메시지 표시
- [ ] **신규 로그인 사용자**: 우선순위 기반 메시지 표시
- [ ] **기존 사용자**: 개인화 추천 메시지 표시
- [ ] **캐싱**: 동일 사용자 재방문시 캐시된 메시지 사용
- [ ] **타임아웃**: API 실패시 3초 내 폴백 메시지 표시
- [ ] **말풍선 클릭**: 추천 장소 정보와 함께 챗봇 열기

### 4.2 성능 테스트

```bash
# API 응답시간 테스트
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8000/api/v1/recommendations/bubble-message"

# 동시 접속 테스트
ab -n 100 -c 10 "http://localhost:8000/api/v1/recommendations/bubble-message"
```

### 4.3 사용자 경험 테스트

| 시나리오 | 예상 응답시간 | 예상 메시지 |
|----------|-------------|------------|
| 첫 방문 (캐시 없음) | 1-3초 | 개인화 메시지 |
| 재방문 (캐시 있음) | 0.1초 | 캐시된 개인화 메시지 |
| API 실패 | 3초 → 즉시 | 우선순위/시간대별 메시지 |

---

## 🏆 **예상 결과**

### 개선 전 vs 개선 후

| 사용자 타입 | 기존 메시지 | 개선 후 메시지 |
|------------|------------|---------------|
| 맛집 선호자 | "안녕하세요" | "명동교자 맛집 어떠세요? 🥟" |
| 자연 선호자 | "여행 계획 필요하세요?" | "설악산 힐링 어때요? 🌿" |
| 쇼핑 선호자 | "어디로 떠나시겠어요?" | "명동 쇼핑 어떠세요? 🛍️" |
| 비로그인 사용자 | "안녕하세요" | "좋은 아침! 여행 계획 어떠세요? 🌅" |

### 예상 성과

- **클릭률 향상**: 30% → 60% (개인화된 흥미 유발)
- **챗봇 사용률 증가**: 기존 대비 2배
- **사용자 참여도**: 구체적 장소 제안으로 즉시 대화 연결
- **데이터 활용**: 기존 추천 시스템의 부가 가치 창출

---

## 🔧 **배포 가이드**

### 5.1 환경별 배포

```bash
# 개발 환경
git checkout feat/bubble-recommendation
git add .
git commit -m "feat: 말풍선 추천 기반 메시지 구현"

# 스테이징 테스트
docker-compose up --build

# 운영 배포
kubectl apply -f k8s/bubble-recommendation-config.yaml
```

### 5.2 모니터링 설정

```python
# 추가 메트릭 수집
- bubble_message_generation_time
- bubble_message_cache_hit_rate
- bubble_message_click_rate
- recommendation_api_timeout_count
```

### 5.3 A/B 테스트 준비

```javascript
// 프론트엔드에서 A/B 테스트 플래그
const useRecommendationBubble = featureFlag('recommendation_bubble', user.id)

if (useRecommendationBubble) {
  // 새로운 추천 기반 말풍선
  await fetchRecommendationMessages()
} else {
  // 기존 정적 메시지
  setMessages(['안녕하세요'])
}
```

---

## ✅ **완료 체크리스트**

### 백엔드
- [ ] `vectorization.py`에 추천 기반 메시지 함수 추가
- [ ] `recommendations.py`에 API 엔드포인트 수정
- [ ] 캐싱 로직 구현
- [ ] 타임아웃 및 폴백 시스템 구현
- [ ] 성능 로깅 추가

### 프론트엔드
- [ ] `BubbleAnimation.tsx` 개선
- [ ] `ChatbotProvider.tsx` 컨텍스트 확장
- [ ] 2단계 로딩 구현
- [ ] 장소 정보 클릭 연동 구현

### 테스트
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 수행
- [ ] 성능 테스트 완료
- [ ] 사용자 테스트 피드백 수집

이 구현으로 **개인화된 흥미 유발 + 즉시 연결**이 가능한 스마트한 말풍선이 완성됩니다! 🎉