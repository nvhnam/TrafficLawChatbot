import google.generativeai as genai
import json
import time
import os
import uuid
import concurrent.futures
import logging
from datetime import datetime

from backend.config import *
from backend.core.gemini_fallback import call_with_fallback

logger = logging.getLogger(__name__)


class GetEntitiesByGemini:
    def __init__(self):
        genai.configure(api_key=API_KEY)
        self.generation_config = {"temperature": 0.1, "response_mime_type": "application/json"}
        self._models_cache = {}
        self.prompt_template = PROMPT_EXTRACT_ENTITIES

    def _get_model(self, model_name):
        if model_name not in self._models_cache:
            self._models_cache[model_name] = genai.GenerativeModel(
                model_name=model_name, generation_config=self.generation_config
            )
        return self._models_cache[model_name]

    def __build_prompt(self, chunk):
        meta = chunk.get("metadata", {})
        chunk_content = chunk.get("content", "")
        chunk_text = f"--- Văn bản: {meta.get('document', '')}, Điều {meta.get('dieu', '')} ---\n{chunk_content}"

        base_prompt = self.prompt_template.replace("actual_chunk_count_replace", "1")

        return f"{base_prompt}\n\n[DỮ LIỆU ĐẦU VÀO]: \n{chunk_text}"

    def validate_and_clean_graph_data(self, extracted_json, chunk_uuid):
        if not extracted_json or not isinstance(extracted_json, dict):
            return {"Level_3_Foundations": [], "Level_2_Rules_Actions": [], "Attributes_Measures": [], "Relationships": []}

        valid_ids = set()

        for category in ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]:
            for entity in extracted_json.get(category, []):
                old_id = entity.get("id", "")

                new_id = f"{chunk_uuid}_{old_id}"
                entity["id"] = new_id
                valid_ids.add(new_id)

                if entity.get("label") == "MONEY_AMOUNT":
                    for key in ["min", "max"]:
                        if key in entity:
                            try:
                                clean_num = ''.join(filter(str.isdigit, str(entity[key])))
                                entity[key] = int(clean_num) if clean_num else 0
                            except:
                                entity[key] = 0

        cleaned_relationships = []
        for rel in extracted_json.get("Relationships", []):
            rel["source"] = f"{chunk_uuid}_{rel.get('source', '')}"
            rel["target"] = f"{chunk_uuid}_{rel.get('target', '')}"

            if rel["source"] in valid_ids and rel["target"] in valid_ids:
                cleaned_relationships.append(rel)

        extracted_json["Relationships"] = cleaned_relationships
        return extracted_json

    def __call_api_single_chunk(self, chunk):
        full_prompt = self.__build_prompt(chunk)

        for attempt in range(3):
            def _do_call(model_name):
                return self._get_model(model_name).generate_content(full_prompt).text

            raw_text, used_model = call_with_fallback(
                _do_call,
                MODEL_INGESTION_FALLBACK,
                min_interval=INGESTION_MIN_INTERVAL_SECONDS,
                max_per_minute=INGESTION_MAX_CALLS_PER_MINUTE,
            )
            if raw_text is None:
                logger.critical("Đã hết hạn mức API (QUOTA_EXCEEDED) trên toàn bộ các model dự phòng.")
                return "QUOTA_EXCEEDED"

            try:
                raw_text = raw_text.strip()
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

                    cleaned_item = self.validate_and_clean_graph_data(extracted_item, chunk_uuid)

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

        return None

    def process_content(self, all_chunks, output_file_path, num_chunk_per_batch=3):
        progress_file = f"{output_file_path}.progress"
        temp_data_file = f"{output_file_path}.temp"

        file_identifier = os.path.basename(output_file_path)
        total_chunks = len(all_chunks)

        while True:
            start_idx = 0
            if os.path.exists(progress_file):
                with open(progress_file, "r") as f:
                    content = f.read().strip()
                    start_idx = int(content) if content.isdigit() else 0

            if start_idx >= total_chunks:
                break

            remaining_chunks = all_chunks[start_idx:]
            batches = [remaining_chunks[i: i + num_chunk_per_batch] for i in range(0, len(remaining_chunks), num_chunk_per_batch)]

            current_count = start_idx
            is_crashed = False

            with open(temp_data_file, "a", encoding="utf-8") as f_temp:
                for batch in batches:
                    results = []

                    with concurrent.futures.ThreadPoolExecutor(max_workers=num_chunk_per_batch) as executor:
                        future_to_chunk = {executor.submit(self.__call_api_single_chunk, chunk): chunk for chunk in batch}

                        for future in concurrent.futures.as_completed(future_to_chunk):
                            extracted_item = future.result()
                            results.append(extracted_item)

                    for item in results:
                        if item == "QUOTA_EXCEEDED":
                            logger.critical(
                                "Entity extraction for '%s' stopped at chunk %d/%d: all fallback models exhausted.",
                                file_identifier, current_count + 1, total_chunks,
                            )
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

                    logger.info(
                        "Entity extraction chunk %d/%d done for '%s'.",
                        current_count, total_chunks, file_identifier,
                    )

                    time.sleep(2)

            if is_crashed:
                logger.error("CRASHED tại: %s | Chunk: %d/%d. Hệ thống ngủ 60s rồi chạy lại...", file_identifier, current_count, total_chunks)
                time.sleep(60)
                continue

        final_results = []
        if os.path.exists(temp_data_file):
            with open(temp_data_file, "r", encoding="utf-8") as f_temp:
                for line in f_temp:
                    if line.strip():
                        final_results.append(json.loads(line.strip()))

        if os.path.exists(progress_file): os.remove(progress_file)
        if os.path.exists(temp_data_file): os.remove(temp_data_file)

        return final_results