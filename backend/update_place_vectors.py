"""
장소 벡터 데이터 업데이트 스크립트
place_id와 table_name을 메타데이터에 포함하여 벡터화 재실행
"""
import sys
from sqlalchemy import create_engine, text
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document
from typing import List, Dict, Any
# 데이터베이스 연결 설정
CONNECTION_STRING = "postgresql+psycopg://postgres:witple123!@witple-pub-database.cfme8csmytkv.ap-northeast-2.rds.amazonaws.com:5432/witple_db"
# 임베딩 모델 설정 (안정적인 sentence-transformers 모델 사용)
print("🧠 Sentence Transformers 임베딩 모델 초기화 중...")
embeddings = HuggingFaceEmbeddings(
    model_name='sentence-transformers/all-MiniLM-L12-v2',
)
def get_all_places_data() -> List[Dict[str, Any]]:
    """place_recommendations 테이블에서 장소 데이터 수집"""
    engine = create_engine(CONNECTION_STRING)
    all_places = []
    print("📊 place_recommendations 테이블에서 데이터 수집 중...")
    query = """
    SELECT
        place_id,
        table_name,
        name,
        overview,
        region,
        city,
        category
    FROM place_recommendations
    WHERE name IS NOT NULL
    AND overview IS NOT NULL
    ORDER BY place_id
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            for row in rows:
                place_data = {
                    'place_id': str(row.place_id),
                    'table_name': row.table_name or 'nature',
                    'name': row.name or '',
                    'overview': row.overview or '',
                    'region': row.region or '',
                    'city': row.city or '',
                    'category': row.category or ''
                }
                all_places.append(place_data)
            print(f"   ✅ place_recommendations: {len(rows)}개 장소 수집 완료")
    except Exception as e:
        print(f"   ❌ place_recommendations 테이블 오류: {e}")
        return []
    print(f"🎯 전체 수집 완료: {len(all_places)}개 장소")
    return all_places
def create_documents_with_metadata(places_data: List[Dict[str, Any]]) -> List[Document]:
    """장소 데이터를 Document 객체로 변환 (메타데이터 포함)"""
    documents = []
    for place in places_data:
        # 텍스트 콘텐츠 구성 (기존 방식과 동일)
        content_parts = []
        if place['name']:
            content_parts.append(f"이름: {place['name']}")
        if place['overview']:
            content_parts.append(f"설명: {place['overview']}")
        if place['region']:
            content_parts.append(f"지역: {place['region']}")
        if place['city']:
            content_parts.append(f"도시: {place['city']}")
        if place['category']:
            content_parts.append(f"카테고리: {place['category']}")
        content = "\n".join(content_parts)
        # 메타데이터 구성 (place_id, table_name 추가)
        metadata = {
            'place_id': place['place_id'],
            'table_name': place['table_name'],
            'name': place['name'],
            'region': place['region'],
            'city': place['city'],
            'category': place['category']
        }
        # Document 생성
        doc = Document(
            page_content=content,
            metadata=metadata
        )
        documents.append(doc)
    print(f"📝 {len(documents)}개 Document 생성 완료")
    return documents
def update_langchain_pg_embedding(documents: List[Document]):
    """langchain_pg_embedding 테이블 업데이트"""
    print("🔄 langchain_pg_embedding 테이블 업데이트 중...")
    try:
        # 먼저 기존 컬렉션 삭제
        print("📝 기존 langchain_pg_embedding 데이터 삭제 중...")
        PGVector(
            embeddings=embeddings,
            collection_name="place_recommendations",
            connection=CONNECTION_STRING,
            pre_delete_collection=True,  # 기존 데이터 삭제
        )
        print("📊 새로운 벡터 임베딩 생성 및 저장 중...")
        # 새로운 벡터스토어 생성 및 문서 추가
        vectorstore = PGVector(
            embeddings=embeddings,
            collection_name="place_recommendations",
            connection=CONNECTION_STRING,
            pre_delete_collection=False,  # 이미 삭제했으므로 False
        )
        # 배치 단위로 문서 추가 (메모리 및 성능 최적화)
        batch_size = 100
        total_docs = len(documents)
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]
            print(f"   배치 진행률: {i + len(batch)}/{total_docs} ({(i + len(batch))/total_docs*100:.1f}%)")
            try:
                vectorstore.add_documents(batch)
            except Exception as batch_error:
                print(f"   ⚠️ 배치 {i//batch_size + 1} 처리 오류: {batch_error}")
                # 개별 문서로 재시도
                for doc in batch:
                    try:
                        vectorstore.add_documents([doc])
                    except Exception as doc_error:
                        print(f"   ❌ 문서 처리 실패: {doc.page_content[:50]}... - {doc_error}")
                        continue
        print("✅ langchain_pg_embedding 업데이트 완료!")
        print(f"📊 총 처리된 문서: {total_docs}개")
    except Exception as e:
        print(f"❌ langchain_pg_embedding 업데이트 오류: {e}")
        import traceback
        traceback.print_exc()
        raise
def update_place_recommendations(places_data: List[Dict[str, Any]]):
    """place_recommendations 테이블 업데이트 (UPSERT 방식)"""
    print("🔄 place_recommendations 테이블 업데이트 중...")
    engine = create_engine(CONNECTION_STRING)
    try:
        with engine.connect() as conn:
            # 트랜잭션 시작
            trans = conn.begin()
            try:
                insert_count = 0
                update_count = 0
                batch_size = 100
                for i in range(0, len(places_data), batch_size):
                    batch = places_data[i:i + batch_size]
                    for place in batch:
                        # 벡터 생성
                        text_for_embedding = f"{place['name']} {place['overview']} {place['region']} {place['city']} {place['category']}"

                        try:
                            vector = embeddings.embed_query(text_for_embedding)

                            # 벡터 유효성 검사
                            if not vector or len(vector) == 0:
                                print(f"   ❌ 빈 벡터 생성됨: {place['name']}")
                                continue

                            if all(x == 0 for x in vector):
                                print(f"   ❌ 모든 값이 0인 벡터: {place['name']}")
                                continue

                            # PostgreSQL vector 타입으로 변환
                            vector_str = '[' + ','.join(map(str, vector)) + ']'
                            print(f"   ✅ 벡터 생성 성공: {place['name']} (차원: {len(vector)}, 첫 3개: {vector[:3]})")
                            print(f"   📝 벡터 문자열 형식: {vector_str[:100]}...")

                        except Exception as embed_error:
                            print(f"   ❌ 임베딩 생성 실패: {place['name']} - {embed_error}")
                            continue
                        # 먼저 존재하는지 확인
                        check_query = text("""
                        SELECT id FROM place_recommendations
                        WHERE place_id = :place_id AND table_name = :table_name
                        LIMIT 1
                        """)
                        existing = conn.execute(check_query, {
                            'place_id': place['place_id'],
                            'table_name': place['table_name']
                        }).fetchone()
                        if existing:
                            # UPDATE (벡터를 vector 타입으로 변환)
                            update_query = text("""
                            UPDATE place_recommendations SET
                                name = :name,
                                region = :region,
                                city = :city,
                                category = :category,
                                overview = :overview,
                                vector = CAST(:vector AS vector)
                            WHERE place_id = :place_id AND table_name = :table_name
                            """)
                            query_to_execute = update_query
                            update_count += 1
                        else:
                            # INSERT (벡터를 vector 타입으로 변환)
                            insert_query = text("""
                            INSERT INTO place_recommendations
                            (place_id, table_name, name, region, city, category, overview, vector)
                            VALUES (:place_id, :table_name, :name, :region, :city, :category, :overview, CAST(:vector AS vector))
                            """)
                            query_to_execute = insert_query
                            insert_count += 1
                        try:
                            # DB 저장 전 벡터 재검증
                            if len(vector_str) < 100:  # 너무 짧은 벡터 문자열 체크
                                print(f"   ❌ 벡터 문자열이 너무 짧음: {place['name']} (길이: {len(vector_str)})")
                                continue

                            conn.execute(query_to_execute, {
                                'place_id': place['place_id'],
                                'table_name': place['table_name'],
                                'name': place['name'],
                                'region': place['region'],
                                'city': place['city'],
                                'category': place['category'],
                                'overview': place['overview'],
                                'vector': vector_str
                            })
                            print(f"   💾 DB 저장 성공: {place['name']}")

                        except Exception as db_error:
                            print(f"   ❌ DB 저장 실패: {place['name']} - {db_error}")
                            continue
                    if (i // batch_size + 1) % 10 == 0:
                        print(f"   진행률: {i+len(batch)}/{len(places_data)} ({(i+len(batch))/len(places_data)*100:.1f}%)")
                # 커밋
                trans.commit()
                print(f"✅ place_recommendations 업데이트 완료:")
                print(f"   📝 새로 추가: {insert_count}개")
                print(f"   🔄 업데이트: {update_count}개")
                print(f"   📊 총 처리: {insert_count + update_count}개")
            except Exception as e:
                trans.rollback()
                raise e
    except Exception as e:
        print(f"❌ place_recommendations 업데이트 오류: {e}")
        raise
def main():
    """메인 실행 함수"""
    print("🚀 장소 벡터 데이터 업데이트 시작")
    print("=" * 60)
    try:
        # 1. 모든 장소 데이터 수집
        print("\n📊 1단계: 장소 데이터 수집")
        places_data = get_all_places_data()
        if not places_data:
            print("❌ 수집된 장소 데이터가 없습니다.")
            return
        # 2. Document 객체 생성
        print("\n📝 2단계: Document 객체 생성")
        documents = create_documents_with_metadata(places_data)
        # 3. langchain_pg_embedding 업데이트
        print("\n🔄 3단계: langchain_pg_embedding 업데이트")
        update_langchain_pg_embedding(documents)
        # 4. place_recommendations 업데이트
        print("\n🔄 4단계: place_recommendations 업데이트")
        update_place_recommendations(places_data)
        print("\n" + "=" * 60)
        print("🎉 벡터 데이터 업데이트 완료!")
        print(f"📊 총 처리된 장소: {len(places_data)}개")
        print("✅ langchain_pg_embedding: 업데이트 완료")
        print("✅ place_recommendations: 업데이트 완료")
    except Exception as e:
        print(f"\n❌ 업데이트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
if __name__ == "__main__":
    main()