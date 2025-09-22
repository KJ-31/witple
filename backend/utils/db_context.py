"""
DB 컨텍스트 매니저 유틸리티
"""
from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import SessionLocal


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    DB 세션 컨텍스트 매니저
    자동으로 세션을 열고 닫으며, 에러 시 롤백 처리
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        print(f"❌ DB 작업 중 오류 발생, 롤백 처리: {e}")
        db.rollback()
        raise
    except Exception as e:
        print(f"❌ 예상치 못한 오류 발생, 롤백 처리: {e}")
        db.rollback()
        raise
    finally:
        db.close()


class SafeDBOperation:
    """
    안전한 DB 작업을 위한 헬퍼 클래스
    """

    @staticmethod
    def execute_with_retry(operation, max_retries: int = 3, **kwargs):
        """
        DB 작업을 재시도와 함께 실행

        Args:
            operation: 실행할 함수
            max_retries: 최대 재시도 횟수
            **kwargs: operation에 전달할 인자들

        Returns:
            작업 결과 또는 None (실패시)
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                with get_db_context() as db:
                    return operation(db, **kwargs)
            except SQLAlchemyError as e:
                last_error = e
                print(f"⚠️ DB 작업 시도 {attempt + 1}/{max_retries} 실패: {e}")
                if attempt == max_retries - 1:
                    print(f"❌ 모든 재시도 실패. 마지막 오류: {e}")
                    break
            except Exception as e:
                last_error = e
                print(f"❌ 예상치 못한 오류로 재시도 중단: {e}")
                break

        return None