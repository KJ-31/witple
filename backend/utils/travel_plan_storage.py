"""
여행 계획 저장 및 불러오기 유틸리티
"""
from typing import Dict, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models import TravelPlan
from database import get_db


def save_travel_plan(
    db: Session,
    user_id: str,
    travel_plan: Dict,
    query: str,
    raw_response: str,
    formatted_response: str,
    ui_response: Dict,
    session_id: Optional[str] = None
) -> Optional[TravelPlan]:
    """
    여행 계획을 DB에 저장

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        travel_plan: 파싱된 여행 계획 데이터
        query: 원본 사용자 요청
        raw_response: LLM 원본 응답
        formatted_response: 포맷된 응답
        ui_response: UI용 구조화된 응답
        session_id: 채팅 세션 ID

    Returns:
        저장된 TravelPlan 객체 또는 None (실패시)
    """
    try:
        # 제목 생성 (파싱된 데이터에서 추출 또는 기본값)
        title = travel_plan.get('title')
        if not title:
            # 쿼리에서 지역명 추출하여 제목 생성
            parsed_dates = travel_plan.get('parsed_dates', {})
            duration = travel_plan.get('duration', '')
            regions = []

            # travel_plan에서 지역 정보 찾기
            if travel_plan.get('places'):
                for place in travel_plan['places']:
                    region = place.get('region') or place.get('city')
                    if region and region not in regions:
                        regions.append(region)

            if regions:
                title = f"{', '.join(regions[:2])} {duration} 여행"
            else:
                title = f"{duration} 여행 계획"

        # 날짜 정보 파싱
        parsed_dates = travel_plan.get('parsed_dates', {})
        start_date = None
        end_date = None
        days_count = None

        if parsed_dates:
            start_date_str = parsed_dates.get('startDate')
            end_date_str = parsed_dates.get('endDate')

            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                except ValueError:
                    pass

            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                except ValueError:
                    pass

            # 일수 계산
            if start_date and end_date:
                days_count = (end_date - start_date).days + 1
            elif travel_plan.get('days'):
                days_count = len(travel_plan['days'])

        # TravelPlan 객체 생성
        travel_plan_obj = TravelPlan(
            user_id=user_id,
            title=title,
            query=query,
            travel_dates=travel_plan.get('travel_dates'),
            duration=travel_plan.get('duration'),
            start_date=start_date,
            end_date=end_date,
            days_count=days_count,
            itinerary=travel_plan.get('days', travel_plan.get('itinerary', [])),
            places=travel_plan.get('places', []),
            parsed_dates=parsed_dates,
            raw_response=raw_response,
            formatted_response=formatted_response,
            ui_response=ui_response,
            status='draft',
            session_id=session_id
        )

        # DB에 저장
        db.add(travel_plan_obj)
        db.commit()
        db.refresh(travel_plan_obj)

        # ID를 미리 저장 (세션이 닫히기 전에)
        plan_id = travel_plan_obj.id
        plan_title = travel_plan_obj.title
        print(f"✅ 여행 계획 저장 완료: ID {plan_id}, 제목: {plan_title}")
        return travel_plan_obj

    except SQLAlchemyError as e:
        print(f"❌ 여행 계획 저장 DB 오류: {e}")
        db.rollback()
        return None
    except Exception as e:
        print(f"❌ 여행 계획 저장 일반 오류: {e}")
        db.rollback()
        return None


def get_latest_travel_plan(db: Session, user_id: str, session_id: Optional[str] = None) -> Optional[TravelPlan]:
    """
    사용자의 최신 여행 계획 조회

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        session_id: 채팅 세션 ID (선택사항)

    Returns:
        최신 TravelPlan 객체 또는 None
    """
    try:
        query = db.query(TravelPlan).filter(TravelPlan.user_id == user_id)

        if session_id:
            query = query.filter(TravelPlan.session_id == session_id)

        latest_plan = query.order_by(TravelPlan.created_at.desc()).first()

        if latest_plan:
            print(f"✅ 최신 여행 계획 조회 완료: ID {latest_plan.id}")
        else:
            print(f"⚠️ 저장된 여행 계획이 없습니다 (user_id: {user_id})")

        return latest_plan

    except SQLAlchemyError as e:
        print(f"❌ 여행 계획 조회 DB 오류: {e}")
        return None
    except Exception as e:
        print(f"❌ 여행 계획 조회 일반 오류: {e}")
        return None


