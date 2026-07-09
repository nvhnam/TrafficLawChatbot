#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
load_neo4j.py — Nạp 3 nghị định (đã trích xuất) vào Neo4j + tạo embedding cho System B.

Dùng LẠI đúng code ingest của backend (Neo4jUploader, NodeEmbeddingBuilder) để đồ thị
KHỚP với cypher truy vấn trong backend/chatbot/bot.py -> System B chạy đúng như thật.

KHÔNG tốn API Gemini:
  - Nạp node/quan hệ: thuần Cypher.
  - Embedding: chạy LOCAL bằng model AITeamVN/Vietnamese_Embedding (SentenceTransformer, CPU).
  - (Bỏ qua build_edges.py — bước duy nhất dùng Gemini, chỉ nối quan hệ sửa đổi/bãi bỏ
     giữa các văn bản; không cần cho việc chấm điểm.)

Tính incremental (chạy tới đâu lưu tới đó):
  - upload: commit theo TỪNG chunk.
  - embed : lưu theo từng batch; node đã có embedding thì bỏ qua -> chạy lại là tiếp tục.

YÊU CẦU:
  - Neo4j đang chạy (docker compose up -d) tại bolt://localhost:7687
  - Chạy trong môi trường có: neo4j, sentence-transformers, torch (venv backend)
  - Biến môi trường USER_NEO4J / PASSWORD_NEO4J (mặc định neo4j/trafficlaw123 khớp docker-compose)

CÁCH CHẠY (từ gốc repo TrafficLawChatbot):
    python data/evaluation/harness/load_neo4j.py            # nạp graph + embedding
    python data/evaluation/harness/load_neo4j.py --skip-embed   # chỉ nạp graph (nhanh)
    python data/evaluation/harness/load_neo4j.py --embed-only    # chỉ chạy embedding
"""
import argparse
import logging
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

# Thông tin đăng nhập Neo4j: ưu tiên .env; nếu thiếu -> mặc định khớp docker-compose.yml
os.environ.setdefault("USER_NEO4J", "neo4j")
os.environ.setdefault("PASSWORD_NEO4J", "trafficlaw123")
os.environ.setdefault("API_KEY", "")  # không cần cho nạp/embedding, chỉ để config.py không lỗi

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("load_neo4j")

# 3 nguồn gold: 100 & 168 bản Gemini (tác giả gốc), 123 bản regex của nhóm
SOURCES = [
    REPO / "data/pipeline/sample/data_prepare_up_neo4j/100.signed.jsonl",
    REPO / "data/pipeline/output/neo4j_ready/123-2021nd-cp.jsonl",
    REPO / "data/pipeline/sample/data_prepare_up_neo4j/168-nd-cp.signed.jsonl",
]


def upload_graph():
    from backend.ingestion.upload2neo4j import Neo4jUploader
    uploader = Neo4jUploader()
    try:
        for path in SOURCES:
            if not path.exists():
                log.warning("BỎ QUA (không thấy): %s", path)
                continue
            log.info("⏳ Nạp: %s", path.name)
            uploader.upload_data(str(path))   # commit theo từng chunk bên trong
        # thống kê nhanh
        with uploader.driver.session() as s:
            for lbl in ("Document", "Chunk", "VIOLATION", "MONEY_AMOUNT"):
                n = s.run(f"MATCH (n:{lbl}) RETURN count(n) AS c").single()["c"]
                log.info("   %-14s: %d node", lbl, n)
    finally:
        uploader.close()


def build_embeddings(batch=8, max_seq=512):
    """Chỉ embed CHUNK (thứ bot thật sự dùng qua chunk_vector_index) — bỏ embed entity
    cho nhanh. Dùng VectorEmbeddingBuilder (chunk-only, resume theo 'embedding IS NULL').

    CHẶN RAM: model là BGE-M3 (hỗ trợ tới 8192 token) -> batch lớn + chunk dài sẽ tràn RAM.
    Giữ batch nhỏ và cắt max_seq_length (512 token đủ cho 1 điều/khoản/điểm)."""
    import torch
    torch.set_num_threads(max(1, (os.cpu_count() or 4) // 2))
    from backend.data_processing.build_vector_embeddings import VectorEmbeddingBuilder
    builder = VectorEmbeddingBuilder()
    builder.batch_size = batch
    try:
        builder.model.max_seq_length = max_seq   # cắt độ dài -> chặn cứng bộ nhớ
        remaining = builder.query(
            "MATCH (c:Chunk) WHERE c.embedding IS NULL RETURN count(c) AS t")[0]["t"]
        log.info("⏳ Embedding chunk còn lại: %d (batch=%d, max_seq=%d, local)...",
                 remaining, batch, max_seq)
        builder.run_embedding_process()   # lưu theo từng mẻ -> resume được
        log.info("✅ Xong embedding chunk.")
        setup_sage_fallback(builder.driver)
    finally:
        builder.close()


def setup_sage_fallback(driver):
    """Cypher của bot dùng sage_chunk_index trên c.sage_embedding (GraphSAGE). Môi trường
    này KHÔNG có Neo4j GDS nên KHÔNG train được GraphSAGE. Giải pháp giữ NGUYÊN cypher:
    dùng chính text-embedding làm sage_embedding -> bước "mở rộng hàng xóm" chạy theo tương
    đồng ngữ nghĩa thay cho GraphSAGE. (Khai báo rõ điều này trong báo cáo.)"""
    with driver.session() as s:
        log.info("⏳ Sao chép embedding -> sage_embedding (fallback không cần GDS)...")
        s.run("""
            CALL apoc.periodic.iterate(
              'MATCH (c:Chunk) WHERE c.embedding IS NOT NULL AND c.sage_embedding IS NULL RETURN c',
              'SET c.sage_embedding = c.embedding',
              {batchSize: 500})
        """)
        s.run("""
            CREATE VECTOR INDEX sage_chunk_index IF NOT EXISTS
            FOR (c:Chunk) ON (c.sage_embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1024,
                `vector.similarity_function`: 'cosine'
            }}
        """)
        log.info("✅ Đã tạo sage_chunk_index (fallback). System B chạy đúng cypher gốc.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-embed", action="store_true", help="chỉ nạp graph, bỏ embedding")
    ap.add_argument("--embed-only", action="store_true", help="chỉ chạy embedding")
    ap.add_argument("--batch", type=int, default=8, help="batch size embedding (giảm nếu tràn RAM)")
    ap.add_argument("--max-seq", type=int, default=512, help="cắt độ dài token/chunk (chặn RAM)")
    args = ap.parse_args()

    if not args.embed_only:
        upload_graph()
    if not args.skip_embed:
        build_embeddings(batch=args.batch, max_seq=args.max_seq)
    log.info("🎉 HOÀN TẤT. System B đã sẵn sàng để chạy đánh giá.")


if __name__ == "__main__":
    main()
