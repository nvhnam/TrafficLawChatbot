"""
Script chạy toàn bộ pipeline xử lý dữ liệu pháp luật.

Quy trình:
    Bước 1: Tách văn bản Markdown thành chunks (theo Điều/Khoản/Điểm)
    Bước 2: Trích xuất thực thể bằng regex (3 tầng, chạy local)
    Bước 3: Làm sạch và bổ sung ngữ cảnh
    Bước 3b: Bổ sung thực thể thiếu bằng suy luận ngữ cảnh

Cách dùng:
    python run_pipeline.py                        # Xử lý tất cả file .md trong input/
    python run_pipeline.py 123-2021nd-cp.md       # Xử lý một file cụ thể
    python run_pipeline.py 123-2021nd-cp.md --step 2  # Chỉ chạy từ bước 2 trở đi
"""

import os
import sys
import argparse
import logging

from config import INPUT_DIR, CHUNKS_DIR, ENTITIES_RAW_DIR, ENTITIES_CLEANED_DIR
from step1_chunking import run_chunking
from step2_extract_local import run_local_extraction
from step3_clean_data import run_cleaning
from step3b_enrich import run_enrichment

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)


def run_pipeline(filename, start_step=1):
    """
    Chạy pipeline cho một file markdown.

    Tham số:
        filename: Tên file markdown (VD: "123-2021nd-cp.md")
        start_step: Bước bắt đầu (1, 2, hoặc 3). Dùng khi muốn chạy lại từ giữa.
    """
    base_name = os.path.splitext(filename)[0]
    input_path = os.path.join(INPUT_DIR, filename)
    chunks_path = os.path.join(CHUNKS_DIR, f"{base_name}.json")
    entities_raw_path = os.path.join(ENTITIES_RAW_DIR, f"{base_name}.jsonl")
    entities_cleaned_path = os.path.join(ENTITIES_CLEANED_DIR, f"{base_name}.jsonl")

    print("=" * 60)
    print(f"PIPELINE XỬ LÝ DỮ LIỆU PHÁP LUẬT")
    print(f"File đầu vào: {filename}")
    print(f"Bắt đầu từ bước: {start_step}")
    print("=" * 60)

    # --- Bước 1: Chunking ---
    if start_step <= 1:
        if not os.path.exists(input_path):
            print(f"\nLỗi: Không tìm thấy file {input_path}")
            print(f"Hãy copy file .md vào thư mục input/ trước khi chạy.")
            return False

        chunks = run_chunking(input_path, chunks_path)
        if not chunks:
            print("Lỗi: Không tách được chunk nào. Kiểm tra lại file đầu vào.")
            return False
    else:
        if not os.path.exists(chunks_path):
            print(f"Lỗi: Không tìm thấy {chunks_path}. Hãy chạy lại từ bước 1.")
            return False
        print(f"[Bước 1] Bỏ qua (đã có {chunks_path})")

    # --- Bước 2: Trích xuất thực thể ---
    if start_step <= 2:
        run_local_extraction(chunks_path, entities_raw_path)
    else:
        if not os.path.exists(entities_raw_path):
            print(f"Lỗi: Không tìm thấy {entities_raw_path}. Hãy chạy lại từ bước 2.")
            return False
        print(f"[Bước 2] Bỏ qua (đã có {entities_raw_path})")

    # --- Bước 3: Làm sạch ---
    if start_step <= 3:
        run_cleaning(entities_raw_path, entities_cleaned_path)

    # --- Bước 3b: Bổ sung thực thể thiếu ---
    if start_step <= 3:
        run_enrichment(entities_cleaned_path, chunks_path)

    print("\n" + "=" * 60)
    print("PIPELINE HOÀN TẤT")
    print(f"Kết quả cuối cùng: {entities_cleaned_path}")
    print("=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline xử lý dữ liệu pháp luật giao thông",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "filename",
        nargs="?",
        help="Tên file markdown đầu vào (trong thư mục input/). "
             "Nếu bỏ trống, xử lý tất cả file .md trong input/"
    )
    parser.add_argument(
        "--step", "-s",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="Bước bắt đầu (mặc định: 1)\n"
             "  1 = Chunking -> Entity Extraction -> Cleaning\n"
             "  2 = Entity Extraction -> Cleaning (bỏ qua chunking)\n"
             "  3 = Cleaning (chỉ làm sạch)"
    )

    args = parser.parse_args()

    if args.filename:
        filenames = [args.filename]
    else:
        filenames = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith(".md")])
        if not filenames:
            print(f"Không tìm thấy file .md nào trong {INPUT_DIR}")
            print(f"Hãy copy file Markdown vào thư mục input/ trước khi chạy.")
            sys.exit(1)
        print(f"Tìm thấy {len(filenames)} file: {', '.join(filenames)}\n")

    for filename in filenames:
        success = run_pipeline(filename, start_step=args.step)
        if not success:
            print(f"\nDừng pipeline tại file: {filename}")
            sys.exit(1)


if __name__ == "__main__":
    main()
