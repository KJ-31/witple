import NextAuth from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'
import type { NextAuthOptions } from 'next-auth'

const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    })
  ],
  secret: process.env.NEXTAUTH_SECRET,
  callbacks: {
    async signIn({ user, account, profile }) {
      if (account?.provider === 'google') {
        try {
          console.log('Sending user data to backend:', { user, account })
          
          // 백엔드에 사용자 정보 전송 (Docker 환경에서는 내부 URL 사용)
          const apiUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL
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