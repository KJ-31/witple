// app/layout.tsx
import './globals.css'
import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import { PWAInstallPrompt } from '../components'
import NextAuthSessionProvider from '../components/SessionProvider'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Witple',
  description: 'Witple - 사용자 행동 분석 플랫폼',
  manifest: '/manifest.json',
  // ❌ themeColor 제거 (viewport로 이동)
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Witple',
  },
  formatDetection: { telephone: false },
  icons: {
    icon: [
      { url: '/icons/icon-192x192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icons/icon-512x512.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: [{ url: '/icons/icon-192x192.png', sizes: '192x192', type: 'image/png' }],
  },
  other: {
    'mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-status-bar-style': 'default',
    'apple-mobile-web-app-title': 'Witple',
    'application-name': 'Witple',
    'msapplication-TileColor': '#000000',
    'msapplication-tap-highlight': 'no',
  },
}

// ✅ viewport로 이동
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: '#000000',
  // 라이트/다크 분기 예시:
  // themeColor: [
  //   { media: '(prefers-color-scheme: light)', color: '#ffffff' },
  //   { media: '(prefers-color-scheme: dark)', color: '#000000' },
  // ],
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="h-full">
      <body className={`${inter.className} h-full bg-gray-50 overflow-y-auto no-scrollbar`}>
        <NextAuthSessionProvider>
          <main className="min-h-[100dvh]">
            {children}
          </main>
          <PWAInstallPrompt />
        </NextAuthSessionProvider>
      </body>
    </html>
  )
}
