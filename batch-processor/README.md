# Witple AWS Batch Processor

사용자 행동 데이터를 S3에서 읽어서 BERT 벡터로 변환하여 PostgreSQL에 저장하는 AWS Batch 처리 시스템입니다.

## 📋 개요

이 시스템은 다음 과정을 자동화합니다:
1. S3에서 사용자 행동 데이터 (JSON) 읽기
2. BERT 모델을 사용하여 사용자 행동을 384차원 벡터로 변환
3. 장소별 통계 및 벡터 계산
4. PostgreSQL 데이터베이스에 벡터 데이터 저장
5. Main EC2에 처리 완료 알림 전송

## 🏗️ 아키텍처

```
Collection Server → S3 → AWS Batch → PostgreSQL
                              ↓
                    Main EC2 (Webhook)
```

## 📦 파일 구조

```
batch-processor/
├── Dockerfile              # Docker 컨테이너 설정
├── requirements.txt         # Python 의존성
├── process_batch.py        # 메인 처리 로직
├── healthcheck.py          # 컨테이너 헬스체크
├── deploy.sh              # AWS 배포 스크립트
└── README.md              # 이 문서
```

## 🚀 배포 방법

### 1. 사전 요구사항

- AWS CLI 설정
- Docker 설치
- 다음 AWS 리소스가 미리 생성되어 있어야 함:
  - VPC 및 서브넷
  - Security Groups
  - AWS Batch Compute Environment
  - AWS Batch Job Queue
  - IAM 역할 (witple-batch-job-execution-role)

### 2. 배포 실행

```bash
cd batch-processor
./deploy.sh
```

이 스크립트는 다음을 자동으로 수행합니다:
- Docker 이미지 빌드
- ECR에 이미지 푸시
- AWS Batch Job Definition 생성
- CloudWatch Log Group 생성

### 3. 테스트 작업 제출

```bash
SUBMIT_TEST_JOB=true ./deploy.sh
```

## ⚙️ 환경 변수

### 필수 환경 변수

- `DATABASE_URL`: PostgreSQL 연결 문자열
- `AWS_BATCH_JOB_ID`: Batch 작업 ID (AWS에서 자동 설정)
- `AWS_BATCH_JOB_NAME`: Batch 작업 이름 (AWS에서 자동 설정)

### 선택적 환경 변수

- `AWS_REGION`: AWS 리전 (기본값: ap-northeast-2)
- `S3_BUCKET`: S3 버킷 이름 (기본값: user-actions-data)
- `S3_PREFIX`: S3 접두사 (기본값: user-actions/)
- `WEBHOOK_URL`: 완료 알림을 받을 webhook URL
- `BATCH_ID`: 배치 ID (기본값: 자동 생성)

## 📊 처리 과정

### 1. 데이터 수집
- S3에서 `batch-*.json` 파일들을 검색
- GZIP 압축 파일 지원
- 최대 50개 파일까지 한 번에 처리

### 2. 벡터화 처리
- **사용자 벡터**: 사용자의 행동 패턴을 BERT로 벡터화
- **장소 벡터**: 장소별 통계와 특성을 벡터화
- **점수 계산**: 좋아요, 북마크, 클릭 점수 (0-100 스케일)

### 3. 데이터베이스 저장
- `user_behavior_vectors` 테이블에 사용자 벡터 저장
- `place_vectors` 테이블에 장소 벡터 저장
- UPSERT 방식으로 기존 데이터 업데이트

### 4. 알림 전송
- 처리 완료 시 Main EC2에 webhook 알림
- 성공/실패 상태와 처리 통계 포함

## 🐳 Docker 이미지

### 베이스 이미지
- `python:3.9-slim`
- 총 크기: 약 2-3GB (BERT 모델 포함)

### 리소스 요구사항
- **CPU**: 2 vCPU
- **메모리**: 4096 MB
- **플랫폼**: Fargate
- **실행 시간**: 최대 1시간

## 📝 로깅

### CloudWatch Logs
- Log Group: `/aws/batch/job`
- Log Stream: `witple-batch/{job_id}`

### 로그 레벨
- `INFO`: 일반 처리 상태
- `ERROR`: 오류 및 예외
- `DEBUG`: 상세 디버그 정보

## 🔧 모니터링

### 메트릭
- 처리된 파일 수
- 처리된 액션 수
- 생성된 사용자/장소 벡터 수
- 처리 시간
- 오류 수

### 헬스체크
- 환경 변수 확인
- 필수 파일 존재 확인
- 30초마다 실행

## 🚨 오류 처리

### 재시도 정책
- 최대 2회 재시도
- 각 시도마다 1시간 제한시간

### 일반적인 오류
1. **S3 권한 오류**: IAM 역할 권한 확인
2. **데이터베이스 연결 오류**: DATABASE_URL 및 네트워크 확인
3. **메모리 부족**: 처리할 파일 수 조정
4. **BERT 모델 다운로드 실패**: 인터넷 연결 확인

## 🔒 보안

### IAM 권한
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::user-actions-data",
                "arn:aws:s3:::user-actions-data/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

### 네트워크 보안
- Private 서브넷에서 실행
- 데이터베이스 접근을 위한 Security Group 설정
- NAT Gateway를 통한 인터넷 접근 (모델 다운로드용)

## 📈 성능 최적화

### 모델 캐싱
- BERT 모델을 컨테이너 이미지에 사전 다운로드
- 첫 실행 시 모델 로드 시간 단축

### 배치 처리
- 여러 파일을 한 번에 처리
- 사용자/장소별 데이터 집계 최적화

### 데이터베이스 최적화
- UPSERT 쿼리로 중복 처리 방지
- 인덱스 활용으로 성능 향상

## 🐛 디버깅

### 로그 확인
```bash
aws logs get-log-events \
  --log-group-name /aws/batch/job \
  --log-stream-name witple-batch/{job_id}
```

### 작업 상태 확인
```bash
aws batch describe-jobs --jobs {job_id}
```

### 컨테이너 로컬 테스트
```bash
docker build -t witple-batch-processor .
docker run --env-file .env witple-batch-processor
```