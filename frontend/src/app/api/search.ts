import apiClient from '../auth/login/api'

export interface SearchResult {
  id: string
  title: string
  description: string
  location: string
  image_url?: string
  type: 'attraction' | 'restaurant' | 'hotel' | 'activity'
}

export const searchPlaces = async (query: string): Promise<SearchResult[]> => {
  try {
    const response = await apiClient.get(`/api/v1/search?q=${encodeURIComponent(query)}`)
    return response.data
  } catch (error) {
    console.error('Search API error:', error)
    return []
  }
}