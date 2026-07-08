"""
Bước 4: Chuẩn bị dữ liệu để đẩy lên Neo4j.

Chuyển từ entities_cleaned -> data_prepare_up_neo4j.
Thay đổi duy nhất: thêm trường chunk_id (số thứ tự tăng dần).

Không cần Gemini API.

Cách dùng:
    python step4_prepare_neo4j.py                    # Xử lý tất cả file
    python step4_prepare_neo4j.py 100.signed.jsonl   # Xử lý 1 file
"""

import json
import os
import sys


def prepare_for_neo4j(input_file, output_file):
    """
    Đọc file JSONL đã clean, thêm chunk_id, ghi ra file mới.
    """
    print(f"[Bước 4] Chuẩn bị dữ liệu Neo4j...")
    print(f"         Đầu vào: {os.path.basename(input_file)}")

    data = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))

    # Đánh chunk_id tăng dần từ 1
    for i, chunk in enumerate(data):
        chunk["chunk_id"] = i + 1

    # Ghi ra
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for chunk in data:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # Thống kê
    total_entities = 0
    total_rels = 0
    for chunk in data:
        for cat in ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]:
            total_entities += len(chunk.get(cat, []))
        total_rels += len(chunk.get("Relationships", []))

    print(f"         Tổng chunks: {len(data)}")
    print(f"         Tổng thực thể: {total_entities}")
    print(f"         Tổng quan hệ: {total_rels}")
    print(f"[Bước 4] Hoàn tất -> {output_file}")

    return data


if __name__ == "__main__":
    from config import ENTITIES_CLEANED_DIR

    # Thư mục đầu ra
    output_dir = os.path.join(os.path.dirname(ENTITIES_CLEANED_DIR), "neo4j_ready")

    if len(sys.argv) > 1:
        filenames = [sys.argv[1]]
    else:
        filenames = sorted([
            f for f in os.listdir(ENTITIES_CLEANED_DIR)
            if f.endswith(".jsonl")
        ])

    if not filenames:
        print(f"Không tìm thấy file .jsonl nào trong {ENTITIES_CLEANED_DIR}")
        sys.exit(1)

    print(f"Chuẩn bị {len(filenames)} file cho Neo4j...\n")

    for filename in filenames:
        input_path = os.path.join(ENTITIES_CLEANED_DIR, filename)
        output_path = os.path.join(output_dir, filename)
        prepare_for_neo4j(input_path, output_path)
        print()
