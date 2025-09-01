'use client'

import { useState, useEffect } from 'react'

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[]
  readonly userChoice: Promise<{
    outcome: 'accepted' | 'dismissed'
    platform: string
  }>
  prompt(): Promise<void>
}

export default function PWAInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [showInstallPrompt, setShowInstallPrompt] = useState(false)

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
      setShowInstallPrompt(true)
    }

    window.addEventListener('beforeinstallprompt', handler)

    return () => window.removeEventListener('beforeinstallprompt', handler)
  }, [])

  const handleInstallClick = async () => {
    if (!deferredPrompt) return

    setShowInstallPrompt(false)
    deferredPrompt.prompt()

    const { outcome } = await deferredPrompt.userChoice
    console.log(`User response to the install prompt: ${outcome}`)

    setDeferredPrompt(null)
  }

  const handleDismiss = () => {
    setShowInstallPrompt(false)
    setDeferredPrompt(null)
  }

  if (!showInstallPrompt) return null

  return (
    <div className="fixed bottom-4 left-4 right-4 bg-white border border-gray-200 rounded-lg shadow-lg p-4 z-50 md:left-auto md:right-4 md:w-80">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <div className="w-10 h-10 bg-black rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">W</span>
          </div>
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900 text-sm">
            Witple 앱 설치
          </h3>
          <p className="text-gray-600 text-xs mt-1">
            홈 화면에 추가하여 더 빠르게 액세스하세요
          </p>
          <div className="flex gap-2 mt-3">
            <button
              onClick={handleInstallClick}
              className="bg-black text-white px-3 py-1 rounded text-xs font-medium hover:bg-gray-800 transition-colors"
            >
              설치
            </button>
            <button
              onClick={handleDismiss}
              className="bg-gray-100 text-gray-700 px-3 py-1 rounded text-xs font-medium hover:bg-gray-200 transition-colors"
            >
              나중에
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
