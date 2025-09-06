import NextAuth from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'
import CredentialsProvider from 'next-auth/providers/credentials'
import type { NextAuthOptions } from 'next-auth'

const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' }
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null
        }

        try {
          const apiUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
          
          const formData = new URLSearchParams()
          formData.append('username', credentials.email)
          formData.append('password', credentials.password)

          const response = await fetch(`${apiUrl}/api/v1/auth/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData.toString(),
          })

          if (response.ok) {
            const data = await response.json()
            
            // Get user details
            const userResponse = await fetch(`${apiUrl}/api/v1/auth/me`, {
              headers: {
                'Authorization': `Bearer ${data.access_token}`,
              },
            })
            
            if (userResponse.ok) {
              const userData = await userResponse.json()
              return {
                id: userData.user_id,
                email: userData.email,
                name: userData.name,
                backendToken: data.access_token
              }
            }
          }
        } catch (error) {
          console.error('Login error:', error)
        }
        
        return null
      }
    })
  ],
  secret: process.env.NEXTAUTH_SECRET,
  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === 'google') {
        try {
          console.log('Sending user data to backend:', { user, account })
          
          // 백엔드에 사용자 정보 전송 (Docker 환경에서는 내부 URL 사용)
          const apiUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
          const response = await fetch(`${apiUrl}/api/v1/auth/oauth/callback`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              provider: 'google',
              provider_user_id: account.providerAccountId,
              email: user.email,
              name: user.name,
              image: user.image,
            }),
          })
          
          if (response.ok) {
            const data = await response.json()
            console.log('Backend response:', data)
            // 백엔드에서 받은 토큰을 user 객체에 추가
            ;(user as any).backendToken = data.access_token
            return true
          } else {
            console.error('Backend error:', await response.text())
            return false
          }
        } catch (error) {
          console.error('OAuth callback error:', error)
          return false
        }
      }
      return true
    },
    async jwt({ token, user }) {
      // 로그인 시 토큰에 백엔드 토큰 추가
      if ((user as any)?.backendToken) {
        ;(token as any).backendToken = (user as any).backendToken
      }
      return token
    },
    async session({ session, token }) {
      // 세션에 백엔드 토큰 추가
      if ((token as any).backendToken) {
        ;(session as any).backendToken = (token as any).backendToken
      }
      return session
    }
  }
}

const handler = NextAuth(authOptions)

export { handler as GET, handler as POST }