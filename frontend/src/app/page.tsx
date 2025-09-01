import Link from 'next/link'

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen py-2 bg-gray-50" style={{ backgroundColor: '#f9fafb' }}>
      <main className="flex flex-col items-center justify-center w-full flex-1 px-20 text-center">
        <h1 className="text-6xl font-bold text-gray-900" style={{ color: '#111827' }}>
          Welcome to{' '}
          <span className="text-blue-600" style={{ color: '#2563eb' }}>Witple!</span>
        </h1>

        <p className="mt-3 text-2xl text-gray-700" style={{ color: '#374151' }}>
          혁신적인 웹 애플리케이션에 오신 것을 환영합니다.
        </p>

        <div className="flex mt-6 max-w-4xl flex-wrap items-center justify-around sm:w-full">
          <Link
            href="/auth/login"
            className="p-6 mt-6 text-left border w-96 rounded-xl hover:text-blue-600 focus:text-blue-600 bg-white shadow-md hover:shadow-lg transition-shadow"
            style={{ backgroundColor: '#ffffff' }}
          >
            <h3 className="text-2xl font-bold text-gray-900" style={{ color: '#111827' }}>로그인 &rarr;</h3>
            <p className="mt-4 text-xl text-gray-700" style={{ color: '#374151' }}>
              기존 계정으로 로그인하세요.
            </p>
          </Link>

          <Link
            href="/auth/register"
            className="p-6 mt-6 text-left border w-96 rounded-xl hover:text-blue-600 focus:text-blue-600 bg-white shadow-md hover:shadow-lg transition-shadow"
            style={{ backgroundColor: '#ffffff' }}
          >
            <h3 className="text-2xl font-bold text-gray-900" style={{ color: '#111827' }}>회원가입 &rarr;</h3>
            <p className="mt-4 text-xl text-gray-700" style={{ color: '#374151' }}>
              새 계정을 만들어보세요.
            </p>
          </Link>
        </div>
      </main>
    </div>
  )
}
