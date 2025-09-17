const withPWA = require('next-pwa')({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
  // 문제 있는 파일들 제외
  buildExcludes: [/app-build-manifest\.json$/],
  // 런타임 캐싱 설정
  runtimeCaching: [
    {
      urlPattern: /^https:\/\/witple\.kro\.kr\/_next\/.*$/,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'next-assets',
        expiration: {
          maxEntries: 32,
          maxAgeSeconds: 24 * 60 * 60, // 24 hours
        },
      },
    },
    {
      urlPattern: /^https:\/\/maps\.googleapis\.com\/.*/i,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'google-maps-api',
        networkTimeoutSeconds: 10,
        expiration: {
          maxEntries: 32,
          maxAgeSeconds: 24 * 60 * 60, // 24 hours
        },
      },
    },
    {
      urlPattern: /^https:\/\/maps\.gstatic\.com\/.*/i,
      handler: 'CacheFirst',
      options: {
        cacheName: 'google-maps-static',
        expiration: {
          maxEntries: 32,
          maxAgeSeconds: 24 * 60 * 60, // 24 hours
        },
      },
    },
  ],
})

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
  // GitHub Actions 환경에서 더 안정적인 빌드를 위한 설정
  swcMinify: false,
  poweredByHeader: false,
}

module.exports = withPWA(nextConfig)
