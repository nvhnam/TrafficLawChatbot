"""
Bước 3: Làm sạch và bổ sung ngữ cảnh cho dữ liệu thực thể.

Đây là bước quan trọng nhất trong pipeline, thực hiện 5 công đoạn:
1. Chuẩn hoá tên văn bản (resolve "Nghị định này" -> "Nghị định số 100/2019/NĐ-CP")
2. Bổ sung ngữ cảnh sửa đổi (NĐ 123 sửa đổi NĐ 100 -> gắn context)
3. Tinh chỉnh schema đồ thị (gắn thẻ loại phương tiện vào entity)
4. Trích xuất cây phân cấp văn bản (Document -> Article -> Clause -> Point)
5. Nối các đảo cô lập (resolve tham chiếu chéo "điểm a khoản 2 Điều 5")
"""

import json
import re
import os
import logging
from unidecode import unidecode

logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Bộ làm sạch dữ liệu thực thể pháp luật.

    Nhận đầu vào là file JSONL (từ bước 2) và xuất ra file JSONL đã được
    chuẩn hoá, bổ sung ngữ cảnh, sẵn sàng để đưa vào Neo4j.
    """

    def __init__(self):
        # Regex nhận diện tên văn bản pháp luật chính thức
        self.LEGAL_DOC_PATTERN = r"(Nghị định số \d+/\d+/[A-ZĐa-z0-9-]+|Thông tư số \d+/\d+/[A-ZĐa-z0-9-]+|(?:Bộ )?Luật [A-ZĐ][\w\s,]+?)(?=\s*(?:ngày|tháng|năm|đã|sửa|bổ|$))"

        # Danh sách các giấy tờ vật lý (để phân biệt với DOCUMENT_RECORD pháp luật)
        self.PHYSICAL_DOCS = [
            "giấy phép lái xe", "chứng nhận đăng ký", "tem kiểm định",
            "phù hiệu", "bảo hiểm", "giấy chứng nhận", "biển số",
            "giấy phép lưu hành", "lệnh vận chuyển", "giấy vận tải",
            "chứng chỉ", "giấy phép kinh doanh", "giấy phép thi công",
            "giấy phép hoạt động"
        ]

        # Tên 3 tầng entity trong JSONL
        self.entity_categories = [
            "Level_3_Foundations",
            "Level_2_Rules_Actions",
            "Attributes_Measures"
        ]

    # =========================================================================
    # CÁC HÀM TIỆN ÍCH
    # =========================================================================

    def _clean_markdown(self, text):
        """Dọn dẹp các ký tự markdown dư thừa trong văn bản."""
        # Bỏ ``` markdown
        text = re.sub(r'```\w*\s*', '', text)
        text = re.sub(r'```', '', text)
        # Bỏ ### ## # (markdown heading)
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
        # Bỏ **bold** -> bold
        text = re.sub(r'\*{2,3}([^*]+)\*{2,3}', r'\1', text)
        # Bỏ *italic* -> italic
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', text)
        # Bỏ ___ (horizontal rule)
        text = re.sub(r'^[_*-]{3,}\s*$', '', text, flags=re.MULTILINE)
        # Bỏ dòng trống liên tiếp
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _read_jsonl(self, input_file):
        """Đọc file JSONL, mỗi dòng là một JSON object."""
        data_list = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    data_list.append(json.loads(line))
        return data_list

    def _write_jsonl(self, data_list, output_file):
        """Ghi danh sách JSON object ra file JSONL."""
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in data_list:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def _get_dynamic_doc_name(self, data_list):
        """
        Tự động xác định tên đầy đủ của văn bản từ phần preamble.

        Ví dụ: Từ nội dung file 100.signed.jsonl, xác định được
        "Nghị định số 100/2019/NĐ-CP".
        """
        if not data_list:
            return "Văn bản pháp luật"

        # Tìm chunk preamble
        preamble_chunk = next(
            (chunk for chunk in data_list
             if chunk.get("metadata", {}).get("type") == "PREAMBLE"),
            None
        )
        if not preamble_chunk:
            preamble_chunk = data_list[0]

        content = preamble_chunk.get("original_content", preamble_chunk.get("content", ""))
        content = re.sub(r'^\[Văn bản:.*?\]\s*', '', content)

        # Tách phần trước "Căn cứ" (thường là tiêu đề)
        header_part = content.split("Căn cứ")[0] if "Căn cứ" in content else content
        clean_header = header_part.replace('*', '').replace('#', '')

        # Tìm số hiệu văn bản
        so_match = re.search(
            r"(?:Số|số|Luật số|Bộ luật số)\s*[:]?\s*([0-9]+(?:\s*/\s*[^\s,;]+)+)",
            clean_header, re.IGNORECASE
        )
        so_hieu = ""
        if so_match:
            so_hieu = re.sub(r'\s*/\s*', '/', so_match.group(1).strip())

        # Xác định loại văn bản
        blocks = content.split('\n\n')
        for block in blocks:
            clean_block = block.replace('*', '').replace('#', '').replace('\n', ' ').strip()
            clean_block = re.sub(r'\s+', ' ', clean_block)
            block_unaccented = unidecode(clean_block.lower())

            if block_unaccented.startswith("nghi dinh"):
                return f"Nghị định số {so_hieu}" if so_hieu else "Nghị định"
            if block_unaccented.startswith("thong tu"):
                return f"Thông tư số {so_hieu}" if so_hieu else "Thông tư"
            if block_unaccented.startswith("luat ") or block_unaccented.startswith("bo luat "):
                prefix = "Bộ luật" if "bo luat" in block_unaccented else "Luật"
                return f"{prefix} số {so_hieu}" if so_hieu else prefix

        return f"Văn bản số {so_hieu}" if so_hieu else "Văn bản pháp luật"

    # =========================================================================
    # CÔNG ĐOẠN 1: CHUẨN HOÁ TÊN VĂN BẢN
    # =========================================================================

    def clean_document_name(self, data_list):
        """
        Thay thế các tham chiếu mơ hồ bằng tên văn bản chính xác.

        Ví dụ:
        - "Nghị định này" -> "Nghị định số 100/2019/NĐ-CP"
        - "Điều này" -> "Điều 5 Nghị định số 100/2019/NĐ-CP"
        """
        doc_name = self._get_dynamic_doc_name(data_list)

        for chunk in data_list:
            meta = chunk.get("metadata", {})
            dieu = meta.get("dieu", "")

            for category in self.entity_categories:
                for entity in chunk.get(category, []):
                    value = entity.get("value", "")
                    name = entity.get("name", "")

                    # Thay thế "Nghị định này" / "Thông tư này" / "Luật này"
                    for field in ["value", "name"]:
                        text = entity.get(field, "")
                        text = re.sub(
                            r"(?i)(Nghị định|Thông tư|Luật|Bộ luật)\s+này",
                            doc_name,
                            text
                        )
                        entity[field] = text

                    # Bổ sung context vào original_content
                    if "original_content" in chunk:
                        chunk["original_content"] = re.sub(
                            r"(?i)(Nghị định|Thông tư|Luật|Bộ luật)\s+này",
                            doc_name,
                            chunk["original_content"]
                        )

        return data_list

    # =========================================================================
    # CÔNG ĐOẠN 2: BỔ SUNG NGỮ CẢNH SỬA ĐỔI
    # =========================================================================

    def resolve_amendment_context(self, data_list):
        """
        Xử lý đặc thù cho các nghị định sửa đổi (VD: NĐ 123/2021 sửa NĐ 100/2019).

        Khi gặp entity chứa "sửa đổi khoản X Điều Y", bổ sung thêm context
        về nghị định bị sửa đổi vào entity value.
        """
        for chunk in data_list:
            content = chunk.get("original_content", "")

            # Tìm pattern "Sửa đổi, bổ sung ... của Nghị định số ..."
            amendment_match = re.search(
                r"(?:Sửa đổi|Bổ sung|Thay thế|Bãi bỏ)[^.]*?(Nghị định số \d+/\d+/[A-ZĐa-z0-9-]+)",
                content, re.IGNORECASE
            )

            if amendment_match:
                target_doc = amendment_match.group(1)
                for category in self.entity_categories:
                    for entity in chunk.get(category, []):
                        value = entity.get("value", "")
                        # Nếu entity đề cập "Điều X" mà chưa ghi rõ văn bản nào
                        if re.search(r"Điều \d+", value) and target_doc not in value:
                            entity["value"] = f"{value} (thuộc {target_doc})"

        return data_list

    # =========================================================================
    # CÔNG ĐOẠN 3: TINH CHỈNH SCHEMA ĐỒ THỊ
    # =========================================================================

    def refine_graph_schema(self, data_list):
        """
        Tinh chỉnh nhãn và giá trị thực thể để cải thiện chất lượng đồ thị.

        Thực hiện:
        - Đổi DOCUMENT_RECORD chứa giấy tờ vật lý -> label phù hợp hơn
        - Gắn thẻ loại phương tiện vào SUBJECT/VIOLATION dựa trên ngữ cảnh
        """
        # Các từ khoá phương tiện để gắn thẻ
        vehicle_keywords = {
            "ô tô": "ô tô",
            "xe máy": "xe máy",
            "mô tô": "mô tô",
            "xe đạp": "xe đạp",
            "xe tải": "xe tải",
            "xe buýt": "xe buýt",
            "xe khách": "xe khách",
            "máy kéo": "máy kéo",
            "xe đạp điện": "xe đạp điện",
        }

        for chunk in data_list:
            content = chunk.get("original_content", "").lower()

            # Xác định loại phương tiện từ ngữ cảnh
            detected_vehicles = []
            for keyword, label in vehicle_keywords.items():
                if keyword in content:
                    detected_vehicles.append(label)

            for category in self.entity_categories:
                for entity in chunk.get(category, []):
                    label = entity.get("label", "")
                    value = entity.get("value", "").lower()

                    # Đổi DOCUMENT_RECORD chứa giấy tờ vật lý
                    if label == "DOCUMENT_RECORD":
                        for phys_doc in self.PHYSICAL_DOCS:
                            if phys_doc in value:
                                entity["label"] = "OBJECT_EQUIPMENT"
                                break

                    # Gắn thẻ phương tiện vào SUBJECT nếu ngữ cảnh rõ ràng
                    if label == "SUBJECT" and detected_vehicles and not any(
                        v in entity.get("name", "").lower() for v in detected_vehicles
                    ):
                        if len(detected_vehicles) == 1:
                            entity["name"] = f"{entity['name']} ({detected_vehicles[0]})"

        return data_list

    # =========================================================================
    # CÔNG ĐOẠN 4: TRÍCH XUẤT CÂY PHÂN CẤP VĂN BẢN
    # =========================================================================

    def extract_legal_hierarchy(self, data_list):
        """
        Tạo thêm entity cho cấu trúc phân cấp: Document -> Article -> Clause -> Point.

        Điều này giúp chatbot trích dẫn chính xác "Theo Điều X, Khoản Y, Điểm Z
        của Nghị định số ..."
        """
        doc_name = self._get_dynamic_doc_name(data_list)
        hierarchy_entities = {}

        for chunk in data_list:
            meta = chunk.get("metadata", {})
            dieu = meta.get("dieu")
            khoan = meta.get("khoan")
            diem = meta.get("diem")

            if dieu:
                article_key = f"Điều {dieu}"
                if article_key not in hierarchy_entities:
                    hierarchy_entities[article_key] = {
                        "id": f"hierarchy_{article_key}",
                        "label": "DOCUMENT_RECORD",
                        "name": f"{article_key} {doc_name}",
                        "value": f"{article_key} của {doc_name}"
                    }

        return data_list

    # =========================================================================
    # CÔNG ĐOẠN 5: NỐI CÁC ĐẢO CÔ LẬP (BACKWARD CONTEXT TRACING)
    # =========================================================================

    def link_isolated_islands(self, data_list):
        """
        Resolve các tham chiếu chéo giữa các Điều/Khoản/Điểm.

        Khi gặp entity có giá trị như:
        "Trừ các hành vi quy định tại điểm a, b khoản 2 Điều 5"

        Hàm này sẽ:
        1. Xây dựng bản đồ violation_map[dieu][khoan][diem] từ toàn bộ dữ liệu
        2. Lookup nội dung thật của "điểm a khoản 2 Điều 5"
        3. Đắp nội dung đó vào entity value để bổ sung ngữ cảnh
        """
        # Bước 5a: Xây dựng bản đồ vi phạm
        violation_map = {}  # violation_map[dieu][khoan][diem] = nội_dung
        for chunk in data_list:
            meta = chunk.get("metadata", {})
            dieu = meta.get("dieu")
            khoan = meta.get("khoan")
            diem = meta.get("diem")

            if not dieu:
                continue

            # Tìm tất cả VIOLATION entity trong chunk này
            for category in self.entity_categories:
                for entity in chunk.get(category, []):
                    if entity.get("label") == "VIOLATION":
                        if dieu not in violation_map:
                            violation_map[dieu] = {}
                        if khoan and khoan not in violation_map[dieu]:
                            violation_map[dieu][khoan] = {}
                        if diem and khoan:
                            violation_map[dieu][khoan][diem] = entity.get("value", "")
                        elif khoan:
                            violation_map[dieu][khoan]["_clause_level"] = entity.get("value", "")

        # Bước 5b: Resolve tham chiếu chéo
        ref_pattern = re.compile(
            r"(?:quy định tại|nêu tại|theo)\s+"
            r"(?:điểm\s+([a-zđ]+(?:\s*,\s*[a-zđ]+)*)\s+)?"
            r"(?:khoản\s+(\d+[a-z]?)\s+)?"
            r"Điều\s+(\d+[a-zđ]?)",
            re.IGNORECASE
        )

        for chunk in data_list:
            for category in self.entity_categories:
                for entity in chunk.get(category, []):
                    value = entity.get("value", "")
                    matches = ref_pattern.finditer(value)

                    resolved_refs = []
                    for match in matches:
                        diems = match.group(1)
                        khoan_ref = match.group(2)
                        dieu_ref = match.group(3)

                        if dieu_ref in violation_map:
                            if khoan_ref and khoan_ref in violation_map.get(dieu_ref, {}):
                                if diems:
                                    diem_list = [d.strip() for d in diems.split(",")]
                                    for d in diem_list:
                                        ref_value = violation_map[dieu_ref][khoan_ref].get(d, "")
                                        if ref_value:
                                            resolved_refs.append(
                                                f"[Điểm {d} Khoản {khoan_ref} Điều {dieu_ref}: {ref_value}]"
                                            )
                                else:
                                    ref_value = violation_map[dieu_ref][khoan_ref].get("_clause_level", "")
                                    if ref_value:
                                        resolved_refs.append(
                                            f"[Khoản {khoan_ref} Điều {dieu_ref}: {ref_value}]"
                                        )

                    if resolved_refs:
                        entity["value"] = f"{value} | Tham chiếu: {' '.join(resolved_refs)}"

        return data_list

    # =========================================================================
    # HÀM CHÍNH: CHẠY TOÀN BỘ PIPELINE LÀM SẠCH
    # =========================================================================

    def clean_data(self, input_file, output_file):
        """
        Chạy toàn bộ 5 công đoạn làm sạch theo thứ tự.

        Tham số:
            input_file: Đường dẫn tới file JSONL đầu vào (từ bước 2)
            output_file: Đường dẫn tới file JSONL đầu ra đã làm sạch
        """
        print(f"[Bước 3] Bắt đầu làm sạch dữ liệu...")
        data_list = self._read_jsonl(input_file)
        total = len(data_list)

        print(f"         Đã đọc {total} chunks từ {os.path.basename(input_file)}")

        # Công đoạn 0: Dọn dẹp markdown
        print(f"         [0/5] Dọn dẹp markdown và prefix...")
        for chunk in data_list:
            # Clean original_content: bỏ [Văn bản: ...] prefix và markdown
            if "original_content" in chunk:
                content = chunk["original_content"]
                content = re.sub(r'^\[Văn bản:.*?\]\s*', '', content)
                content = re.sub(r'^\[.*?\]\s*', '', content)
                chunk["original_content"] = self._clean_markdown(content)
            # Clean entity name/value
            for category in self.entity_categories:
                for entity in chunk.get(category, []):
                    for field in ["name", "value"]:
                        if field in entity and isinstance(entity[field], str):
                            entity[field] = self._clean_markdown(entity[field])

        # Công đoạn 1: Chuẩn hoá tên văn bản
        print(f"         [1/5] Chuẩn hoá tên văn bản...")
        data_list = self.clean_document_name(data_list)

        # Công đoạn 2: Bổ sung ngữ cảnh sửa đổi
        print(f"         [2/5] Bổ sung ngữ cảnh sửa đổi...")
        data_list = self.resolve_amendment_context(data_list)

        # Công đoạn 3: Tinh chỉnh schema
        print(f"         [3/5] Tinh chỉnh schema đồ thị...")
        data_list = self.refine_graph_schema(data_list)

        # Công đoạn 4: Trích xuất cây phân cấp
        print(f"         [4/5] Trích xuất cây phân cấp văn bản...")
        data_list = self.extract_legal_hierarchy(data_list)

        # Công đoạn 5: Nối các đảo cô lập
        print(f"         [5/5] Nối các đảo cô lập (resolve tham chiếu chéo)...")
        data_list = self.link_isolated_islands(data_list)

        # Ghi kết quả
        self._write_jsonl(data_list, output_file)

        # Thống kê kết quả
        total_entities = 0
        total_relationships = 0
        label_counts = {}
        for chunk in data_list:
            for category in self.entity_categories:
                for entity in chunk.get(category, []):
                    total_entities += 1
                    label = entity.get("label", "UNKNOWN")
                    label_counts[label] = label_counts.get(label, 0) + 1
            total_relationships += len(chunk.get("Relationships", []))

        print(f"\n[Bước 3] Hoàn tất làm sạch -> {output_file}")
        print(f"         Tổng chunks: {total}")
        print(f"         Tổng thực thể: {total_entities}")
        print(f"         Tổng quan hệ: {total_relationships}")
        print(f"         Phân bổ nhãn:")
        for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
            print(f"           - {label}: {count}")

        return data_list


def run_cleaning(input_file, output_file):
    """
    Thực thi bước làm sạch cho một file JSONL.

    Tham số:
        input_file: Đường dẫn tới file JSONL đầu vào (entities_raw)
        output_file: Đường dẫn tới file JSONL đầu ra (entities_cleaned)
    """
    cleaner = DataCleaner()
    return cleaner.clean_data(input_file, output_file)


if __name__ == "__main__":
    import sys
    from config import ENTITIES_RAW_DIR, ENTITIES_CLEANED_DIR

    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        jsonl_files = [f for f in os.listdir(ENTITIES_RAW_DIR) if f.endswith(".jsonl")]
        if not jsonl_files:
            print(f"Không tìm thấy file .jsonl nào trong {ENTITIES_RAW_DIR}")
            sys.exit(1)
        filename = jsonl_files[0]

    input_path = os.path.join(ENTITIES_RAW_DIR, filename)
    output_path = os.path.join(ENTITIES_CLEANED_DIR, filename)

    run_cleaning(input_path, output_path)
