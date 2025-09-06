import "next-auth"
import "next-auth/jwt"

declare module "next-auth" {
  interface User {
    id?: string
    accessToken?: string
    backendToken?: string
  }
  
  interface Session {
    accessToken?: string
    backendToken?: string
    user?: User
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string
  }
}