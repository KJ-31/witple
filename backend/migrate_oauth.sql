-- OAuth 지원을 위한 데이터베이스 스키마 업데이트

-- 1. users 테이블의 pw 컬럼을 NULL 허용으로 변경
ALTER TABLE users ALTER COLUMN pw DROP NOT NULL;

-- 2. oauth_accounts 테이블 생성 (이미 존재할 수 있음)
CREATE TABLE IF NOT EXISTS oauth_accounts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES users(user_id),
    provider VARCHAR NOT NULL,
    provider_user_id VARCHAR NOT NULL,
    email VARCHAR,
    name VARCHAR,
    profile_picture VARCHAR,
    access_token TEXT,
    refresh_token TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, provider_user_id)
);

-- 3. 인덱스 생성 (성능 향상)
CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user_id ON oauth_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_accounts_provider ON oauth_accounts(provider, provider_user_id);