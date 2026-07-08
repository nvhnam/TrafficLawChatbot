"""
Cấu hình chung cho toàn bộ data pipeline.
Đọc các tham số từ config.yaml và .env.
"""
from dotenv import load_dotenv
import os
import yaml

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config_data = yaml.safe_load(f)

# --- Khoá API ---
API_KEY = os.getenv("API_KEY")

# --- Cấu hình model ---
MODEL_PRO = config_data["models"]["pro"]
MODEL_FLASH = config_data["models"]["flash"]

# --- Đường dẫn thư mục ---
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CHUNKS_DIR = os.path.join(OUTPUT_DIR, "chunks")
ENTITIES_RAW_DIR = os.path.join(OUTPUT_DIR, "entities_raw")
ENTITIES_CLEANED_DIR = os.path.join(OUTPUT_DIR, "entities_cleaned")

# Đảm bảo thư mục tồn tại
for d in [INPUT_DIR, CHUNKS_DIR, ENTITIES_RAW_DIR, ENTITIES_CLEANED_DIR]:
    os.makedirs(d, exist_ok=True)

# --- Ánh xạ tên văn bản ---
DOCUMENT_MAPPING = {
    "100.signed": "Nghị định số 100/2019/NĐ-CP",
    "168-nd-cp.signed": "Nghị định số 168/2024/NĐ-CP",
    "123-2021nd-cp": "Nghị định số 123/2021/NĐ-CP",
}

