from typing import List


def format_docs(docs):
    """검색된 문서들을 텍스트로 포맷팅 (유사도 점수 포함, 상위 30개로 제한)"""
    if not docs:
        return "NO_RELEVANT_DATA"  # 관련 데이터 없음을 나타내는 특별한 마커

    # 상위 30개 문서만 선택
    docs = docs[:30]
    print(f"📄 LLM에 전달할 문서 수: {len(docs)}개 (상위 30개로 제한)")

    formatted_docs = []
    for i, doc in enumerate(docs, 1):
        # 유사도 점수 추출
        similarity_score = doc.metadata.get('similarity_score', 'N/A')
        content = f"[여행지 {i}] (유사도: {similarity_score})\n{doc.page_content}"

        if doc.metadata:
            meta_info = []
            for key, value in doc.metadata.items():
                if value and key not in ['original_id', 'similarity_score', '_embedding', 'search_method']:  # 내부 키 제외
                    meta_info.append(f"{key}: {value}")
            if meta_info:
                content += f"\n({', '.join(meta_info)})"
        formatted_docs.append(content)

    return "\n\n".join(formatted_docs)


def process_response_for_frontend(response: str) -> tuple[str, List[str]]:
    """프론트엔드에서 쉽게 처리할 수 있도록 응답을 여러 형태로 변환"""

    # HTML 형태 변환 (\n -> <br>)
    response_html = response.replace('\n', '<br>')

    # 줄별 배열 형태 변환
    response_lines = []
    for line in response.split('\n'):
        # 빈 줄은 유지하되 공백 문자열로 변환
        response_lines.append(line.strip() if line.strip() else "")

    return response_html, response_lines