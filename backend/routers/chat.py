from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import sys
import os

# LLM_RAG.py를 임포트하기 위해 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from LLM_RAG import get_travel_recommendation
    print("✅ LLM_RAG module imported successfully")
except ImportError as e:
    print(f"❌ Warning: Could not import LLM_RAG module: {e}")
    print("This is likely due to missing dependencies (langchain_aws, boto3, etc.)")
    get_travel_recommendation = None
except Exception as e:
    print(f"❌ Error initializing LLM_RAG module: {e}")
    get_travel_recommendation = None

router = APIRouter()

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    success: bool
    error: str = None

@router.post("/chat", response_model=ChatResponse)
async def chat_with_llm(chat_message: ChatMessage):
    """
    사용자의 메시지를 받아 LLM_RAG.py의 여행 추천 기능을 사용하여 응답을 생성합니다.
    """
    try:
        if get_travel_recommendation is None:
            # LLM_RAG가 사용 불가능할 때 기본 응답
            return ChatResponse(
                response=f"Input: {chat_message.message}'\n\n 응 꺼져",
                success=True
            )
        
        # LLM_RAG.py의 get_travel_recommendation 함수 호출
        print(f"🔍 Processing travel query: {chat_message.message}")
        response = get_travel_recommendation(chat_message.message, stream=False)
        print(f"✅ Got response: {response[:100]}..." if len(response) > 100 else f"✅ Got response: {response}")
        
        return ChatResponse(
            response=response,
            success=True
        )
        
    except Exception as e:
        print(f"Chat API error: {e}")
        return ChatResponse(
            response="응 꺼져",
            success=False,
            error=str(e)
        )

@router.get("/chat/health")
async def chat_health():
    """
    챗봇 서비스의 상태를 확인합니다.
    """
    try:
        if get_travel_recommendation is None:
            return {
                "status": "unhealthy", 
                "message": "LLM RAG 시스템이 초기화되지 않음"
            }
        
        # 간단한 테스트 쿼리로 시스템 상태 확인
        test_response = get_travel_recommendation("서울", stream=False)
        
        return {
            "status": "healthy",
            "message": "LLM RAG 시스템이 정상 작동 중"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy", 
            "message": f"LLM RAG 시스템 오류: {str(e)}"
        }