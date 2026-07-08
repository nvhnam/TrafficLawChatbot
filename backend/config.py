from dotenv import load_dotenv
import os
import yaml
import logging
# path_save_json
folder_weight = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weight")
path_save_json = "folder_save_json_12_2"


load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config_data = yaml.safe_load(f)


API_KEY = os.getenv("API_KEY")
URI = config_data["database"]["uri"]
USER_NEO4J = os.getenv("USER_NEO4J")
PASSWORD_NEO4J = os.getenv("PASSWORD_NEO4J")

DB_NAME = config_data["database"]["name"]
MODEL_PRO = config_data["models"]["pro"]
MODEL_FLASH = config_data["models"]["flash"]
MODEL_3 = config_data["models"]["preview"]
MODEL_INGESTION = config_data["models"]["ingestion"]
MODEL_INGESTION_FALLBACK = config_data["models"].get("ingestion_fallback") or [MODEL_INGESTION]
_ingestion_rate_limit = config_data["models"].get("ingestion_rate_limit", {})
INGESTION_MIN_INTERVAL_SECONDS = _ingestion_rate_limit.get("min_interval_seconds", 4)
INGESTION_MAX_CALLS_PER_MINUTE = _ingestion_rate_limit.get("max_calls_per_minute", 10)
_chat_rate_limit = config_data["models"].get("chat_rate_limit", {})
CHAT_MIN_INTERVAL_SECONDS = _chat_rate_limit.get("min_interval_seconds", 2)
CHAT_MAX_CALLS_PER_MINUTE = _chat_rate_limit.get("max_calls_per_minute", 8)
MODEL_EMBEDDING = config_data["models"]["embedding"]
GENERATION_CONFIG = config_data["generation_config"]

_ingestion_config = config_data.get("ingestion", {})
USE_LOCAL_OCR = bool(_ingestion_config.get("use_local_ocr", False))
USE_LOCAL_EXTRACTION = bool(_ingestion_config.get("use_local_extraction", False))

PROMPT_EXTRACT_ENTITIES = f"""Bạn là một Chuyên gia xây dựng Đồ thị Tri thức (Knowledge Graph) phân tầng (Hierarchical GraphRAG) cho toàn bộ hệ thống Pháp luật Việt Nam.
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

DOCUMENT_MAPPING = {
    # 1. CÁC LUẬT CỦA QUỐC HỘI (Có năm ban hành rõ ràng)
    "36-2024-qh15_converted": "Luật Trật tự, an toàn giao thông đường bộ số 36/2024/QH15",
    "35-2024-qh15_converted": "Luật Đường bộ số 35/2024/QH15",
    "2012_479 + 480-15_2012_QH13_converted": "Luật Xử lý vi phạm hành chính số 15/2012/QH13",
    "83559_l23qh_converted": "Luật Giao thông đường bộ số 23/2008/QH12", # Viết tắt của Luật số 23 Quốc hội
    "100.signed_converted": "Bộ luật Hình sự số 100/2015/QH13",
    "12.signed_converted": "Luật sửa đổi Bộ luật Hình sự 2017 12/2017/QH14",

    # 2. CÁC NGHỊ ĐỊNH CỦA CHÍNH PHỦ (Phạt VPHC, Điều kiện kinh doanh...)
    "168-nd-cp.signed": "Nghị định số 168/2024/NĐ-CP",
    "100.signed": "Nghị định số 100/2019/NĐ-CP", # Nghị định nổi tiếng nhất về xử phạt giao thông
    "10.signed": "Nghị định số 10/2020/NĐ-CP", # Kinh doanh vận tải bằng xe ô tô
    "135.signed": "Nghị định số 135/2021/NĐ-CP", # Quy định về thiết bị kỹ thuật nghiệp vụ (bắn tốc độ, camera...)
    "121-cp.signed": "Nghị định số 121/2024/NĐ-CP",
    "16-ndcp.signed": "Nghị định số 16/2026/NĐ-CP",
    "17-nd.signed": "Nghị định số 17/2026/NĐ-CP",
    "19.signed": "Quyết định số 19/2020/NĐ-CP",
    "39-cp.signed": "Nghị định số 39/2023/NĐ-CP",
    "47-cp.signed": "Nghị định số 47/2022/NĐ-CP",
    "67-cp.signed": "Nghị định số 67/2023/NĐ-CP",
    "91.signed_converted": "Bộ luật Dân sự số 91/2015/QH13",
    "04-cp.signed": "Nghị định số 04/2026/NĐ-CP",
    "61nd.signed_converted": "Nghị định 61/2026/NĐ-CP",
    "336nd.signed": "Nghị định số 336/2025/NĐ-CP", # Hoặc có thể là số 33/2016/NĐ-CP gõ nhầm

    # 3. THÔNG TƯ LIÊN TỊCH
    "24-ttlt-byt-bgtvt.signed": "Thông tư liên tịch số 24/2015/TTLT-BYT-BGTVT", # Tiêu chuẩn sức khỏe người lái xe

    # 4. THÔNG TƯ BỘ CÔNG AN (Quản lý biển số, đăng ký xe, xử lý vi phạm)
    "24-bca.signed": "Thông tư số 24/2023/TT-BCA", # Cấp, thu hồi đăng ký, biển số xe cơ giới (Biển số định danh)
    "2020_877 + 878_63-2020-TT-BCA_converted": "Thông tư số 63/2020/TT-BCA",
    "46-bca.signed": "Thông tư số 46/2024/TT-BCA",
    "73-bca_converted": "Thông tư số 73/2024/TT-BCA",

    # 5. THÔNG TƯ BỘ GIAO THÔNG VẬN TẢI (Đào tạo lái xe, tốc độ, tải trọng)
    "31-bgtvt.signed": "Thông tư số 31/2019/TT-BGTVT", # Quy định về tốc độ và khoảng cách an toàn
    "46-bgtvt.signed": "Thông tư số 46/2015/TT-BGTVT", # Tải trọng, khổ giới hạn của đường bộ
    "38-bgtvt.signed": "Thông tư số 38/2019/TT-BGTVT",
    "04-bgtvt.signed": "Thông tư số 04/2022/TT-BGTVT",
    "01-bgtvt.signed": "Thông tư số 01/2021/TT-BGTVT",
    "08-bgtvt.signed": "Thông tư số 08/2023/TT-BGTVT",
    "51-bgtvt.signed": "Thông tư số 51/2022/TT-BGTVT",

    # 6. THÔNG TƯ BỘ TÀI CHÍNH (Lệ phí, phạt tiền)
    "229-btc.signed": "Thông tư số 229/2016/TT-BTC", # Quy định mức thu lệ phí đăng ký, cấp biển phương tiện
    "37-btc.signed": "Thông tư số 37/2023/TT-BTC", # Quy định mức thu phí sát hạch lái xe
    "70-btc_converted": "Thông tư số 70/2021/TT-BTC", # Mức thu phí sử dụng đường bộ

    # 7. CÁC FILE KHÔNG ĐỦ HẬU TỐ (Cần đối chiếu nội dung)
    "42.signed": "Nghị định số 42/2020/NĐ-CP", # Hoặc Thông tư số 42
    # "03.signed_04": "Nghị định số 03/2021/NĐ-CP", # Có thể là NĐ về bảo hiểm TNDS bắt buộc
}

