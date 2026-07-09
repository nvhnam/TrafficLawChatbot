#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_gold.py — Chọn ~300 lỗi CÂN BẰNG từ violations_gold.csv (bản đầy đủ).

Tiêu chí (để bộ gold "đẹp" và dễ bảo vệ):
  - Chỉ lấy lỗi CÓ loại phương tiện xác định + CÓ mức phạt dạng số.
  - Phân tầng theo loại phương tiện (quota), phủ đủ nhóm hành vi quan trọng
    (nồng độ cồn, tốc độ, tín hiệu/đèn, giấy tờ, dừng đỗ...).
  - Trong mỗi nhóm: ưu tiên lỗi có hình thức bổ sung / trừ điểm, rồi trải đều
    theo Điều để không dồn vào một chỗ.
  - Trải trên cả 3 nghị định (100/123/168).

OUTPUT: violations_gold_300.csv  (thêm cột behavior_category để phân tích)

Chạy:  python data/evaluation/harness/sample_gold.py
"""
import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GOLD = REPO / "data/evaluation/gold/violations_gold.csv"
OUT = REPO / "data/evaluation/gold/violations_gold_300.csv"

# Quota theo loại phương tiện (sẽ tự thu nhỏ nếu không đủ dữ liệu)
QUOTA = {
    "ô tô": 80,
    "xe máy": 80,
    "máy kéo/xe máy chuyên dùng": 40,
    "xe đạp/xe thô sơ": 30,
    "tổ chức/cá nhân khác": 40,
    "người đi bộ": 15,
    "xe súc vật kéo": 15,
}
TARGET = 300


def behavior_category(text: str) -> str:
    t = text.lower()
    if "nồng độ cồn" in t or "có cồn" in t or "ma túy" in t or "chất kích thích" in t:
        return "cồn/ma túy"
    if "tốc độ" in t:
        return "tốc độ"
    if "đèn" in t or "hiệu lệnh" in t or "tín hiệu" in t or "biển báo" in t or "vạch" in t:
        return "tín hiệu/biển báo"
    if "giấy phép" in t or "đăng ký" in t or "chứng nhận" in t or "giấy tờ" in t or "bằng lái" in t:
        return "giấy tờ/GPLX"
    if "dừng" in t or "đỗ" in t or "đậu" in t:
        return "dừng/đỗ"
    if "làn" in t or "phần đường" in t or "chuyển hướng" in t or "ngược chiều" in t:
        return "làn/phần đường"
    if "nồng độ" in t or "quá tải" in t or "quá khổ" in t or "chở" in t:
        return "chở hàng/chở người"
    return "khác"


def main():
    rows = list(csv.DictReader(open(GOLD, encoding="utf-8-sig")))
    usable = [r for r in rows
              if r["vehicle_type"] != "không xác định" and r["fine_min"] != ""]
    for r in usable:
        r["behavior_category"] = behavior_category(
            r["behavior_canonical"] + " " + r["behavior_raw"])

    # gom theo loại xe
    buckets = {}
    for r in usable:
        buckets.setdefault(r["vehicle_type"], []).append(r)

    def priority_sort(bucket):
        # ưu tiên có bổ sung/trừ điểm; rồi trải đều theo Điều (round-robin)
        rich = [r for r in bucket if r["additional_penalty"] or r["point_deduction"]]
        rest = [r for r in bucket if not (r["additional_penalty"] or r["point_deduction"])]
        ordered = []
        for group in (rich, rest):
            by_article = {}
            for r in group:
                by_article.setdefault(r["article"], []).append(r)
            # round-robin qua các Điều
            pools = list(by_article.values())
            i = 0
            while any(pools):
                p = pools[i % len(pools)]
                if p:
                    ordered.append(p.pop(0))
                i += 1
                if i > 100000:
                    break
        return ordered

    selected = []
    seen = set()
    for veh, quota in QUOTA.items():
        bucket = priority_sort(buckets.get(veh, []))
        take = 0
        for r in bucket:
            if take >= quota:
                break
            if r["violation_id"] in seen:
                continue
            selected.append(r)
            seen.add(r["violation_id"])
            take += 1

    # nếu chưa đủ TARGET, bù thêm từ phần còn lại (bất kỳ loại xe nào)
    if len(selected) < TARGET:
        for r in usable:
            if len(selected) >= TARGET:
                break
            if r["violation_id"] not in seen:
                selected.append(r); seen.add(r["violation_id"])

    selected = selected[:TARGET]

    cols = list(rows[0].keys()) + ["behavior_category"]
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in selected:
            w.writerow({c: r.get(c, "") for c in cols})

    # thống kê
    from collections import Counter
    print(f"Đã chọn {len(selected)} lỗi -> {OUT}")
    print("Theo loại xe :", dict(Counter(r["vehicle_type"] for r in selected)))
    print("Theo nghị định:", dict(Counter(r["legal_doc"][11:14] for r in selected)))
    print("Theo nhóm hành vi:")
    for k, v in Counter(r["behavior_category"] for r in selected).most_common():
        print(f"   {v:4d}  {k}")


if __name__ == "__main__":
    main()
