"""
place_features 테이블에 place_recommendations 테이블의 벡터값 매핑
name이 일치하는 행에 벡터값을 복사하는 스크립트
"""
import sys
from sqlalchemy import create_engine, text
from typing import List, Tuple

# 데이터베이스 연결 설정
CONNECTION_STRING = "postgresql+psycopg://postgres:witple123!@witple-pub-database.cfme8csmytkv.ap-northeast-2.rds.amazonaws.com:5432/witple_db"

def check_table_structures():
    """테이블 구조 확인"""
    engine = create_engine(CONNECTION_STRING)

    print("=== 테이블 구조 확인 ===")

    with engine.connect() as conn:
        # place_features 테이블 구조
        print("\n📊 place_features 테이블 구조:")
        features_schema = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'place_features'
            ORDER BY ordinal_position
        """))

        for row in features_schema:
            print(f"  - {row.column_name}: {row.data_type} ({'NULL' if row.is_nullable == 'YES' else 'NOT NULL'})")

        # place_recommendations 테이블 구조
        print("\n📊 place_recommendations 테이블 구조:")
        recommendations_schema = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'place_recommendations'
            ORDER BY ordinal_position
        """))

        for row in recommendations_schema:
            print(f"  - {row.column_name}: {row.data_type} ({'NULL' if row.is_nullable == 'YES' else 'NOT NULL'})")

        # 샘플 데이터 확인
        print("\n📊 place_features 샘플 데이터:")
        features_sample = conn.execute(text("""
            SELECT id, place_id, name, vector IS NOT NULL as has_vector
            FROM place_features
            LIMIT 5
        """))

        for row in features_sample:
            print(f"  - ID: {row.id}, Place ID: {row.place_id}, Name: {row.name}, Has Vector: {row.has_vector}")

        print("\n📊 place_recommendations 샘플 데이터:")
        recommendations_sample = conn.execute(text("""
            SELECT place_id, name, vector IS NOT NULL as has_vector
            FROM place_recommendations
            WHERE vector IS NOT NULL
            LIMIT 5
        """))

        for row in recommendations_sample:
            print(f"  - Place ID: {row.place_id}, Name: {row.name}, Has Vector: {row.has_vector}")

        # name 중복 확인
        print("\n📊 name 중복 확인:")

        # place_features에서 name 중복
        features_duplicates = conn.execute(text("""
            SELECT name, COUNT(*) as count
            FROM place_features
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 5
        """))

        print("  place_features 중복 name (상위 5개):")
        for row in features_duplicates:
            print(f"    - '{row.name}': {row.count}개")

        # place_recommendations에서 name 중복
        recommendations_duplicates = conn.execute(text("""
            SELECT name, COUNT(*) as count
            FROM place_recommendations
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 5
        """))

        print("  place_recommendations 중복 name (상위 5개):")
        for row in recommendations_duplicates:
            print(f"    - '{row.name}': {row.count}개")

