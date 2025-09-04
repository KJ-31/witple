import { NextRequest, NextResponse } from 'next/server';

// 환경별 백엔드 URL 설정
const getBackendUrl = () => {
  // 프로덕션 환경에서는 백엔드 서비스 이름 사용
  if (process.env.NODE_ENV === 'production') {
    return 'http://witple-backend-service:80'; // Kubernetes 서비스 이름
  }
  
  // 개발 환경에서는 환경 변수 또는 기본값 사용
  return process.env.API_INTERNAL_URL || 'http://localhost:8000';
};

const API_INTERNAL_URL = getBackendUrl();

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxyRequest(request, params.path, 'GET');
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxyRequest(request, params.path, 'POST');
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxyRequest(request, params.path, 'PUT');
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxyRequest(request, params.path, 'DELETE');
}

async function proxyRequest(
  request: NextRequest,
  pathSegments: string[],
  method: string
) {
  try {
    console.log('=== PROXY REQUEST START ===');
    console.log('NODE_ENV:', process.env.NODE_ENV);
    console.log('Request method:', method);
    console.log('Request URL:', request.url);
    console.log('Path segments:', pathSegments);
    
    const path = pathSegments.join('/');
    const url = new URL(request.url);
    const queryString = url.search;
    
    const backendUrl = `${API_INTERNAL_URL}/${path}${queryString}`;
    
    console.log('API_INTERNAL_URL:', API_INTERNAL_URL);
    console.log('Final backend URL:', backendUrl);

    const headers: HeadersInit = {};

    // 원본 요청의 Content-Type을 그대로 전달
    const contentType = request.headers.get('content-type');
    if (contentType) {
      headers['Content-Type'] = contentType;
    }

    // 인증 헤더가 있으면 전달
    const authHeader = request.headers.get('authorization');
    if (authHeader) {
      headers['authorization'] = authHeader;
    }

    let body: string | undefined;
    if (['POST', 'PUT'].includes(method)) {
      body = await request.text();
    }

    console.log(`Proxying ${method} request to: ${backendUrl}`);
    console.log(`Headers:`, headers);
    console.log(`Body length:`, body ? body.length : 0);
    console.log('=== PROXY REQUEST END ===');

    const response = await fetch(backendUrl, {
      method,
      headers,
      body,
    });

    console.log('=== PROXY RESPONSE ===');
    console.log('Response status:', response.status);
    console.log('Response statusText:', response.statusText);
    console.log('Response headers:', Object.fromEntries(response.headers.entries()));

    const data = await response.text();
    
    console.log('Response data length:', data.length);
    console.log('Response data preview:', data.substring(0, 200));
    console.log('=== PROXY RESPONSE END ===');
    
    return new NextResponse(data, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'application/json',
      },
    });
  } catch (error: any) {
    console.error('=== PROXY ERROR ===');
    console.error('Proxy error:', error);
    console.error('Error details:', {
      message: error.message,
      name: error.name,
      stack: error.stack,
      type: typeof error
    });
    console.error('=== PROXY ERROR END ===');
    
    return NextResponse.json(
      { error: 'Internal server error', details: error.message },
      { status: 500 }
    );
  }
}
