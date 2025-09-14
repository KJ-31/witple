# Collection Server Dockerfile
FROM node:18-alpine

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치 (curl for health check)
RUN apk add --no-cache curl

# 패키지 파일들 먼저 복사 (Docker 캐시 최적화)
COPY package*.json ./

# 의존성 설치 (프로덕션 모드)
RUN npm ci --only=production && npm cache clean --force

# 애플리케이션 소스 코드 복사
COPY . .

# non-root 사용자 생성 및 권한 설정
RUN addgroup -g 1001 -S nodejs && \
    adduser -S -u 1001 -G nodejs nodejs && \
    chown -R nodejs:nodejs /app

# nodejs 사용자로 전환
USER nodejs

# 포트 노출
EXPOSE 8080

# 환경변수 기본값 설정
ENV NODE_ENV=production
ENV PORT=8080
ENV MAX_BUFFER_SIZE=100
ENV MAX_BUFFER_AGE=300000

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# 애플리케이션 실행
CMD ["node", "server.js"]