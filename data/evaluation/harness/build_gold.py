#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_gold.py — Dựng bộ GOLD (300 lỗi giao thông chuẩn hóa) từ JSONL đã trích xuất.

INPUT (3 nguồn, KHÔNG tốn API):
  - 100/2019: bản Gemini tác giả gốc   (sample/data_prepare_up_neo4j/100.signed.jsonl)
  - 168/2024: bản Gemini tác giả gốc   (sample/data_prepare_up_neo4j/168-nd-cp.signed.jsonl)
  - 123/2021: bản regex của nhóm        (output/neo4j_ready/123-2021nd-cp.jsonl)

Ý tưởng: mỗi hành vi vi phạm đã tồn tại dưới dạng chuỗi quan hệ trong từng chunk:
    (SUBJECT) -COMMITS-> (VIOLATION) -HAS_MONEY_AMOUNT-> (MONEY_AMOUNT)
                                     -HAS_PENALTY------> (PENALTY_MEASURE) -HAS_DURATION-> (TIME_DURATION)
                                     -DEDUCTS_POINT----> (POINT_DEDUCTION)
                                     -MEETS_CONDITION--> (STANDARD_CONDITION)
    + metadata: document / dieu / khoan / diem   (căn cứ điều luật)
Script duyệt từng chunk, gom quanh mỗi VIOLATION thành 1 dòng gold, chuẩn hóa và ghi CSV.

OUTPUT:
  - violations_gold.csv     : mỗi dòng = 1 lỗi chuẩn hóa (đã dedup trong cùng văn bản)
  - violation_aliases.csv   : seed alias (behavior gốc) để nhóm bổ sung cách nói đời thường

Cách chạy:
    cd TrafficLawChatbot
    python data/evaluation/harness/build_gold.py

