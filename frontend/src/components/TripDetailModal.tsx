'use client'

import React, { useState } from 'react'
import { X, Calendar, MapPin, Clock, Copy, Check } from 'lucide-react'

interface TripDetailModalProps {
  trip: {
    id: number
    title: string
    description?: string
    start_date?: string
    end_date?: string
    status: string
    places: any[]
    created_at: string
    updated_at?: string
  }
  isOpen: boolean
  onClose: () => void
  onCopyTrip: (tripId: number) => Promise<void>
  isOwner?: boolean
}

export default function TripDetailModal({ 
  trip, 
  isOpen, 
  onClose, 
  onCopyTrip, 
  isOwner = false 
}: TripDetailModalProps) {
  const [isCopying, setIsCopying] = useState(false)
  const [copySuccess, setCopySuccess] = useState(false)

  if (!isOpen) return null

  const handleCopyTrip = async () => {
    try {
      setIsCopying(true)
      await onCopyTrip(trip.id)
      setCopySuccess(true)
      setTimeout(() => setCopySuccess(false), 2000)
    } catch (error) {
      console.error('일정 복사 실패:', error)
    } finally {
      setIsCopying(false)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  const getStatusText = (status: string) => {
    const statusMap: { [key: string]: string } = {
      'planning': '계획 중',
      'ongoing': '진행 중',
      'completed': '완료',
      'cancelled': '취소됨'
    }
    return statusMap[status] || status
  }

  const getStatusColor = (status: string) => {
    const colorMap: { [key: string]: string } = {
      'planning': 'bg-blue-500',
      'ongoing': 'bg-green-500',
      'completed': 'bg-gray-500',
      'cancelled': 'bg-red-500'
    }
    return colorMap[status] || 'bg-gray-500'
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <h2 className="text-xl font-bold text-white">여행 일정 상세</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Title and Status */}
          <div>
            <h3 className="text-2xl font-bold text-white mb-2">{trip.title}</h3>
            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 rounded-full text-xs font-medium text-white ${getStatusColor(trip.status)}`}>
                {getStatusText(trip.status)}
              </span>
              <span className="text-sm text-gray-400">
                {formatDate(trip.created_at)} 생성
              </span>
            </div>
          </div>

          {/* Description */}
          {trip.description && (
            <div>
              <h4 className="text-lg font-semibold text-white mb-2">설명</h4>
              <p className="text-gray-300 leading-relaxed">{trip.description}</p>
            </div>
          )}

          {/* Date Range */}
          {trip.start_date && trip.end_date && (
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Calendar className="w-5 h-5 text-blue-400" />
                <span className="text-white font-medium">여행 기간</span>
              </div>
              <div className="text-gray-300">
                {formatDate(trip.start_date)} ~ {formatDate(trip.end_date)}
              </div>
            </div>
          )}

          {/* Places */}
          <div>
            <h4 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              <MapPin className="w-5 h-5 text-blue-400" />
              방문 장소 ({trip.places.length}개)
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {trip.places.map((place, index) => (
                <div key={index} className="bg-gray-700 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                    <span className="text-white text-sm">
                      {typeof place === 'string' ? place : place.name || `장소 ${index + 1}`}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          {!isOwner && (
            <div className="flex gap-3 pt-4 border-t border-gray-700">
              <button
                onClick={handleCopyTrip}
                disabled={isCopying}
                className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-medium transition-colors ${
                  copySuccess
                    ? 'bg-green-600 text-white'
                    : isCopying
                    ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                {isCopying ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                    복사 중...
                  </>
                ) : copySuccess ? (
                  <>
                    <Check className="w-4 h-4" />
                    복사 완료!
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    내 일정으로 복사
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
