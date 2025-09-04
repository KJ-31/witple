import { NextRequest, NextResponse } from 'next/server';

const API_INTERNAL_URL = process.env.API_INTERNAL_URL || 'http://localhost:8000';

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
    const path = pathSegments.join('/');
    const url = new URL(request.url);
    const queryString = url.search;
    
    // 중복된 /api 제거하고 올바른 백엔드 URL 생성
    const backendUrl = `${API_INTERNAL_URL}/api/v1/${path}${queryString}`;

    console.log('=== PROXY DEBUG INFO ===');
    console.log(`Request URL: ${request.url}`);
    console.log(`Path segments:`, pathSegments);
    console.log(`API_INTERNAL_URL: ${API_INTERNAL_URL}`);
    console.log(`Final backend URL: ${backendUrl}`);
    console.log(`Method: ${method}`);

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
    console.log('=== END DEBUG INFO ===');

    const response = await fetch(backendUrl, {
      method,
      headers,
      body,
    });

    const data = await response.text();
    
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
      stack: error.stack
    });
    console.error('=== END ERROR ===');
    
    return NextResponse.json(
      { error: 'Internal server error', details: error.message },
      { status: 500 }
    );
  }
}
