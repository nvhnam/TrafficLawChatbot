"""
Bước 2: Trích xuất thực thể (Entity Extraction) bằng Gemini API.

Gửi từng chunk tới Gemini Pro để trích xuất thực thể 3 tầng:
- Level_3_Foundations: Chủ thể, khái niệm, điều kiện, ...
- Level_2_Rules_Actions: Hành vi vi phạm, thủ tục, quyền/nghĩa vụ, ...
- Attributes_Measures: Mức phạt tiền, hình thức phạt bổ sung, thời hạn, ...

Hỗ trợ:
- Tự động retry khi gặp lỗi API (tối đa 3 lần mỗi chunk)
- Lưu tiến trình (progress file) để có thể chạy tiếp nếu bị gián đoạn
- Chạy song song nhiều chunk cùng lúc (mặc định 3 chunk/batch)
"""

import google.generativeai as genai
import json
import time
import os
import uuid
import concurrent.futures
import logging

from config import API_KEY, MODEL_FLASH, PROMPT_EXTRACT_ENTITIES

logger = logging.getLogger(__name__)


class EntityExtractor:
    """
    Trích xuất thực thể từ các chunk pháp luật bằng Gemini Pro API.
    """

    def __init__(self):
        """Khởi tạo kết nối tới Gemini API."""
        genai.configure(api_key=API_KEY)
        self.model = genai.GenerativeModel(
            model_name=MODEL_FLASH,
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
        )
        self.prompt_template = PROMPT_EXTRACT_ENTITIES

    def _build_prompt(self, chunk):
        """
        Xây dựng prompt đầy đủ cho Gemini từ một chunk.

        Tham số:
            chunk: dict chứa 'content' và 'metadata'

        Trả về:
            Chuỗi prompt hoàn chỉnh
        """
        meta = chunk.get("metadata", {})
        chunk_content = chunk.get("content", "")
        chunk_text = f"--- Văn bản: {meta.get('document', '')}, Điều {meta.get('dieu', '')} ---\n{chunk_content}"

        base_prompt = self.prompt_template.replace("actual_chunk_count_replace", "1")
        return f"{base_prompt}\n\n[DỮ LIỆU ĐẦU VÀO]: \n{chunk_text}"

    def _validate_and_clean(self, extracted_json, chunk_uuid):
        """
        Xác thực và chuẩn hoá kết quả trích xuất từ Gemini.

        Thực hiện:
        - Gắn chunk_uuid vào tất cả entity ID (đảm bảo duy nhất toàn cục)
        - Chuẩn hoá MONEY_AMOUNT (min/max) về số nguyên
        - Loại bỏ relationship trỏ tới entity không tồn tại

        Tham số:
            extracted_json: dict JSON trả về từ Gemini
            chunk_uuid: UUID duy nhất của chunk hiện tại

        Trả về:
            dict đã được chuẩn hoá
        """
        if not extracted_json or not isinstance(extracted_json, dict):
            return {
                "Level_3_Foundations": [],
                "Level_2_Rules_Actions": [],
                "Attributes_Measures": [],
                "Relationships": []
            }

        valid_ids = set()

        for category in ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]:
            for entity in extracted_json.get(category, []):
                old_id = entity.get("id", "")
                new_id = f"{chunk_uuid}_{old_id}"
                entity["id"] = new_id
                valid_ids.add(new_id)

                # Chuẩn hoá MONEY_AMOUNT: đảm bảo min/max là số nguyên
                if entity.get("label") == "MONEY_AMOUNT":
                    for key in ["min", "max"]:
                        if key in entity:
                            try:
                                clean_num = ''.join(filter(str.isdigit, str(entity[key])))
                                entity[key] = int(clean_num) if clean_num else 0
                            except (ValueError, TypeError):
                                entity[key] = 0

        # Lọc relationship: chỉ giữ những quan hệ mà cả source và target đều tồn tại
        cleaned_relationships = []
        for rel in extracted_json.get("Relationships", []):
            rel["source"] = f"{chunk_uuid}_{rel.get('source', '')}"
            rel["target"] = f"{chunk_uuid}_{rel.get('target', '')}"

            if rel["source"] in valid_ids and rel["target"] in valid_ids:
                cleaned_relationships.append(rel)

        extracted_json["Relationships"] = cleaned_relationships
        return extracted_json

    def _call_api_single_chunk(self, chunk):
        """
        Gọi Gemini API cho một chunk duy nhất, có retry.

        Tham số:
            chunk: dict chứa 'content' và 'metadata'

        Trả về:
            - dict chứa entities đã chuẩn hoá (thành công)
            - "QUOTA_EXCEEDED" (hết hạn mức API)
            - None (thất bại sau 3 lần thử)
        """
        full_prompt = self._build_prompt(chunk)

        for attempt in range(3):
            try:
                response = self.model.generate_content(full_prompt)

                raw_text = response.text.strip()
                # Loại bỏ markdown code fence nếu có
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()

                extracted_item = json.loads(raw_text)

                if isinstance(extracted_item, dict):
                    chunk_uuid = chunk.get("metadata", {}).get("chunk_uuid", uuid.uuid4().hex)
                    cleaned_item = self._validate_and_clean(extracted_item, chunk_uuid)
                    cleaned_item["metadata"] = chunk.get("metadata", {})
                    cleaned_item["metadata"]["chunk_uuid"] = chunk_uuid
                    cleaned_item["original_content"] = chunk.get("content", "")
                    return cleaned_item
                else:
                    time.sleep(5)
                    continue

            except json.decoder.JSONDecodeError as e:
                logger.warning("Lỗi parse JSON (Thử lại %d/3): %s", attempt + 1, e)
                time.sleep(5)
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg:
                    logger.critical("Đã hết hạn mức API (QUOTA_EXCEEDED).")
                    return "QUOTA_EXCEEDED"

                logger.error("Lỗi API (Thử lại %d/3): %s", attempt + 1, e)
                time.sleep(10 if "504" in error_msg else 5)

        return None

    def process_chunks(self, all_chunks, output_file_path, num_chunk_per_batch=3):
        """
        Xử lý toàn bộ danh sách chunk, gọi Gemini song song theo batch.

        Hỗ trợ resume: nếu bị gián đoạn, chạy lại sẽ tiếp tục từ chunk cuối.

        Tham số:
            all_chunks: Danh sách chunk (từ bước 1)
            output_file_path: Đường dẫn file JSONL đầu ra
            num_chunk_per_batch: Số chunk xử lý song song mỗi batch (mặc định 3)

        Trả về:
            - Danh sách kết quả (thành công)
            - "QUOTA_EXCEEDED" (hết hạn mức)
        """
        progress_file = f"{output_file_path}.progress"
        temp_data_file = f"{output_file_path}.temp"

        file_identifier = os.path.basename(output_file_path)
        total_chunks = len(all_chunks)

        print(f"[Bước 2] Bắt đầu trích xuất thực thể cho {total_chunks} chunks...")
        print(f"         Mỗi batch gồm {num_chunk_per_batch} chunks song song")
        print(f"         Ước tính số lần gọi Gemini: {total_chunks} lần")

        while True:
            start_idx = 0
            if os.path.exists(progress_file):
                with open(progress_file, "r") as f:
                    content = f.read().strip()
                    start_idx = int(content) if content.isdigit() else 0

            if start_idx >= total_chunks:
                break

            if start_idx > 0:
                print(f"         Tiếp tục từ chunk {start_idx}/{total_chunks}")

            remaining_chunks = all_chunks[start_idx:]
            batches = [
                remaining_chunks[i: i + num_chunk_per_batch]
                for i in range(0, len(remaining_chunks), num_chunk_per_batch)
            ]

            current_count = start_idx
            is_crashed = False

            with open(temp_data_file, "a", encoding="utf-8") as f_temp:
                for batch_idx, batch in enumerate(batches):
                    results = []

                    with concurrent.futures.ThreadPoolExecutor(max_workers=num_chunk_per_batch) as executor:
                        future_to_chunk = {
                            executor.submit(self._call_api_single_chunk, chunk): chunk
                            for chunk in batch
                        }
                        for future in concurrent.futures.as_completed(future_to_chunk):
                            extracted_item = future.result()
                            results.append(extracted_item)

                    for item in results:
                        if item == "QUOTA_EXCEEDED":
                            print(f"\n[Bước 2] HẾT HẠN MỨC API tại chunk {current_count}/{total_chunks}")
                            return "QUOTA_EXCEEDED"
                        if item is None:
                            is_crashed = True
                            break

                    if is_crashed:
                        break

                    for item in results:
                        f_temp.write(json.dumps(item, ensure_ascii=False) + "\n")
                    f_temp.flush()

                    current_count += len(batch)
                    with open(progress_file, "w") as f_prog:
                        f_prog.write(str(current_count))

                    # Hiển thị tiến trình
                    print(f"         [{current_count}/{total_chunks}] "
                          f"({current_count * 100 // total_chunks}%)", end="\r")

                    time.sleep(2)

            if is_crashed:
                logger.error(
                    "Lỗi tại chunk %d/%d. Hệ thống ngủ 60 giây rồi chạy lại...",
                    current_count, total_chunks
                )
                time.sleep(60)
                continue

        # Đọc kết quả từ file tạm
        final_results = []
        if os.path.exists(temp_data_file):
            with open(temp_data_file, "r", encoding="utf-8") as f_temp:
                for line in f_temp:
                    if line.strip():
                        final_results.append(json.loads(line.strip()))

        # Dọn dẹp file tạm
        if os.path.exists(progress_file):
            os.remove(progress_file)
        if os.path.exists(temp_data_file):
            os.remove(temp_data_file)

        print(f"\n[Bước 2] Hoàn tất trích xuất {len(final_results)} chunks -> {output_file_path}")
        return final_results