def confirm_travel_plan(db: Session, plan_id: int) -> bool:
    """
    여행 계획 확정

    Args:
        db: 데이터베이스 세션
        plan_id: 여행 계획 ID

    Returns:
        성공 여부
    """
    try:
        travel_plan = db.query(TravelPlan).filter(TravelPlan.id == plan_id).first()

        if not travel_plan:
            print(f"❌ 여행 계획을 찾을 수 없습니다: ID {plan_id}")
            return False

        travel_plan.status = 'confirmed'
        travel_plan.is_confirmed = True
        travel_plan.confirmed_at = datetime.now()

        db.commit()

        print(f"✅ 여행 계획 확정 완료: ID {plan_id}")
        return True

    except SQLAlchemyError as e:
        print(f"❌ 여행 계획 확정 DB 오류: {e}")
        db.rollback()
        return False
    except Exception as e:
        print(f"❌ 여행 계획 확정 일반 오류: {e}")
        db.rollback()
        return False


def get_travel_plan_by_id(db: Session, plan_id: int, user_id: str) -> Optional[TravelPlan]:
    """
    특정 여행 계획 조회 (사용자 검증 포함)

    Args:
        db: 데이터베이스 세션
        plan_id: 여행 계획 ID
        user_id: 사용자 ID

    Returns:
        TravelPlan 객체 또는 None
    """
    try:
        travel_plan = db.query(TravelPlan).filter(
            TravelPlan.id == plan_id,
            TravelPlan.user_id == user_id
        ).first()

        if travel_plan:
            print(f"✅ 여행 계획 조회 완료: ID {plan_id}")
        else:
            print(f"⚠️ 여행 계획을 찾을 수 없습니다: ID {plan_id}, user_id: {user_id}")

        return travel_plan

    except SQLAlchemyError as e:
        print(f"❌ 여행 계획 조회 DB 오류: {e}")
        return None
    except Exception as e:
        print(f"❌ 여행 계획 조회 일반 오류: {e}")
        return None


def get_user_travel_plans(
    db: Session,
    user_id: str,
    limit: int = 10,
    status: Optional[str] = None
) -> List[TravelPlan]:
    """
    사용자의 여행 계획 목록 조회

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        limit: 조회할 최대 개수
        status: 상태 필터 ('draft', 'confirmed', 'modified')

    Returns:
        TravelPlan 객체 리스트
    """
    try:
        query = db.query(TravelPlan).filter(TravelPlan.user_id == user_id)

        if status:
            query = query.filter(TravelPlan.status == status)

        plans = query.order_by(TravelPlan.created_at.desc()).limit(limit).all()

        print(f"✅ 여행 계획 목록 조회 완료: {len(plans)}개 (user_id: {user_id})")
        return plans

    except SQLAlchemyError as e:
        print(f"❌ 여행 계획 목록 조회 DB 오류: {e}")
        return []
    except Exception as e:
        print(f"❌ 여행 계획 목록 조회 일반 오류: {e}")
        return []


def travel_plan_to_dict(travel_plan: TravelPlan) -> Dict:
    """
    TravelPlan 객체를 딕셔너리로 변환 (워크플로우에서 사용하기 위해)

    Args:
        travel_plan: TravelPlan 객체

    Returns:
        딕셔너리 형태의 여행 계획 데이터
    """
    return {
        'id': travel_plan.id,
        'title': travel_plan.title,
        'query': travel_plan.query,
        'travel_dates': travel_plan.travel_dates,
        'duration': travel_plan.duration,
        'days': travel_plan.itinerary,
        'itinerary': travel_plan.itinerary,  # 호환성을 위해 중복
        'places': travel_plan.places or [],
        'parsed_dates': travel_plan.parsed_dates or {},
        'status': travel_plan.status,
        'confirmed_at': travel_plan.confirmed_at.isoformat() if travel_plan.confirmed_at else None,
        'created_at': travel_plan.created_at.isoformat(),
        'updated_at': travel_plan.updated_at.isoformat() if travel_plan.updated_at else None
    }