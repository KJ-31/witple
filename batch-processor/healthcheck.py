#!/usr/bin/env python3
"""
AWS Batch 컨테이너 헬스체크 스크립트
"""
import os
import sys
import logging

def main():
    """간단한 헬스체크 - 필요한 환경변수와 파일 존재 확인"""
    try:
        # 필수 환경 변수 확인
        required_vars = ['DATABASE_URL']
        for var in required_vars:
            if not os.getenv(var):
                print(f"Missing environment variable: {var}")
                sys.exit(1)
        
        # 메인 스크립트 파일 존재 확인
        if not os.path.exists('/app/process_batch.py'):
            print("Main processing script not found")
            sys.exit(1)
        
        # 모델 캐시 디렉토리 확인
        if not os.path.exists('/app/models_cache'):
            print("Models cache directory not found")
            sys.exit(1)
        
        print("Health check passed")
        sys.exit(0)
        
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()