# --- Prompt trích xuất thực thể ---
PROMPT_EXTRACT_ENTITIES = """Bạn là một Chuyên gia xây dựng Đồ thị Tri thức (Knowledge Graph) phân tầng (Hierarchical GraphRAG) cho toàn bộ hệ thống Pháp luật Việt Nam.
Nhiệm vụ của bạn là đọc đoạn văn bản luật (Markdown) dưới đây và trích xuất các Thực thể (Entities) cùng Quan hệ (Edges), sau đó PHÂN LOẠI CHÚNG VÀO CẤU TRÚC JSON PHÂN TẦNG.

[CÁC QUY TẮC TRÍCH XUẤT CỐT LÕI]
1. BÁM SÁT NGUYÊN VĂN Ở TRƯỜNG 'value': Giữ nguyên văn phong, cấu trúc. Tuyệt đối KHÔNG tự ý tóm tắt văn bản gốc.
2. CHUẨN HÓA Ở TRƯỜNG 'name': Rút trích một cụm từ ngắn gọn, bao hàm ý nghĩa nhất để làm tên định danh cho thực thể (dùng cho tìm kiếm vector).
3. DỌN DẸP LỖI OCR: Tự động sửa các lỗi chính tả, lỗi dấu câu về tiếng Việt chuẩn xác trước khi đưa vào JSON.
4. QUY ĐỊNH VỀ ID: Các "id" (VD: "e1", "e2", "e3") phải là DUY NHẤT trên toàn bộ JSON, không được trùng lặp giữa các tầng.
5. SỬA ĐỔI/BÃI BỎ: Trích xuất các quy định mới trong ngoặc kép như luật bình thường, ĐỒNG THỜI tạo thực thể DOCUMENT_RECORD cho Điều/Khoản bị sửa/bãi bỏ để nối quan hệ AMENDS hoặc REPEALS.
6. XỬ LÝ TIỀN (MONEY_AMOUNT): Trích xuất min, max bằng số nguyên (VND). Nếu luật ghi "phạt 2 triệu", để min=2000000, max=2000000. Nếu "phạt đến 2 triệu", để min=0, max=2000000. TUYỆT ĐỐI CHỈ TẠO trường "min" và "max" CHO NHÃN "MONEY_AMOUNT", các nhãn khác cấm thêm 2 trường này.

[HỆ THỐNG NHÃN - ENTITY LABELS CHO PHÉP]
- Level_3_Foundations (Mỏ neo pháp lý): "SUBJECT", "LEGAL_CONCEPT", "DEFINITION", "STANDARD_CONDITION", "OBJECT_EQUIPMENT", "DOCUMENT_RECORD"
- Level_2_Rules_Actions (Quy định & Hành vi): "VIOLATION", "RIGHT_OBLIGATION", "PROHIBITED_EXCLUDED", "PROCEDURE_ACTION"
- Attributes_Measures (Thuộc tính bổ trợ): "PENALTY_MEASURE", "MONEY_AMOUNT", "POINT_DEDUCTION", "TIME_DURATION", "PERCENTAGE"

[LƯỢC ĐỒ QUAN HỆ - EDGE TYPES CHO PHÉP]
1. "HAS_RIGHT_OBLIGATION": SUBJECT -> RIGHT_OBLIGATION
2. "IS_PROHIBITED_OR_EXCLUDED": SUBJECT -> PROHIBITED_EXCLUDED
3. "COMMITS": SUBJECT -> VIOLATION
4. "EXECUTES_ACTION": SUBJECT -> PROCEDURE_ACTION
5. "MEETS_CONDITION": SUBJECT (hoặc OBJECT_EQUIPMENT, PROCEDURE_ACTION) -> STANDARD_CONDITION
6. "HAS_PENALTY": VIOLATION (hoặc SUBJECT) -> PENALTY_MEASURE
7. "HAS_MONEY_AMOUNT": VIOLATION (hoặc SUBJECT, PROCEDURE_ACTION) -> MONEY_AMOUNT
8. "DEDUCTS_POINT": VIOLATION -> POINT_DEDUCTION
9. "HAS_AUTHORITY": SUBJECT -> VIOLATION (hoặc PENALTY_MEASURE, OBJECT_EQUIPMENT)
10. "REQUIRES_DOCUMENT": PROCEDURE_ACTION (hoặc SUBJECT) -> DOCUMENT_RECORD
11. "HAS_DURATION": PENALTY_MEASURE (hoặc PROCEDURE_ACTION, DOCUMENT_RECORD) -> TIME_DURATION
12. "APPLIES_TO_OBJECT": PROCEDURE_ACTION (hoặc VIOLATION, STANDARD_CONDITION) -> OBJECT_EQUIPMENT
13. "DEFINES": LEGAL_CONCEPT -> DEFINITION
14. "HAS_PERCENTAGE": VIOLATION (hoặc RIGHT_OBLIGATION) -> PERCENTAGE
15. "AMENDS": DOCUMENT_RECORD (mới) -> DOCUMENT_RECORD (bị sửa)
16. "REPEALS": DOCUMENT_RECORD (mới) -> DOCUMENT_RECORD (bị bãi bỏ)

Văn bản luật:
\"\"\"actual_chunk_count_replace\"\"\"

BẮT BUỘC TRẢ VỀ DUY NHẤT MỘT KHỐI JSON HỢP LỆ (Theo mẫu dưới đây, mảng nào không có thì để []):
{{
  "Level_3_Foundations": [
    {{
      "id": "e1",
      "label": "SUBJECT",
      "name": "Người điều khiển xe mô tô",
      "value": "người điều khiển xe mô tô, xe gắn máy"
    }}
  ],
  "Level_2_Rules_Actions": [
    {{
      "id": "e2",
      "label": "VIOLATION",
      "name": "Không đội mũ bảo hiểm",
      "value": "không đội mũ bảo hiểm cho người đi mô tô, xe máy"
    }}
  ],
  "Attributes_Measures": [
    {{
      "id": "e3",
      "label": "MONEY_AMOUNT",
      "name": "Từ 400.000 đến 600.000 đồng",
      "value": "phạt tiền từ 400.000 đồng đến 600.000 đồng",
      "min": 400000,
      "max": 600000
    }},
    {{
      "id": "e4",
      "label": "PENALTY_MEASURE",
      "name": "Tước quyền sử dụng Giấy phép lái xe",
      "value": "Tước quyền sử dụng Giấy phép lái xe từ 01 tháng đến 03 tháng"
    }}
  ],
  "Relationships": [
    {{
      "source": "e1",
      "type": "COMMITS",
      "target": "e2"
    }},
    {{
      "source": "e2",
      "type": "HAS_MONEY_AMOUNT",
      "target": "e3"
    }}
  ]
}}
"""