def find_matching_records():
    """place_id와 name이 일치하는 레코드 찾기"""
    engine = create_engine(CONNECTION_STRING)

    print("\n=== 매칭 분석 ===")

    with engine.connect() as conn:
        # 1. place_id + name으로 정확 매칭 (가장 안전)
        print("\n📊 1. place_id + name 정확 매칭:")
        id_name_matches = conn.execute(text("""
            SELECT
                pf.id as features_id,
                pf.place_id as features_place_id,
                pf.name as features_name,
                pr.place_id as recommendations_place_id,
                pr.name as recommendations_name,
                pr.vector IS NOT NULL as has_vector
            FROM place_features pf
            INNER JOIN place_recommendations pr
                ON pf.place_id = pr.place_id AND pf.name = pr.name
            WHERE pr.vector IS NOT NULL
            LIMIT 10
        """))

        id_name_list = list(id_name_matches)
        print(f"   매칭된 레코드: {len(id_name_list)}개 (상위 10개 표시)")

        for i, row in enumerate(id_name_list, 1):
            print(f"   {i}. Features ID: {row.features_id} | Place ID: {row.features_place_id} | Name: '{row.features_name}'")

        # 전체 개수 확인
        total_id_name_matches = conn.execute(text("""
            SELECT COUNT(*) as total_count
            FROM place_features pf
            INNER JOIN place_recommendations pr
                ON pf.place_id = pr.place_id AND pf.name = pr.name
            WHERE pr.vector IS NOT NULL
            AND pf.vector IS NULL
        """)).fetchone()

        print(f"   🎯 총 place_id + name 매칭: {total_id_name_matches.total_count}개")

        # 2. place_id만으로 매칭 (name이 다를 수 있음)
        print("\n📊 2. place_id만 매칭 (name 무관):")
        id_only_matches = conn.execute(text("""
            SELECT
                pf.id as features_id,
                pf.place_id as features_place_id,
                pf.name as features_name,
                pr.place_id as recommendations_place_id,
                pr.name as recommendations_name,
                CASE WHEN pf.name = pr.name THEN 'SAME' ELSE 'DIFFERENT' END as name_status,
                pr.vector IS NOT NULL as has_vector
            FROM place_features pf
            INNER JOIN place_recommendations pr
                ON pf.place_id = pr.place_id
            WHERE pr.vector IS NOT NULL
            AND pf.vector IS NULL
            LIMIT 10
        """))

        id_only_list = list(id_only_matches)
        print(f"   매칭된 레코드: {len(id_only_list)}개 (상위 10개 표시)")

        for i, row in enumerate(id_only_list, 1):
            print(f"   {i}. Features ID: {row.features_id} | Place ID: {row.features_place_id}")
            print(f"      Features Name: '{row.features_name}'")
            print(f"      Recommendations Name: '{row.recommendations_name}' ({row.name_status})")

        # 전체 개수 확인
        total_id_only_matches = conn.execute(text("""
            SELECT COUNT(*) as total_count
            FROM place_features pf
            INNER JOIN place_recommendations pr
                ON pf.place_id = pr.place_id
            WHERE pr.vector IS NOT NULL
            AND pf.vector IS NULL
        """)).fetchone()

        print(f"   🎯 총 place_id만 매칭: {total_id_only_matches.total_count}개")

        # 3. name만으로 매칭 (place_id가 다를 수 있음)
        print("\n📊 3. name만 매칭 (place_id 무관):")
        name_only_matches = conn.execute(text("""
            SELECT COUNT(*) as total_count
            FROM place_features pf
            INNER JOIN place_recommendations pr
                ON pf.name = pr.name
            WHERE pr.vector IS NOT NULL
            AND pf.vector IS NULL
            AND pf.place_id != pr.place_id  -- place_id가 다른 경우만
        """)).fetchone()

        print(f"   🎯 name만 매칭 (place_id 다름): {name_only_matches.total_count}개")

        return {
            'id_name': total_id_name_matches.total_count,
            'id_only': total_id_only_matches.total_count,
            'name_only': name_only_matches.total_count
        }

def update_place_features_vectors():
    """place_features 테이블에 벡터값 업데이트"""
    engine = create_engine(CONNECTION_STRING)

    print("\n=== place_features 벡터 업데이트 시작 ===")

    try:
        with engine.connect() as conn:
            # 트랜잭션 시작
            trans = conn.begin()

            try:
                # 매칭되는 레코드들을 배치로 처리
                print("📊 매칭되는 레코드 조회 중...")

                matching_records = conn.execute(text("""
                    SELECT
                        pf.id as features_id,
                        pf.place_id as features_place_id,
                        pf.name as features_name,
                        pr.vector as recommendations_vector
                    FROM place_features pf
                    INNER JOIN place_recommendations pr
                        ON pf.place_id = pr.place_id AND pf.name = pr.name
                    WHERE pr.vector IS NOT NULL
                    AND pf.vector IS NULL  -- 아직 벡터가 없는 것만
                    ORDER BY pf.id
                """))

                records = list(matching_records)
                total_records = len(records)

                if total_records == 0:
                    print("❌ 업데이트할 레코드가 없습니다.")
                    return

                print(f"🎯 업데이트할 레코드: {total_records}개")

                # 배치 처리
                batch_size = 100
                updated_count = 0
                failed_count = 0

                for i in range(0, total_records, batch_size):
                    batch = records[i:i + batch_size]

                    for record in batch:
                        try:
                            # 개별 레코드 업데이트
                            update_query = text("""
                                UPDATE place_features
                                SET vector = CAST(:vector AS vector)
                                WHERE id = :features_id
                            """)

                            conn.execute(update_query, {
                                'vector': str(record.recommendations_vector),
                                'features_id': record.features_id
                            })

                            updated_count += 1

                            if updated_count % 50 == 0:
                                print(f"   진행률: {updated_count}/{total_records} ({updated_count/total_records*100:.1f}%)")

                        except Exception as record_error:
                            print(f"   ❌ 레코드 업데이트 실패 ID {record.features_id}: {record_error}")
                            failed_count += 1
                            continue

                # 커밋
                trans.commit()

                print(f"\n✅ place_features 벡터 업데이트 완료!")
                print(f"   📝 성공: {updated_count}개")
                print(f"   ❌ 실패: {failed_count}개")
                print(f"   📊 총 처리: {updated_count + failed_count}개")

                return updated_count

            except Exception as e:
                trans.rollback()
                print(f"❌ 트랜잭션 롤백: {e}")
                raise e

    except Exception as e:
        print(f"❌ place_features 업데이트 오류: {e}")
        raise

