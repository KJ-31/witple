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
    
    // GitHub Actions 환경에서 더 안정적인 빌드를 위한 설정
    if (process.env.CI) {
      config.optimization.minimize = false;
      config.optimization.splitChunks = false;
    }
    
    return config;
  },
  // GitHub Actions 환경에서 더 안정적인 빌드를 위한 설정
  swcMinify: false,
  poweredByHeader: false,
}

module.exports = nextConfig
