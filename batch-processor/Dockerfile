# AWS Batch Processor for Witple User Behavior Vectorization
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치를 위한 파일 복사
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 환경 변수 기본값 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV AWS_DEFAULT_REGION=ap-northeast-2

# Hugging Face 캐시 디렉토리 설정 (컨테이너 내에서)
ENV TRANSFORMERS_CACHE=/app/models_cache
ENV SENTENCE_TRANSFORMERS_HOME=/app/models_cache
RUN mkdir -p /app/models_cache

# 헬스체크 스크립트
COPY healthcheck.py ./
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python healthcheck.py || exit 1

# 메인 처리 스크립트 실행
CMD ["python", "process_batch.py"]