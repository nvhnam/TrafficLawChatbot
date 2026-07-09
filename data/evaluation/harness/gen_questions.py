#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_questions.py — Sinh 300 câu hỏi kiểm thử (test set) TỪ gold, KÈM ĐÁP ÁN GOLD.

Mỗi câu hỏi nối khóa ngoại về 1 lỗi trong violations_gold_300.csv, và mang theo
"đáp án đúng" (mức phạt, căn cứ điều/khoản/điểm...) để chấm điểm mà không cần join thủ công.

Phân bổ 300 câu (theo 300test.md §5):
    keyword       80  -> hỏi thẳng, đúng từ khóa luật        (answer)
    semantic      80  -> diễn đạt đời thường/khác từ khóa    (answer)  << lõi đánh giá ngữ nghĩa
    conditional   60  -> hỏi 2 phần / hỏi bổ sung / căn cứ   (answer)
    missing_info  40  -> thiếu loại xe -> phải HỎI LẠI        (ask_clarification)
    out_of_scope  40  -> ngoài 3 nghị định -> phải NÓI KHÔNG (no_data)

KHÔNG tốn API: sinh bằng template. Nhóm có thể tinh chỉnh câu semantic bằng tay sau.

Chạy:  python data/evaluation/harness/gen_questions.py
Output: data/evaluation/test/test_questions.csv
"""
import csv
import json
import random
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GOLD = REPO / "data/evaluation/gold/violations_gold_300.csv"
OUT = REPO / "data/evaluation/test/test_questions.csv"
random.seed(42)

# hiển thị loại xe tự nhiên trong câu hỏi
VEHICLE_DISPLAY = {
    "ô tô": "ô tô", "xe máy": "xe máy",
    "máy kéo/xe máy chuyên dùng": "xe máy chuyên dùng",
    "xe đạp/xe thô sơ": "xe đạp", "người đi bộ": "người đi bộ",
    "xe súc vật kéo": "xe do súc vật kéo", "chủ phương tiện": "chủ xe",
    "tổ chức/cá nhân khác": "",
}

COLS = [
    "question_id", "question", "question_type", "difficulty",
    "expected_answer_type", "expected_intent", "expected_vehicle_type",
    "expected_violation_id", "expected_entities",
    "gold_fine_min", "gold_fine_max", "gold_legal_doc",
    "gold_article", "gold_clause", "gold_point",
    "gold_additional_penalty", "gold_point_deduction", "gold_note",
]


def clean_behavior(text: str) -> str:
    """Rút gọn hành vi cho câu hỏi đọc tự nhiên: bỏ mệnh đề 'trừ...', ngoặc, cắt dài."""
    t = re.sub(r"\s+", " ", (text or "")).strip()
    t = re.split(r",?\s*trừ (?:trường hợp|các|hành vi)", t)[0]
    t = re.sub(r"\([^)]*\)", "", t).strip(" ,.;")
    if t:
        t = t[0].lower() + t[1:]
    return t[:110].strip(" ,.;")


def base_row(vid, q, qtype, diff, ans_type, intent, veh, gold, entities, note=""):
    return {
        "question_id": "", "question": q, "question_type": qtype, "difficulty": diff,
        "expected_answer_type": ans_type, "expected_intent": intent,
        "expected_vehicle_type": veh, "expected_violation_id": vid,
        "expected_entities": json.dumps(entities, ensure_ascii=False),
        "gold_fine_min": (gold or {}).get("fine_min", ""),
        "gold_fine_max": (gold or {}).get("fine_max", ""),
        "gold_legal_doc": (gold or {}).get("legal_doc", ""),
        "gold_article": (gold or {}).get("article", ""),
        "gold_clause": (gold or {}).get("clause", ""),
        "gold_point": (gold or {}).get("point", ""),
        "gold_additional_penalty": (gold or {}).get("additional_penalty", ""),
        "gold_point_deduction": (gold or {}).get("point_deduction", ""),
        "gold_note": note,
    }


# ---------------- các template câu hỏi ----------------
KEYWORD_TPL = [
    "{veh} {beh} thì bị phạt bao nhiêu tiền?",
    "Mức phạt đối với hành vi {veh} {beh} là bao nhiêu?",
    "{veh} {beh} bị xử phạt như thế nào?",
]
SEMANTIC_TPL = [
    "Lỡ {beh} khi đi {veh} thì mất bao nhiêu tiền?",
    "Đi {veh} mà {beh} có bị phạt nặng không, khoảng nhiêu?",
    "{veh} bị lỗi {beh} thì tốn bao nhiêu tiền phạt vậy?",
    "Chạy {veh} rồi {beh}, phạt cỡ nhiêu ạ?",
]
COND_FINE_BASIS_TPL = [
    "{veh} {beh} bị phạt bao nhiêu và căn cứ theo điều khoản nào?",
    "Cho hỏi {veh} {beh} phạt bao nhiêu, quy định ở đâu trong luật?",
]
COND_PENALTY_TPL = [
    "Ngoài phạt tiền, {veh} {beh} còn bị xử phạt bổ sung gì không?",
    "{veh} {beh} có bị tước bằng hay tịch thu xe gì không?",
]
MISSING_TPL = [
    "{beh} thì bị phạt bao nhiêu tiền?",
    "Cho hỏi lỗi {beh} phạt bao nhiêu ạ?",
]

OUT_OF_SCOPE = [
    "Tàu biển chở quá tải bị phạt bao nhiêu theo luật hàng hải?",
    "Máy bay hạ cánh sai đường băng bị xử phạt thế nào?",
    "Trốn thuế thu nhập cá nhân bị phạt bao nhiêu?",
    "Xây nhà không phép bị xử phạt ra sao?",
    "Câu cá ở khu vực cấm bị phạt bao nhiêu?",
    "Bán hàng giả trên mạng bị xử lý thế nào?",
    "Đánh bắt hải sản bằng thuốc nổ bị phạt bao nhiêu?",
    "Hút thuốc nơi công cộng bị phạt bao nhiêu tiền?",
    "Nuôi chó không rọ mõm nơi công cộng phạt bao nhiêu?",
    "Xả rác ra sông bị xử phạt như thế nào?",
    "Vi phạm bản quyền phần mềm bị phạt bao nhiêu?",
    "Gây ô nhiễm tiếng ồn ban đêm bị xử phạt sao?",
    "Kinh doanh không giấy phép bị phạt bao nhiêu?",
    "Chuyển nhượng đất không sổ đỏ bị xử lý thế nào?",
    "Làm giả bằng đại học bị phạt bao nhiêu?",
    "Nhập lậu điện thoại bị xử phạt ra sao?",
    "Tổ chức đánh bạc bị phạt bao nhiêu tiền?",
    "Bán rượu cho trẻ em bị xử phạt thế nào?",
    "Phá rừng phòng hộ bị phạt bao nhiêu?",
    "Săn bắt động vật hoang dã bị xử lý ra sao?",
    "Cho vay nặng lãi bị phạt bao nhiêu?",
    "Quảng cáo sai sự thật bị xử phạt thế nào?",
    "Sử dụng hóa chất cấm trong thực phẩm bị phạt bao nhiêu?",
    "Trốn nghĩa vụ quân sự bị xử lý ra sao?",
    "Vượt biên trái phép bị phạt bao nhiêu?",
    "Kết hôn giả để nhập tịch bị xử phạt thế nào?",
    "Xúc phạm người khác trên mạng xã hội bị phạt bao nhiêu?",
    "Lấn chiếm vỉa hè để kinh doanh bị xử lý ra sao?",
    "Đốt pháo trái phép dịp Tết bị phạt bao nhiêu?",
    "Nuôi động vật quý hiếm không phép bị xử phạt sao?",
    "Khai thác cát trái phép bị phạt bao nhiêu?",
    "Bán thuốc không kê đơn bị xử lý thế nào?",
    "Hôm nay trời có mưa không?",
    "Nấu phở bò cần những nguyên liệu gì?",
    "Đội tuyển Việt Nam đá với ai tối nay?",
    "Giá vàng hôm nay bao nhiêu một chỉ?",
    "Cách trồng cây xương rồng trong nhà?",
    "Thủ đô của nước Pháp là gì?",
    "Làm sao để học tiếng Anh nhanh?",
    "Mua vé máy bay đi Đà Nẵng ở đâu rẻ?",
]


def main():
    rows = list(csv.DictReader(open(GOLD, encoding="utf-8-sig")))
    random.shuffle(rows)

    # ưu tiên rows có bổ sung cho nhóm hỏi bổ sung
    with_pen = [r for r in rows if r["additional_penalty"]]
    without_pen = [r for r in rows if not r["additional_penalty"]]

    out = []
    used = set()

    def veh_disp(r):
        return VEHICLE_DISPLAY.get(r["vehicle_type"], r["vehicle_type"])

    def take(pool, n):
        picked = []
        for r in pool:
            if len(picked) >= n:
                break
            if r["violation_id"] not in used:
                picked.append(r); used.add(r["violation_id"])
        return picked

    # 1) keyword 80
    for i, r in enumerate(take(rows, 80)):
        beh = clean_behavior(r["behavior_canonical"])
        veh = veh_disp(r)
        q = KEYWORD_TPL[i % len(KEYWORD_TPL)].format(veh=veh, beh=beh).replace("  ", " ").strip().capitalize()
        out.append(base_row(r["violation_id"], q, "keyword", "easy", "answer", "ask_fine",
                             r["vehicle_type"], r, {"vehicle_type": r["vehicle_type"], "behavior": beh}))

    # 2) semantic 80
    for i, r in enumerate(take(rows, 80)):
        beh = clean_behavior(r["behavior_canonical"])
        veh = veh_disp(r)
        q = SEMANTIC_TPL[i % len(SEMANTIC_TPL)].format(veh=veh, beh=beh).replace("  ", " ").strip().capitalize()
        out.append(base_row(r["violation_id"], q, "semantic", "medium", "answer", "ask_fine",
                             r["vehicle_type"], r, {"vehicle_type": r["vehicle_type"], "behavior": beh}))

    # 3) conditional 60: ~ rows có bổ sung -> hỏi bổ sung; còn lại -> hỏi phạt+căn cứ
    pen_rows = take([r for r in with_pen], 20)
    for i, r in enumerate(pen_rows):
        beh = clean_behavior(r["behavior_canonical"]); veh = veh_disp(r)
        q = COND_PENALTY_TPL[i % len(COND_PENALTY_TPL)].format(veh=veh, beh=beh).replace("  ", " ").strip().capitalize()
        out.append(base_row(r["violation_id"], q, "conditional", "hard", "answer",
                             "ask_additional_penalty", r["vehicle_type"], r,
                             {"vehicle_type": r["vehicle_type"], "behavior": beh}))
    for i, r in enumerate(take(rows, 60 - len(pen_rows))):
        beh = clean_behavior(r["behavior_canonical"]); veh = veh_disp(r)
        q = COND_FINE_BASIS_TPL[i % len(COND_FINE_BASIS_TPL)].format(veh=veh, beh=beh).replace("  ", " ").strip().capitalize()
        out.append(base_row(r["violation_id"], q, "conditional", "hard", "answer",
                             "ask_fine_and_basis", r["vehicle_type"], r,
                             {"vehicle_type": r["vehicle_type"], "behavior": beh}))

    # 4) missing_info 40: bỏ loại xe -> ambiguous -> ask_clarification
    for i, r in enumerate(take(rows, 40)):
        beh = clean_behavior(r["behavior_canonical"])
        q = MISSING_TPL[i % len(MISSING_TPL)].format(beh=beh).replace("  ", " ").strip().capitalize()
        # đáp án gold: KHÔNG có mức phạt cụ thể (thiếu loại xe), phải hỏi lại
        out.append(base_row("", q, "missing_info", "hard", "ask_clarification", "ask_fine",
                             "", None, {"behavior": beh, "missing": "vehicle_type"},
                             note=f"thiếu loại xe; ứng viên: {r['violation_id']}"))

    # 5) out_of_scope 40
    for q in OUT_OF_SCOPE[:40]:
        out.append(base_row("", q, "out_of_scope", "hard", "no_data", "unknown",
                            "", None, {}, note="ngoài phạm vi 3 nghị định"))

    # đánh số + ghi (flush ngay)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for i, row in enumerate(out, 1):
            row["question_id"] = f"Q{i:03d}"
            w.writerow(row)
            f.flush()

    from collections import Counter
    print(f"Đã sinh {len(out)} câu -> {OUT}")
    print("Theo nhóm     :", dict(Counter(r["question_type"] for r in out)))
    print("Theo answer   :", dict(Counter(r["expected_answer_type"] for r in out)))
    print("\nVí dụ mỗi nhóm:")
    seen = set()
    for r in out:
        if r["question_type"] not in seen:
            seen.add(r["question_type"])
            print(f"  [{r['question_type']:12}] {r['question']}")
            if r["expected_violation_id"]:
                print(f"      -> gold: {r['gold_fine_min']}-{r['gold_fine_max']}đ | "
                      f"{r['gold_legal_doc']} Đ{r['gold_article']} K{r['gold_clause']} Đ{r['gold_point']}")


if __name__ == "__main__":
    main()