Nguyên tắc: GHI THEO TỪNG NGUỒN, flush ngay sau mỗi văn bản (chạy tới đâu lưu tới đó).
"""

import csv
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Cấu hình đường dẫn (tương đối so với gốc repo TrafficLawChatbot)
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[3]          # .../TrafficLawChatbot
OUT_DIR = REPO / "data" / "evaluation" / "gold"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (nhãn văn bản, đường dẫn jsonl, tên nghị định chuẩn, trạng thái hiệu lực)
SOURCES = [
    ("ND100", REPO / "data/pipeline/sample/data_prepare_up_neo4j/100.signed.jsonl",
     "Nghị định 100/2019/NĐ-CP", "old_base"),      # gốc, phần lớn bị 168 thay
    ("ND123", REPO / "data/pipeline/output/neo4j_ready/123-2021nd-cp.jsonl",
     "Nghị định 123/2021/NĐ-CP", "amendment"),      # sửa đổi 100
    ("ND168", REPO / "data/pipeline/sample/data_prepare_up_neo4j/168-nd-cp.signed.jsonl",
     "Nghị định 168/2024/NĐ-CP", "current"),        # hiện hành
]

ENTITY_KEYS = ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]

COLUMNS = [
    "violation_id", "legal_doc", "article", "clause", "point",
    "vehicle_type", "actor", "behavior_canonical", "behavior_raw",
    "condition_text", "fine_min", "fine_max", "fine_text",
    "additional_penalty", "penalty_duration", "point_deduction",
    "remedial_measure", "effective_status", "source_text", "note",
]

# ---------------------------------------------------------------------------
# Chuẩn hóa loại phương tiện từ text SUBJECT (thứ tự kiểm tra QUAN TRỌNG:
# 'mô tô' chứa chuỗi con 'ô tô' nên phải xét mô tô/xe máy TRƯỚC 'ô tô')
# ---------------------------------------------------------------------------
def normalize_vehicle(subject_text: str) -> str:
    t = (subject_text or "").lower()
    if not t.strip():
        return "không xác định"
    if "đi bộ" in t:
        return "người đi bộ"
    if "súc vật" in t or "vật nuôi" in t:
        return "xe súc vật kéo"
    if "xe đạp" in t or "thô sơ" in t:
        return "xe đạp/xe thô sơ"
    if "máy kéo" in t or "chuyên dùng" in t:
        return "máy kéo/xe máy chuyên dùng"
    if "mô tô" in t or "gắn máy" in t or "xe máy" in t:
        return "xe máy"
    if "ô tô" in t:
        return "ô tô"
    if "chủ phương tiện" in t or "chủ xe" in t:
        return "chủ phương tiện"
    if "người sử dụng lao động" in t or "cơ quan" in t or "tổ chức" in t:
        return "tổ chức/cá nhân khác"
    return "không xác định"


# ---------------------------------------------------------------------------
# Parse mức phạt tiền -> (fine_min, fine_max) dạng số nguyên VND
#   "Phạt tiền từ 200.000 đồng đến 400.000 đồng"  -> (200000, 400000)
#   "Phạt tiền 500.000 đồng"                       -> (500000, 500000)
#   không parse được                               -> (None, None)
# ---------------------------------------------------------------------------
_NUM = r"(\d{1,3}(?:\.\d{3})+|\d+)"
_RANGE_RE = re.compile(rf"từ\s*{_NUM}\s*(?:đồng)?\s*đến\s*{_NUM}\s*đồng", re.IGNORECASE)
_SINGLE_RE = re.compile(rf"{_NUM}\s*đồng", re.IGNORECASE)


def _to_int(s: str):
    try:
        return int(s.replace(".", "").strip())
    except (ValueError, AttributeError):
        return None


def parse_fine(money_text: str):
    t = money_text or ""
    m = _RANGE_RE.search(t)
    if m:
        return _to_int(m.group(1)), _to_int(m.group(2))
    m = _SINGLE_RE.search(t)
    if m:
        v = _to_int(m.group(1))
        return v, v
    return None, None


def val(e):
    """Ưu tiên .value (nguyên văn), lùi về .name."""
    return (e.get("value") or e.get("name") or "").strip()


# ---------------------------------------------------------------------------
# Trích các bản ghi lỗi từ 1 chunk
# ---------------------------------------------------------------------------
def extract_from_chunk(chunk: dict):
    ents = {}
    for k in ENTITY_KEYS:
        for e in chunk.get(k, []):
            if e.get("id"):
                ents[e["id"]] = e
    rels = chunk.get("Relationships", []) or []
    meta = chunk.get("metadata", {}) or {}
    source_text = (chunk.get("original_content") or "").strip()

    # Chỉ số cạnh theo hướng
    out = {}  # source_id -> list[(type, target_id)]
    inc = {}  # target_id -> list[(type, source_id)]
    for r in rels:
        s, tp, tg = r.get("source"), r.get("type"), r.get("target")
        if not (s and tp and tg):
            continue
        out.setdefault(s, []).append((tp, tg))
        inc.setdefault(tg, []).append((tp, s))

    def label_of(_id):
        return (ents.get(_id) or {}).get("label")

    def targets(_id, rel_type, want_label):
        res = []
        for tp, tg in out.get(_id, []):
            if tp == rel_type and label_of(tg) == want_label:
                res.append(ents[tg])
        return res

    records = []
    violation_ids = [i for i, e in ents.items() if e.get("label") == "VIOLATION"]

    # Fallback tiền/phạt ở mức chunk (khi không nối trực tiếp tới violation)
    chunk_money = [e for e in ents.values() if e.get("label") == "MONEY_AMOUNT"]

    for vid in violation_ids:
        v = ents[vid]

        # Chủ thể: SUBJECT -COMMITS-> VIOLATION (cạnh vào)
        subjects = [ents[s] for tp, s in inc.get(vid, [])
                    if tp == "COMMITS" and label_of(s) == "SUBJECT"]
        actor = subjects[0]["name"].strip() if subjects else ""
        vehicle = normalize_vehicle(val(subjects[0]) if subjects else "")

        # Mức phạt
        moneys = targets(vid, "HAS_MONEY_AMOUNT", "MONEY_AMOUNT")
        note = ""
        if not moneys and len(chunk_money) == 1:
            moneys = chunk_money            # fallback thận trọng: chunk có đúng 1 mức phạt
            note = "fine_fallback_chunk"
        fine_text = val(moneys[0]) if moneys else ""
        fine_min, fine_max = parse_fine(fine_text)

        # Hình thức bổ sung + thời hạn
        penalties = targets(vid, "HAS_PENALTY", "PENALTY_MEASURE")
        add_penalty = " | ".join(val(p) for p in penalties)
        durations = targets(vid, "HAS_DURATION", "TIME_DURATION")
        for p in penalties:                 # thời hạn có thể gắn vào node penalty
            durations += targets(p["id"], "HAS_DURATION", "TIME_DURATION")
        penalty_duration = " | ".join(dict.fromkeys(val(d) for d in durations))

        # Trừ điểm GPLX (đặc thù NĐ 168)
        points = targets(vid, "DEDUCTS_POINT", "POINT_DEDUCTION")
        point_deduction = " | ".join(val(p) for p in points)

        # Điều kiện áp dụng
        conds = targets(vid, "MEETS_CONDITION", "STANDARD_CONDITION")
        condition_text = " | ".join(val(c) for c in conds)

        # Biện pháp khắc phục (PROCEDURE_ACTION nếu có nối)
        remedials = targets(vid, "EXECUTES_ACTION", "PROCEDURE_ACTION")
        remedial = " | ".join(val(r) for r in remedials)

        records.append({
            "vehicle_type": vehicle,
            "actor": actor,
            "behavior_canonical": v.get("name", "").strip(),
            "behavior_raw": val(v),
            "condition_text": condition_text,
            "fine_min": fine_min if fine_min is not None else "",
            "fine_max": fine_max if fine_max is not None else "",
            "fine_text": fine_text,
            "additional_penalty": add_penalty,
            "penalty_duration": penalty_duration,
            "point_deduction": point_deduction,
            "remedial_measure": remedial,
            "source_text": source_text,
            "note": note,
            "_dieu": meta.get("dieu"), "_khoan": meta.get("khoan"), "_diem": meta.get("diem"),
        })
    return records


# ---------------------------------------------------------------------------
# Dedup trong cùng 1 văn bản: gộp theo (điều, khoản, điểm, hành vi, loại xe),
# giữ bản ghi ĐẦY ĐỦ TRƯỜNG nhất.
# ---------------------------------------------------------------------------
def dedup(records):
    def norm(s):
        return re.sub(r"\s+", " ", (s or "").lower()).strip()

    def fill_score(r):
        return sum(1 for f in ("fine_text", "additional_penalty", "point_deduction",
                               "condition_text", "actor") if r.get(f))

    best = {}
    for r in records:
        key = (r.get("_dieu"), r.get("_khoan"), r.get("_diem"),
               norm(r["behavior_canonical"]), r["vehicle_type"])
        if key not in best or fill_score(r) > fill_score(best[key]):
            best[key] = r
    return list(best.values())


def make_id(tag, r, seq):
    parts = [tag]
    for f in ("_dieu", "_khoan", "_diem"):
        v = r.get(f)
        if v:
            parts.append(str(v).replace(" ", ""))
    parts.append(f"{seq:04d}")
    return "_".join(parts)


# ---------------------------------------------------------------------------
def main():
    gold_path = OUT_DIR / "violations_gold.csv"
    alias_path = OUT_DIR / "violation_aliases.csv"

    total = 0
    by_doc, by_vehicle, with_fine = {}, {}, 0

    with open(gold_path, "w", newline="", encoding="utf-8-sig") as gf, \
         open(alias_path, "w", newline="", encoding="utf-8-sig") as af:
        gw = csv.DictWriter(gf, fieldnames=COLUMNS)
        gw.writeheader()
        aw = csv.writer(af)
        aw.writerow(["alias_id", "violation_id", "alias_text", "alias_type"])

        for tag, path, doc_name, status in SOURCES:
            if not path.exists():
                print(f"  [BỎ QUA] không thấy: {path}", file=sys.stderr)
                continue

            raw = []
            for line in open(path, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw += extract_from_chunk(json.loads(line))
                except json.JSONDecodeError:
                    continue

            deduped = dedup(raw)
            seq = 0
            for r in deduped:
                seq += 1
                vid = make_id(tag, r, seq)
                row = {c: r.get(c, "") for c in COLUMNS}
                row["violation_id"] = vid
                row["legal_doc"] = doc_name
                row["article"] = r.get("_dieu") or ""
                row["clause"] = r.get("_khoan") or ""
                row["point"] = r.get("_diem") or ""
                row["effective_status"] = status
                # cắt source_text dài cho gọn CSV (giữ đủ để truy vết)
                row["source_text"] = (row["source_text"] or "")[:600]
                gw.writerow(row)

                # seed alias: dòng behavior gốc để nhóm bổ sung cách nói đời thường
                aw.writerow([f"{vid}_a0", vid, r["behavior_canonical"], "canonical"])

                total += 1
                by_doc[tag] = by_doc.get(tag, 0) + 1
                by_vehicle[row["vehicle_type"]] = by_vehicle.get(row["vehicle_type"], 0) + 1
                if row["fine_min"] != "":
                    with_fine += 1

            gf.flush(); af.flush()      # <-- ghi tới đâu lưu tới đó (theo từng văn bản)
            print(f"  [OK] {tag}: {len(raw)} thô -> {len(deduped)} lỗi (đã dedup)")

    # -------- Thống kê --------
    print("\n================ THỐNG KÊ GOLD ================")
    print(f"Tổng số lỗi     : {total}")
    print(f"Có mức phạt (số): {with_fine}  ({100*with_fine//max(total,1)}%)")
    print("Theo văn bản    :", by_doc)
    print("Theo loại xe    :")
    for k, v in sorted(by_vehicle.items(), key=lambda x: -x[1]):
        print(f"   {v:5d}  {k}")
    print(f"\nĐã ghi: {gold_path}")
    print(f"Đã ghi: {alias_path}")
    print("\nBước sau: xem file, chọn/lọc ~300 lỗi cân bằng nhóm phương tiện, "
          "bổ sung alias đời thường vào violation_aliases.csv.")


if __name__ == "__main__":
    main()
