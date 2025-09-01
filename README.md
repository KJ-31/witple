# Witple - Full Stack Application

FastAPI 백엔드와 Next.js 프론트엔드로 구성된 풀스택 애플리케이션입니다.

## 🏗️ 프로젝트 구조

```
witple/
├── backend/                 # FastAPI 백엔드
│   ├── main.py             # FastAPI 애플리케이션 진입점
│   ├── requirements.txt    # Python 의존성
│   ├── Dockerfile         # 백엔드 Docker 이미지
│   ├── config.py          # 설정 관리
│   ├── database.py        # 데이터베이스 연결
│   ├── models.py          # SQLAlchemy 모델
│   ├── schemas.py         # Pydantic 스키마
│   ├── auth_utils.py      # 인증 유틸리티
│   ├── routers/           # API 라우터
│   └── tests/             # 테스트 파일
├── frontend/              # Next.js 프론트엔드
│   ├── package.json       # Node.js 의존성
│   ├── Dockerfile         # 프론트엔드 Docker 이미지
│   ├── next.config.js     # Next.js 설정
│   ├── tailwind.config.js # Tailwind CSS 설정
│   └── src/
│       ├── app/           # Next.js App Router
│       ├── lib/           # 유틸리티 함수
│       └── types/         # TypeScript 타입 정의
├── k8s/                   # Kubernetes 매니페스트
│   ├── backend/           # 백엔드 전용 매니페스트
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   └── kustomization.yaml
│   ├── frontend/          # 프론트엔드 전용 매니페스트
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   └── kustomization.yaml
│   ├── shared/            # 공통 리소스
│   │   └── kustomization.yaml
│   ├── namespace.yaml     # 네임스페이스
│   ├── configmap.yaml     # 설정
│   ├── secret.yaml        # 시크릿
│   └── hpa.yaml          # Horizontal Pod Autoscaler
├── docker-compose.yml     # 로컬 개발 환경
└── .github/workflows/     # CI/CD 파이프라인
    └── ci-cd.yml         # 통합 CI/CD 워크플로우
```

## 🚀 로컬 개발 환경

### 사전 요구사항
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### 시작하기
```bash
# 1. 저장소 클론
git clone <repository-url>
cd witple

# 2. 환경 변수 설정
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 3. 로컬 개발 환경 시작
docker-compose up -d

# 4. 접속 확인
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# PostgreSQL: localhost:5432
# Redis: localhost:6379
```

### 환경 변수 설정
```bash
# Backend (.env)
DATABASE_URL=postgresql://user:password@localhost:5432/witple
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key

# Frontend (.env)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## ☁️ AWS 배포

### 사전 요구사항
1. **GitHub OIDC 설정** (필수)
   - [GitHub Actions OIDC 설정 가이드](docs/GITHUB_ACTIONS_OIDC_SETUP.md) 참조

2. **AWS 리소스 설정**
   - [AWS 설정 가이드](docs/AWS_SETUP_GUIDE.md) 참조

3. **GitHub Secrets 설정**
   ```bash
   AWS_ACCOUNT_ID=123456789012
   DOMAIN_NAME=yourdomain.com (선택사항)
   CERTIFICATE_ARN=arn:aws:acm:region:account:certificate/cert-id
   DATABASE_URL=postgresql://user:password@rds-endpoint:5432/dbname
   REDIS_URL=redis://redis-endpoint:6379
   SECRET_KEY=your-secret-key
   ```

### 배포 프로세스
1. **main 브랜치에 푸시**하면 자동으로 CI/CD 파이프라인이 실행됩니다
2. **변경 감지**: 백엔드, 프론트엔드, K8s 매니페스트 변경사항을 자동으로 감지
3. **스마트 배포**: 변경된 부분만 테스트하고 배포

## 🔄 CI/CD 파이프라인

### 워크플로우 구조
```mermaid
graph TD
    A[Push to main] --> B[Changes Detection]
    B --> C{Backend Changes?}
    B --> D{Frontend Changes?}
    B --> E{K8s Changes?}
    
    C -->|Yes| F[Test Backend]
    D -->|Yes| G[Test Frontend]
    E -->|Yes| F
    E -->|Yes| G
    
    F --> H[Build Backend]
    G --> I[Build Frontend]
    
    H --> J[Deploy]
    I --> J
    
    J --> K[Deploy Backend]
    J --> L[Deploy Frontend]
    J --> M[Setup Ingress]
    
    K --> N[Health Check]
    L --> N
    M --> N
```

### 스마트 배포 기능
- **변경 감지**: `dorny/paths-filter`를 사용하여 백엔드/프론트엔드 변경사항 자동 감지
- **선택적 테스트**: 변경된 부분만 테스트 실행
- **선택적 빌드**: 변경된 부분만 Docker 이미지 빌드
- **선택적 배포**: 변경된 부분만 Kubernetes에 배포
- **병렬 처리**: 백엔드와 프론트엔드 테스트/빌드를 병렬로 실행

### 배포 시나리오

#### 1. 백엔드만 변경
```bash
git add backend/
git commit -m "Update backend API"
git push origin main
```
- ✅ 백엔드 테스트만 실행
- ✅ 백엔드 이미지만 빌드
- ✅ 백엔드만 배포
- ⏭️ 프론트엔드는 기존 버전 유지

#### 2. 프론트엔드만 변경
```bash
git add frontend/
git commit -m "Update frontend UI"
git push origin main
```
- ✅ 프론트엔드 테스트만 실행
- ✅ 프론트엔드 이미지만 빌드
- ✅ 프론트엔드만 배포
- ⏭️ 백엔드는 기존 버전 유지

#### 3. 둘 다 변경
```bash
git add backend/ frontend/
git commit -m "Update both backend and frontend"
git push origin main
```
- ✅ 백엔드와 프론트엔드 테스트 병렬 실행
- ✅ 백엔드와 프론트엔드 이미지 병렬 빌드
- ✅ 백엔드와 프론트엔드 모두 배포

## 🏗️ Kubernetes 구조

### 분리된 매니페스트 구조
```
k8s/
├── backend/           # 백엔드 전용
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── kustomization.yaml
├── frontend/          # 프론트엔드 전용
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── kustomization.yaml
└── shared/            # 공통 리소스
    └── kustomization.yaml
```

### 배포 방식
- **백엔드**: `api.yourdomain.com` 또는 별도 ALB DNS
- **프론트엔드**: `yourdomain.com` 또는 별도 ALB DNS
- **공통 리소스**: 네임스페이스, ConfigMap, Secret, HPA

## 📊 모니터링 및 로그

### 배포 상태 확인
```bash
# Pod 상태 확인
kubectl get pods -n witple

# 배포 상태 확인
kubectl get deployments -n witple

# 서비스 상태 확인
kubectl get services -n witple

# Ingress 상태 확인
kubectl get ingress -n witple
```

### 로그 확인
```bash
# 백엔드 로그
kubectl logs -f deployment/witple-backend -n witple

# 프론트엔드 로그
kubectl logs -f deployment/witple-frontend -n witple
```

## 🔧 개발 가이드

### 백엔드 개발
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 프론트엔드 개발
```bash
cd frontend
npm install
npm run dev
```

### 테스트 실행
```bash
# 백엔드 테스트
cd backend
pytest

# 프론트엔드 테스트
cd frontend
npm run lint
npm run test
```

## 📝 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다.
