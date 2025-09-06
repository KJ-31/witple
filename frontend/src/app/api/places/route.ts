import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const query = searchParams.get('query')

  if (!query) {
    return NextResponse.json({ error: 'Query parameter is required' }, { status: 400 })
  }

  try {
    // OpenStreetMap Nominatim API 사용 (한국 지역 우선)
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?` +
      new URLSearchParams({
        format: 'json',
        q: query,
        limit: '8',
        'accept-language': 'ko,en',
        countrycodes: 'kr',
        addressdetails: '1',
        extratags: '1'
      }).toString(),
      {
        headers: {
          'User-Agent': 'Witple Social Media App (witple@example.com)'
        }
      }
    )

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    
    // 결과를 더 사용자 친화적으로 정리
    const formattedResults = data.map((item: any) => ({
      display_name: item.display_name,
      lat: item.lat,
      lon: item.lon,
      type: item.type || 'location',
      importance: item.importance || 0,
      // 주소 구성 요소 추가
      name: item.name,
      city: item.address?.city || item.address?.town || item.address?.village,
      state: item.address?.state,
      country: item.address?.country
    }))

    // 중요도순으로 정렬
    formattedResults.sort((a: any, b: any) => (b.importance || 0) - (a.importance || 0))

    return NextResponse.json(formattedResults)
    
  } catch (error) {
    console.error('Nominatim search error:', error)
    return NextResponse.json({ error: 'Search failed', details: error }, { status: 500 })
  }
}