def verify_update_results():
    """업데이트 결과 검증"""
    engine = create_engine(CONNECTION_STRING)

    print("\n=== 업데이트 결과 검증 ===")

    with engine.connect() as conn:
        # 벡터가 있는 place_features 레코드 수 확인
        vector_count = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM place_features
            WHERE vector IS NOT NULL
        """)).fetchone()

        print(f"📊 벡터가 있는 place_features 레코드: {vector_count.count}개")

        # 샘플 확인
        sample_records = conn.execute(text("""
            SELECT id, name, vector IS NOT NULL as has_vector
            FROM place_features
            WHERE vector IS NOT NULL
            LIMIT 5
        """))

        print("\n📊 업데이트된 샘플 레코드:")
        for row in sample_records:
            print(f"  - ID: {row.id}, Name: {row.name}, Has Vector: {row.has_vector}")

        # 벡터 값 샘플 확인
        vector_sample = conn.execute(text("""
            SELECT name, vector::text as vector_text
            FROM place_features
            WHERE vector IS NOT NULL
            LIMIT 2
        """))

        print("\n📊 벡터 값 샘플:")
        for row in vector_sample:
            vector_text = row.vector_text
            print(f"  - Name: {row.name}")
            print(f"    Vector: {vector_text[:100]}...")

            # 0 벡터인지 확인
            try:
                import ast
                vector_list = ast.literal_eval(vector_text)
                is_zero_vector = all(x == 0 for x in vector_list)
                print(f"    Zero Vector: {is_zero_vector}")
                if not is_zero_vector:
                    print(f"    First 3 values: {vector_list[:3]}")
            except:
                print("    Vector parsing failed")

def main():
    """메인 실행 함수"""
    print("🚀 place_features 벡터 업데이트 시작")
    print("=" * 60)

    try:
        # 1. 테이블 구조 확인
        print("\n📊 1단계: 테이블 구조 확인")
        check_table_structures()

        # 2. 매칭되는 레코드 찾기
        print("\n🔍 2단계: 매칭 분석")
        match_stats = find_matching_records()

        if match_stats['id_name'] == 0:
            print("❌ 매칭되는 레코드가 없습니다.")
            return

        # 3. 사용자 확인
        response = input(f"\n🤔 {match_stats['id_name']}개 레코드를 업데이트하시겠습니까? (y/N): ")
        if response.lower() != 'y':
            print("❌ 업데이트가 취소되었습니다.")
            return

        # 4. 벡터 업데이트 실행
        print("\n🔄 3단계: place_features 벡터 업데이트")
        updated_count = update_place_features_vectors()

        # 5. 결과 검증
        print("\n✅ 4단계: 업데이트 결과 검증")
        verify_update_results()

        print("\n" + "=" * 60)
        print("🎉 place_features 벡터 업데이트 완료!")
        print(f"📊 업데이트된 레코드: {updated_count}개")

    except Exception as e:
        print(f"\n❌ 업데이트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()