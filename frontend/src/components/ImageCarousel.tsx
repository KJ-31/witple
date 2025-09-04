'use client'

import React, { useState } from 'react'
import Image from 'next/image'

interface ImageInfo {
  src: string
  alt: string
}

interface ImageCarouselProps {
  title: string
  images: ImageInfo[]
}

export function ImageCarousel({ title, images }: ImageCarouselProps) {
  const [currentIndex, setCurrentIndex] = useState(0)

  const nextImage = () => {
    setCurrentIndex((prev) => (prev + 1) % images.length)
  }

  const prevImage = () => {
    setCurrentIndex((prev) => (prev - 1 + images.length) % images.length)
  }

  if (!images || images.length === 0) {
    return null
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl font-semibold mb-6 text-gray-300">{title}</h2>

      <div className="relative">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {images.map((image, imageIndex) => (
            <div
              key={imageIndex}
              className={`relative group cursor-pointer overflow-hidden rounded-lg transition-all duration-500 aspect-[4/3] ${imageIndex === currentIndex
                  ? 'transform scale-105 ring-2 ring-blue-500'
                  : 'opacity-70 hover:opacity-100'
                }`}
              onClick={() => setCurrentIndex(imageIndex)}
            >
              <Image
                src={image.src}
                alt={image.alt}
                fill
                sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                className="object-cover"
              />
              <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all duration-300"></div>
            </div>
          ))}
        </div>

        {images.length > 2 && (
          <>
            <button onClick={prevImage} className="absolute left-0 top-1/2 transform -translate-y-1/2 -translate-x-4 bg-black bg-opacity-50 hover:bg-opacity-75 rounded-full p-2 transition-all duration-200">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            </button>
            <button onClick={nextImage} className="absolute right-0 top-1/2 transform -translate-y-1/2 translate-x-4 bg-black bg-opacity-50 hover:bg-opacity-75 rounded-full p-2 transition-all duration-200">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            </button>
          </>
        )}

        <div className="flex justify-center space-x-2 mt-4">
          {images.map((_, index) => (
            <button
              key={index}
              onClick={() => setCurrentIndex(index)}
              className={`w-3 h-3 rounded-full transition-all duration-200 ${index === currentIndex ? 'bg-blue-500' : 'bg-gray-600 hover:bg-gray-400'
                }`}
            />
          ))}
        </div>
      </div>
    </div>
  )
}