def run_extraction(chunks_file, output_file):
    """
    Thực thi bước trích xuất thực thể cho một file chunks.

    Tham số:
        chunks_file: Đường dẫn tới file JSON chứa chunks (đầu ra bước 1)
        output_file: Đường dẫn tới file JSONL đầu ra
    """
    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    extractor = EntityExtractor()
    results = extractor.process_chunks(chunks, output_file)

    if results == "QUOTA_EXCEEDED":
        print("[Bước 2] Hết hạn mức API. Chạy lại sau hoặc đổi API key.")
        return None

    # Ghi kết quả cuối cùng ra file JSONL
    with open(output_file, "w", encoding="utf-8") as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return results


if __name__ == "__main__":
    import sys
    from config import CHUNKS_DIR, ENTITIES_RAW_DIR

    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        json_files = [f for f in os.listdir(CHUNKS_DIR) if f.endswith(".json")]
        if not json_files:
            print(f"Không tìm thấy file .json nào trong {CHUNKS_DIR}")
            sys.exit(1)
        filename = json_files[0]

    input_path = os.path.join(CHUNKS_DIR, filename)
    output_name = os.path.splitext(filename)[0] + ".jsonl"
    output_path = os.path.join(ENTITIES_RAW_DIR, output_name)

    run_extraction(input_path, output_path)
