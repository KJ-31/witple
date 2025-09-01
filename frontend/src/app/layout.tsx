import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { PWAInstallPrompt } from '../components'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Witple',
  description: 'Witple - 사용자 행동 분석 플랫폼',
  manifest: '/manifest.json',
  themeColor: '#000000',
  viewport: {
    width: 'device-width',
    initialScale: 1,
    maximumScale: 1,
    userScalable: false,
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Witple',
  },
  formatDetection: {
    telephone: false,
  },
  icons: {
    icon: [
      { url: '/icons/icon-192x192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icons/icon-512x512.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: [
      { url: '/icons/icon-192x192.png', sizes: '192x192', type: 'image/png' },
    ],
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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko">
      <body className={inter.className}>
        <main className="min-h-screen bg-gray-50">
          {children}
        </main>
        <PWAInstallPrompt />
      </body>
    </html>
  )
}
