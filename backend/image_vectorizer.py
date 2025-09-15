"""
이미지 벡터화 전용 스크립트
S3 이미지를 open_clip으로 벡터화하여 place_recommendations_backup_20250915 테이블에 저장
"""

import asyncio
import logging
import requests
import json
import numpy as np
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse, quote
from sqlalchemy import create_engine, text

import torch
import open_clip

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DB 연결 문자열
CONNECTION_STRING = (
    "postgresql+psycopg://postgres:witple123!"
    "@witple-pub-database.cfme8csmytkv.ap-northeast-2.rds.amazonaws.com:5432/witple_db"
)

class ImageVectorizer:
    """이미지 벡터화 전용 클래스"""

    def __init__(self):
        logger.info("🖼️ open_clip ViT-B-32 모델 초기화 중...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # open_clip 모델 + 전처리
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k"
        )
        self.model = self.model.to(self.device).eval()
        logger.info("✅ 이미지 벡터화 시스템 초기화 완료 (512차원)")

        # DB 엔진
        self.engine = create_engine(CONNECTION_STRING)

    def _s3_to_https(self, url: str, default_region: str = "ap-northeast-2") -> str:
        """
        s3://bucket/key -> https://bucket.s3.<region>.amazonaws.com/key
        """
        if url.startswith("s3://"):
            p = urlparse(url)
            bucket = p.netloc
            key = p.path.lstrip("/")
            key_enc = "/".join(quote(part) for part in key.split("/"))
            return f"https://{bucket}.s3.{default_region}.amazonaws.com/{key_enc}"
        return url

    def encode_image_from_url(self, image_url: str) -> tuple[np.ndarray, bool]:
        """이미지를 open_clip으로 임베딩 (512D, L2 정규화)"""
        try:
            url = self._s3_to_https(image_url)

            resp = requests.get(
                url, stream=True, timeout=15,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            resp.raise_for_status()

            image = Image.open(BytesIO(resp.content)).convert("RGB")
            image.load()  # lazy load 방지

            with torch.no_grad():
                img_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
                feats = self.model.encode_image(img_tensor)       # (1, 512)
                feats = feats / feats.norm(dim=-1, keepdim=True)  # L2 정규화
                vec = feats.squeeze(0).cpu().numpy().astype(np.float32)

            if vec.shape != (512,) or not np.all(np.isfinite(vec)):
                raise ValueError("invalid vector")
            return vec, True

        except Exception as e:
            logger.error(f"❌ 이미지 인코딩 실패: {e} ({image_url[:120]}...)")
            return np.zeros(512, dtype=np.float32), False

    async def get_image_data(self) -> list:
        """DB에서 이미지 URL 데이터 조회"""
        logger.info("🔍 이미지 데이터 조회 중...")
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT id, place_id, name, image_urls
                    FROM place_recommendations_backup_20250915
                    WHERE image_urls IS NOT NULL
                      AND image_urls::text != 'null'
                      AND image_urls::text != '[]'
                      AND TRIM(image_urls::text) != ''
                    ORDER BY place_id
                """))
                rows = result.fetchall()
                logger.info(f"✅ {len(rows)}개 이미지 데이터 조회 완료")
                return [dict(row._mapping) for row in rows]
        except Exception as e:
            logger.error(f"❌ 데이터 조회 실패: {e}")
            return []

    async def vectorize_images(self, batch_size: int = 50):
        """이미지를 벡터화하고 DB에 저장"""
        logger.info("🖼️ 이미지 벡터화 시작...")
        places = await self.get_image_data()
        if not places:
            return

        success, fail = 0, 0

        for i, place in enumerate(places, 1):
            try:
                # image_urls 파싱
                image_urls = place["image_urls"]
                if isinstance(image_urls, str):
                    try:
                        image_urls = json.loads(image_urls)
                    except:
                        image_urls = [image_urls]

                if not image_urls:
                    logger.warning(f"⚠️ 이미지 없음 (id={place['id']})")
                    vec, ok = np.zeros(512, dtype=np.float32), False
                else:
                    vec, ok = self.encode_image_from_url(image_urls[0])

                vec_str = None if not ok else "[" + ",".join(f"{x:.6f}" for x in vec) + "]"

                # DB 업데이트
                with self.engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE place_recommendations_backup_20250915
                               SET image_vector = CAST(:vector AS vector(512))
                             WHERE id = :id
                        """),
                        {"vector": vec_str, "id": place["id"]}
                    )

                if ok:
                    success += 1
                else:
                    fail += 1

                if i % 50 == 0:
                    logger.info(f"📈 진행률 {i}/{len(places)} → 성공 {success}, 실패 {fail}")

            except Exception as e:
                fail += 1
                logger.error(f"❌ 처리 실패 (id={place['id']}): {e}")

        logger.info(f"✅ 이미지 벡터화 완료 → 성공 {success}, 실패 {fail}")

    async def verify_image_vectors(self):
        """벡터 상태 확인"""
        with self.engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM place_recommendations_backup_20250915")).scalar()
            has_vec = conn.execute(text("SELECT COUNT(*) FROM place_recommendations_backup_20250915 WHERE image_vector IS NOT NULL")).scalar()
            logger.info(f"📊 전체={total}, 벡터 보유={has_vec}, 완료율={has_vec/total*100:.1f}%")
            return has_vec


# 실행 함수
async def main():
    v = ImageVectorizer()
    await v.verify_image_vectors()
    await v.vectorize_images()
    await v.verify_image_vectors()

if __name__ == "__main__":
    asyncio.run(main())
