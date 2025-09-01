/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // 프록시 설정 제거 (API Route를 사용하므로)
  experimental: {
    // standalone 모드에서 path mapping이 제대로 동작하도록 설정
    outputFileTracingIncludes: {
      '/': ['./src/**/*'],
    },
    // 모든 소스 파일이 번들에 포함되도록 설정
    outputFileTracingExcludes: {},
  },
  // TypeScript path mapping을 webpack에서도 인식하도록 설정
  webpack: (config, { isServer }) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': require('path').resolve(__dirname, 'src'),
    };
    return config;
  },
}

module.exports = nextConfig
