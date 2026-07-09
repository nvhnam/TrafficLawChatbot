#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score.py — Chấm điểm kết quả các hệ thống so với GOLD. KHÔNG tốn token.

Đọc:  test_questions.csv (đáp án gold)  +  results/*_results.jsonl (câu trả lời)
Rút trường dự đoán từ câu trả lời bằng REGEX (chung cho mọi hệ thống -> công bằng):
    mức phạt (VND), căn cứ Điều/Khoản/Điểm, có "không có dữ liệu" không, có "hỏi lại" không.
Tính: fine/legal/no_data/clarification accuracy, hallucination_rate,
      + Wilson 95% CI + kiểm định McNemar (A vs B).

Xuất: results/comparison_report.csv  và in bảng ra màn hình.

Chạy:  python data/evaluation/harness/score.py
"""
import csv
import glob
import json
import math
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEST = REPO / "data/evaluation/test/test_questions.csv"
RESULTS = REPO / "data/evaluation/results"

# ----------------------------- rút trường từ text -----------------------------
_MULT = {"nghìn": 1_000, "ngàn": 1_000, "triệu": 1_000_000}
_MONEY_RE = re.compile(
    r"(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)\s*(triệu|nghìn|ngàn)?\s*(?:đồng|vnđ|₫)?",
    re.IGNORECASE)


def extract_money(text: str):
    """Trả về danh sách số tiền (VND) tìm thấy gần đơn vị tiền tệ."""
    amounts = []
    for m in re.finditer(r"([\d.,]+)\s*(triệu|nghìn|ngàn)?\s*(đồng|vnđ|₫)", text, re.IGNORECASE):
        num, mult = m.group(1), (m.group(2) or "").lower()
        try:
            val = float(num.replace(".", "").replace(",", ".")) if mult else int(num.replace(".", ""))
        except ValueError:
            continue
        val = int(val * _MULT.get(mult, 1))
        if val >= 10_000:                      # loại số quá nhỏ (không phải mức phạt)
            amounts.append(val)
    return amounts


def extract_citation(text: str):
    dieu = re.search(r"Điều\s+(\d+)", text)
    khoan = re.search(r"[Kk]hoản\s+(\d+)", text)
    diem = re.search(r"[Đđ]iểm\s+([a-zà-ỹ])\b", text)
    return (dieu.group(1) if dieu else "",
            khoan.group(1) if khoan else "",
            diem.group(1) if diem else "")


_NODATA = ["không có dữ liệu", "không tìm thấy", "không có thông tin", "không có căn cứ",
           "không thuộc phạm vi", "ngoài phạm vi", "tôi không biết", "không rõ quy định"]
_CLARIFY = ["loại xe nào", "loại phương tiện nào", "phương tiện gì", "vui lòng cho biết",
            "bạn đang hỏi", "cho biết loại", "xe gì", "bạn muốn hỏi về", "cần biết thêm"]


def is_no_data(text): t = text.lower(); return any(k in t for k in _NODATA)
def is_clarify(text): t = text.lower(); return any(k in t for k in _CLARIFY)


def predict_fields(answer: str):
    money = extract_money(answer)
    d, k, p = extract_citation(answer)
    return {
        "amounts": money,                       # TẤT CẢ số tiền tìm thấy
        "pred_fine_min": min(money) if money else None,
        "pred_fine_max": max(money) if money else None,
        "pred_dieu": d, "pred_khoan": k, "pred_diem": p,
        "pred_no_data": is_no_data(answer),
        "pred_clarify": is_clarify(answer),
        "has_citation": bool(d),
        "has_fine": bool(money),
    }


# ----------------------------- thống kê -----------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (round(100 * p, 1), round(100 * (center - half), 1), round(100 * (center + half), 1))


def mcnemar(a_correct, b_correct):
    """a_correct/b_correct: dict question_id->bool (cùng tập câu). Trả (b, c, p)."""
    ids = set(a_correct) & set(b_correct)
    b = sum(1 for i in ids if a_correct[i] and not b_correct[i])   # A đúng, B sai
    c = sum(1 for i in ids if not a_correct[i] and b_correct[i])   # A sai, B đúng
    if b + c == 0:
        return b, c, 1.0
    z = (abs(b - c) - 1) / math.sqrt(b + c)          # xấp xỉ chuẩn (hiệu chỉnh liên tục)
    p = math.erfc(z / math.sqrt(2))                  # 2 phía
    return b, c, round(p, 4)


def norm(s): return str(s or "").strip().lower()


def main():
    gold = {r["question_id"]: r for r in csv.DictReader(open(TEST, encoding="utf-8-sig"))}

    files = sorted(glob.glob(str(RESULTS / "*_results.jsonl")))
    if not files:
        print("Chưa có kết quả trong results/. Chạy run_systems.py trước."); return

    # per-system: question_id -> record đã chấm
    systems = {}
    for f in files:
        sysname = Path(f).stem.replace("_results", "")
        recs = {}
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            recs[r["question_id"]] = r
        systems[sysname] = recs

    report_rows = []
    correct_map = {}   # sysname -> {qid: bool overall-correct} (cho McNemar)

    for sysname, recs in systems.items():
        # bộ đếm
        fine_k = fine_n = 0
        legal_k = legal_n = 0
        nodata_k = nodata_n = 0
        clar_k = clar_n = 0
        hallu_k = hallu_n = 0
        overall = {}

        for qid, g in gold.items():
            if qid not in recs:
                continue
            pred = predict_fields(recs[qid]["answer"])
            qtype = g["question_type"]
            ans_type = g["expected_answer_type"]

            if ans_type == "answer":
                # mức phạt
                if g["gold_fine_min"]:
                    fine_n += 1
                    # đúng nếu câu trả lời có NÊU đúng khoảng gold (cả min và max xuất hiện),
                    # dù câu trả lời dài và nhắc thêm số khác -> công bằng cho cả A và B
                    gmin, gmax = int(g["gold_fine_min"]), int(g["gold_fine_max"])
                    ok_fine = (gmin in pred["amounts"]) and (gmax in pred["amounts"])
                    fine_k += ok_fine
                    overall[qid] = ok_fine
                # căn cứ điều luật
                if g["gold_article"]:
                    legal_n += 1
                    ok_legal = (norm(pred["pred_dieu"]) == norm(g["gold_article"]) and
                                (not g["gold_clause"] or norm(pred["pred_khoan"]) == norm(g["gold_clause"])))
                    legal_k += ok_legal

            elif ans_type == "no_data":         # out_of_scope
                nodata_n += 1
                ok = pred["pred_no_data"] and not (pred["has_fine"] or pred["has_citation"])
                nodata_k += ok
                overall[qid] = ok
                hallu_n += 1
                hallu_k += (pred["has_fine"] or pred["has_citation"]) and not pred["pred_no_data"]

            elif ans_type == "ask_clarification":   # missing_info
                clar_n += 1
                ok = pred["pred_clarify"] or pred["pred_no_data"]
                clar_k += ok
                overall[qid] = ok
                hallu_n += 1
                hallu_k += pred["has_fine"] and not (pred["pred_clarify"] or pred["pred_no_data"])

        correct_map[sysname] = overall

        def add(metric, k, n):
            pct, lo, hi = wilson(k, n)
            report_rows.append({"system": sysname, "metric": metric, "n": n,
                                "correct": k, "accuracy_%": pct, "ci95_low": lo, "ci95_high": hi})

        add("fine_accuracy", fine_k, fine_n)
        add("legal_basis_accuracy", legal_k, legal_n)
        add("no_data_accuracy", nodata_k, nodata_n)
        add("clarification_accuracy", clar_k, clar_n)
        add("hallucination_rate", hallu_k, hallu_n)

    # ---- ghi CSV ----
    out = RESULTS / "comparison_report.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["system", "metric", "n", "correct",
                                          "accuracy_%", "ci95_low", "ci95_high"])
        w.writeheader()
        for row in report_rows:
            w.writerow(row)

    # ---- in bảng ----
    print(f"\n{'system':14} {'metric':24} {'n':>4} {'acc%':>7}  95% CI")
    print("-" * 62)
    for row in report_rows:
        print(f"{row['system']:14} {row['metric']:24} {row['n']:>4} "
              f"{row['accuracy_%']:>6}%  [{row['ci95_low']}, {row['ci95_high']}]")

    # ---- McNemar A vs B ----
    names = list(correct_map)
    if len(names) >= 2:
        a, b = names[0], names[1]
        bb, cc, p = mcnemar(correct_map[a], correct_map[b])
        print(f"\nMcNemar ({a} vs {b}): {a} đúng-{b} sai = {bb}, "
              f"{a} sai-{b} đúng = {cc}, p = {p} "
              f"{'(khác biệt có ý nghĩa, p<0.05)' if p < 0.05 else '(chưa có ý nghĩa)'}")

    print(f"\nĐã ghi: {out}")


if __name__ == "__main__":
    main()
