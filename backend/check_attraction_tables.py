#!/usr/bin/env python3

from database import engine
from sqlalchemy import text

def check_table_schema(table_name):
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' AND table_schema = 'public'
            ORDER BY ordinal_position
        """))
        
        columns = result.fetchall()
        print(f"\n📋 {table_name} table schema:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
        
        # 샘플 데이터 확인
        result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 2"))
        rows = result.fetchall()
        if rows:
            print(f"\n  Sample data:")
            for row in rows:
                print(f"    {dict(row)}")

# 관광 관련 테이블들 확인
tables = ['nature', 'restaurants', 'shopping', 'accommodation', 'humanities', 'leisure_sports']
for table in tables:
    check_table_schema(table)