"""
Bước 3b: Hậu xử lý bổ sung thực thể thiếu bằng suy luận ngữ cảnh.

Giải quyết 3 vấn đề chính mà regex đơn thuần không bắt được:
1. SUBJECT thiếu: Suy ra chủ thể từ khoản cha khi tiêu đề Điều không rõ
2. PENALTY_MEASURE thiếu: Resolve tham chiếu "tại khoản X" trong khoản phạt bổ sung
3. POINT_DEDUCTION: Resolve tham chiếu "tại khoản X" trong khoản trừ điểm

Chạy sau step3_clean_data.py, trước khi xuất kết quả cuối cùng.
"""

import json
import re
import os
import logging

logger = logging.getLogger(__name__)


def load_jsonl(filepath):
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def save_jsonl(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _strip_prefix(content):
    text = re.sub(r'^\[Văn bản:.*?\]\s*', '', content)
    text = re.sub(r'^\[.*?\]\s*', '', text)
    return text


def run_enrichment(jsonl_file, chunks_file):
    """
    Bổ sung thực thể thiếu bằng suy luận ngữ cảnh.

    Tham số:
        jsonl_file: File JSONL đã qua bước clean (entities_cleaned)
        chunks_file: File JSON chứa chunks gốc (dùng để đọc nội dung đầy đủ)
    """
    data = load_jsonl(jsonl_file)
    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"[Bước 3b] Bắt đầu bổ sung thực thể thiếu...")

    stats = {"penalty_added": 0, "subject_added": 0, "point_added": 0}

    # =========================================================================
    # GIAI ĐOẠN 1: Xây dựng bản đồ khoản phạt bổ sung (CHI TIẾT ĐẾN TỪNG ĐIỂM)
    # =========================================================================
    # Quét khoản phạt bổ sung (khoản 11, 12...) để tìm tham chiếu:
    #   "tại điểm đ khoản 2" → chỉ áp dụng cho điểm đ khoản 2
    #   "tại khoản 4" (không nêu điểm) → áp dụng cho toàn bộ khoản 4
    #
    # Key: (dieu, khoan, diem_or_None) → penalty_text
    # Khi diem=None nghĩa là áp dụng cho toàn bộ khoản

    PENALTY_SIMPLE_PATTERN = re.compile(
        r"(?:tại\s+)((?:điểm\s+[a-zđ][\s,]*)*(?:khoản\s+\d+[a-z]?)(?:[\s,;và]*(?:điểm\s+[a-zđ][\s,]*)*(?:khoản\s+\d+[a-z]?))*)"
        r"[^.]*?"
        r"((?:tước quyền sử dụng|tịch thu|đình chỉ)[^.;]*?)(?:\.|;|$)",
        re.IGNORECASE | re.DOTALL
    )

    # Pattern để tách "điểm a, điểm b khoản 2; khoản 4; điểm c khoản 5"
    # thành list of (khoan, [diem_list])
    KHOAN_DIEM_PATTERN = re.compile(
        r"((?:điểm\s+[a-zđ](?:\s*,\s*điểm\s+[a-zđ])*\s+)?khoản\s+(\d+[a-z]?))",
        re.IGNORECASE
    )
    DIEM_IN_REF_PATTERN = re.compile(r"điểm\s+([a-zđ])", re.IGNORECASE)

    penalty_map = {}  # (dieu, khoan, diem_or_None) -> [{"text": ...}]

    for chunk in data:
        meta = chunk.get("metadata", {})
        dieu = meta.get("dieu")
        content = chunk.get("original_content", "")
        raw = _strip_prefix(content)

        is_penalty_clause = (
            "xử phạt bổ sung" in raw.lower() or
            "tước quyền" in raw.lower() or
            "tịch thu" in raw.lower()
        )
        if not is_penalty_clause or not dieu:
            continue

        for match in PENALTY_SIMPLE_PATTERN.finditer(raw):
            ref_text = match.group(1).strip()
            penalty_text = match.group(2).strip()

            if len(penalty_text) < 10:
                continue

            # Tách ref_text thành các cặp (khoan, [diem_list])
            # Ví dụ: "điểm đ khoản 2; điểm h, điểm i khoản 3; khoản 4"
            # → [(2, ['đ']), (3, ['h','i']), (4, [])]
            for km in KHOAN_DIEM_PATTERN.finditer(ref_text):
                full_ref = km.group(1)
                khoan_num = km.group(2)
                diems = DIEM_IN_REF_PATTERN.findall(full_ref)

                if diems:
                    # Có điểm cụ thể → chỉ áp dụng cho các điểm đó
                    for d in diems:
                        key = (dieu, khoan_num, d)
                        if key not in penalty_map:
                            penalty_map[key] = []
                        if not any(p["text"] == penalty_text for p in penalty_map[key]):
                            penalty_map[key].append({"text": penalty_text})
                else:
                    # Không nêu điểm → áp dụng cho toàn bộ khoản
                    key = (dieu, khoan_num, None)
                    if key not in penalty_map:
                        penalty_map[key] = []
                    if not any(p["text"] == penalty_text for p in penalty_map[key]):
                        penalty_map[key].append({"text": penalty_text})

    print(f"         Tìm được {len(penalty_map)} nhóm (khoản/điểm) có phạt bổ sung")

    # =========================================================================
    # GIAI ĐOẠN 2: Gắn PENALTY_MEASURE vào chunk VIOLATION tương ứng
    # =========================================================================
    for i, chunk in enumerate(data):
        meta = chunk.get("metadata", {})
        dieu = meta.get("dieu")
        khoan = meta.get("khoan")
        diem = meta.get("diem")

        if not dieu or not khoan:
            continue

        # Tìm penalty áp dụng cho chunk này:
        # 1. Exact match: (dieu, khoan, diem) — khi tham chiếu nêu rõ điểm
        # 2. Whole-khoản: (dieu, khoan, None) — khi tham chiếu chỉ nêu khoản
        applicable_penalties = []
        exact_key = (dieu, khoan, diem)
        whole_key = (dieu, khoan, None)

        if exact_key in penalty_map:
            applicable_penalties.extend(penalty_map[exact_key])
        if whole_key in penalty_map:
            applicable_penalties.extend(penalty_map[whole_key])

        if not applicable_penalties:
            continue

        # Kiểm tra chunk này có VIOLATION không
        violations = [
            e for e in chunk.get("Level_2_Rules_Actions", [])
            if e.get("label") == "VIOLATION"
        ]
        if not violations:
            continue

        # Kiểm tra đã có PENALTY_MEASURE chưa
        existing_penalties = [
            e for e in chunk.get("Attributes_Measures", [])
            if e.get("label") == "PENALTY_MEASURE"
        ]

        for penalty_info in applicable_penalties:
            penalty_text = penalty_info["text"]
            # Kiểm tra trùng
            already_exists = any(
                penalty_text in ep.get("value", "")
                for ep in existing_penalties
            )
            if already_exists:
                continue

            # Tạo PENALTY_MEASURE mới
            chunk_uuid = meta.get("chunk_uuid", "unknown")
            existing_ids = set()
            for cat in ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]:
                for e in chunk.get(cat, []):
                    existing_ids.add(e.get("id", ""))

            # Tìm ID chưa dùng
            n = 1
            while f"{chunk_uuid}_ep{n}" in existing_ids:
                n += 1
            penalty_id = f"{chunk_uuid}_ep{n}"

            # Tạo tên ngắn gọn
            short_text = penalty_text[:80] + "..." if len(penalty_text) > 80 else penalty_text
            data[i]["Attributes_Measures"].append({
                "id": penalty_id,
                "label": "PENALTY_MEASURE",
                "name": short_text,
                "value": penalty_text
            })

            # Nối với VIOLATION
            for v in violations:
                data[i]["Relationships"].append({
                    "source": v["id"],
                    "type": "HAS_PENALTY",
                    "target": penalty_id
                })

            stats["penalty_added"] += 1

    # =========================================================================
    # GIAI ĐOẠN 3: Bổ sung SUBJECT cho Điều dạng "các hành vi vi phạm khác"
    # =========================================================================
    # Khi tiêu đề Điều không chứa chủ thể cụ thể, nhìn vào nội dung khoản
    # để suy ra. Nếu khoản chứa "người điều khiển" → gán SUBJECT.

    SUBJECT_IN_CLAUSE = re.compile(
        r"(?:đối với|Đối với)\s+((?:người|chủ)\s+[^,;.]{5,60})",
        re.IGNORECASE
    )

    for i, chunk in enumerate(data):
        meta = chunk.get("metadata", {})
        # Chỉ bổ sung cho chunk chưa có SUBJECT
        has_subject = any(
            e.get("label") == "SUBJECT"
            for e in chunk.get("Level_3_Foundations", [])
        )
        if has_subject:
            continue

        raw = _strip_prefix(chunk.get("original_content", ""))
        match = SUBJECT_IN_CLAUSE.search(raw)
        if match:
            subject_text = match.group(1).strip()
            subject_text = re.sub(r'\s+', ' ', subject_text)

            chunk_uuid = meta.get("chunk_uuid", "unknown")
            subject_id = f"{chunk_uuid}_es1"
            data[i]["Level_3_Foundations"].append({
                "id": subject_id,
                "label": "SUBJECT",
                "name": subject_text[:60],
                "value": subject_text
            })

            # Nối với VIOLATION
            for v in chunk.get("Level_2_Rules_Actions", []):
                if v.get("label") == "VIOLATION":
                    data[i]["Relationships"].append({
                        "source": subject_id,
                        "type": "COMMITS",
                        "target": v["id"]
                    })

            stats["subject_added"] += 1

    # =========================================================================
    # GIAI ĐOẠN 4: Thống kê và lưu
    # =========================================================================
    save_jsonl(data, jsonl_file)

    total_entities = 0
    label_counts = {}
    total_rels = 0
    for chunk in data:
        for cat in ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]:
            for e in chunk.get(cat, []):
                total_entities += 1
                label = e.get("label", "?")
                label_counts[label] = label_counts.get(label, 0) + 1
        total_rels += len(chunk.get("Relationships", []))

    print(f"         Đã bổ sung:")
    print(f"           - PENALTY_MEASURE: +{stats['penalty_added']}")
    print(f"           - SUBJECT: +{stats['subject_added']}")
    print(f"\n[Bước 3b] Hoàn tất -> {jsonl_file}")
    print(f"          Tổng thực thể: {total_entities}")
    print(f"          Tổng quan hệ: {total_rels}")
    print(f"          Phân bổ nhãn:")
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"            - {label}: {count}")

    return data
