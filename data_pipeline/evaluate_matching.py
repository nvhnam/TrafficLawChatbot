"""
Đánh giá chất lượng trích xuất bằng Entity Matching.

Thay vì chỉ đếm số lượng, script này so sánh NỘI DUNG thực thể giữa
pipeline regex và Gemini (tham chiếu) theo từng Điều/Khoản/Điểm.

Các chỉ số:
- Precision: Bao nhiêu entity của regex cũng xuất hiện trong Gemini?
  (cao = ít false positive)
- Recall: Bao nhiêu entity của Gemini cũng được regex bắt?
  (cao = ít false negative)  
- F1: Trung bình hài hoà Precision & Recall

Cách dùng:
    python evaluate_matching.py output/entities_cleaned/100.signed.jsonl \\
        --ref ../data/data_called_entities_best/100.signed.jsonl
"""

import json
import re
import os
import sys
import argparse
from difflib import SequenceMatcher


def load_jsonl(filepath):
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def normalize(text):
    """Chuẩn hoá text để so sánh: lowercase, bỏ dấu câu, khoảng trắng thừa."""
    text = text.lower().strip()
    text = re.sub(r'[*#`_\[\]()]', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[;,.]$', '', text)
    return text


def fuzzy_match(text1, text2, threshold=0.6):
    """So sánh 2 đoạn text bằng SequenceMatcher. Trả True nếu >= threshold."""
    if not text1 or not text2:
        return False
    t1 = normalize(text1)
    t2 = normalize(text2)
    # Exact substring match
    if t1 in t2 or t2 in t1:
        return True
    # Fuzzy match
    ratio = SequenceMatcher(None, t1[:200], t2[:200]).ratio()
    return ratio >= threshold


def extract_entities(chunk):
    """Trích tất cả entity từ 1 chunk, trả dict {label: [value_list]}."""
    entities = {}
    for cat in ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]:
        for e in chunk.get(cat, []):
            label = e.get("label", "")
            value = e.get("value", e.get("name", ""))
            if label not in entities:
                entities[label] = []
            entities[label].append(value)
    return entities


def build_chunk_key(meta):
    """Tạo key duy nhất cho mỗi chunk: (dieu, khoan, diem)."""
    return (
        meta.get("dieu", ""),
        meta.get("khoan", ""),
        meta.get("diem", "")
    )


def match_entities_for_label(pipe_values, ref_values, threshold=0.6):
    """
    So khớp danh sách entity values giữa pipeline và reference.
    Trả (matched, precision_denom, recall_denom).
    """
    if not pipe_values and not ref_values:
        return 0, 0, 0

    matched = 0
    ref_matched = set()

    for pv in pipe_values:
        for i, rv in enumerate(ref_values):
            if i not in ref_matched and fuzzy_match(pv, rv, threshold):
                matched += 1
                ref_matched.add(i)
                break

    return matched, len(pipe_values), len(ref_values)


def run_matching_evaluation(pipe_file, ref_file):
    """Chạy đánh giá entity matching."""
    pipe_data = load_jsonl(pipe_file)
    ref_data = load_jsonl(ref_file)

    print("=" * 60)
    print("ĐÁNH GIÁ CHẤT LƯỢNG BẰNG ENTITY MATCHING")
    print(f"  Pipeline: {os.path.basename(pipe_file)}")
    print(f"  Tham chiếu: {os.path.basename(ref_file)}")
    print("=" * 60)

    # Xây dựng index theo (dieu, khoan, diem)
    pipe_index = {}
    for chunk in pipe_data:
        key = build_chunk_key(chunk.get("metadata", {}))
        if key not in pipe_index:
            pipe_index[key] = []
        pipe_index[key].append(chunk)

    ref_index = {}
    for chunk in ref_data:
        key = build_chunk_key(chunk.get("metadata", {}))
        if key not in ref_index:
            ref_index[key] = []
        ref_index[key].append(chunk)

    # Chỉ so sánh các key có trong CẢ HAI
    common_keys = set(pipe_index.keys()) & set(ref_index.keys())
    print(f"\n  Chunk keys chung: {len(common_keys)}")
    print(f"  Chỉ có trong Pipeline: {len(set(pipe_index.keys()) - set(ref_index.keys()))}")
    print(f"  Chỉ có trong Tham chiếu: {len(set(ref_index.keys()) - set(pipe_index.keys()))}")

    # Đánh giá cho từng label
    IMPORTANT_LABELS = [
        "VIOLATION", "MONEY_AMOUNT", "SUBJECT", "PENALTY_MEASURE",
        "OBJECT_EQUIPMENT", "TIME_DURATION", "PROCEDURE_ACTION"
    ]

    label_stats = {}
    for label in IMPORTANT_LABELS:
        label_stats[label] = {"matched": 0, "pipe_total": 0, "ref_total": 0}

    for key in common_keys:
        # Gom entities từ tất cả chunk cùng key
        pipe_entities = {}
        for chunk in pipe_index[key]:
            for label, values in extract_entities(chunk).items():
                if label not in pipe_entities:
                    pipe_entities[label] = []
                pipe_entities[label].extend(values)

        ref_entities = {}
        for chunk in ref_index[key]:
            for label, values in extract_entities(chunk).items():
                if label not in ref_entities:
                    ref_entities[label] = []
                ref_entities[label].extend(values)

        # So khớp từng label
        for label in IMPORTANT_LABELS:
            pv = pipe_entities.get(label, [])
            rv = ref_entities.get(label, [])
            matched, p_total, r_total = match_entities_for_label(pv, rv)
            label_stats[label]["matched"] += matched
            label_stats[label]["pipe_total"] += p_total
            label_stats[label]["ref_total"] += r_total

    # In kết quả
    print(f"\n{'='*60}")
    print(f"{'Nhãn':<22} {'Precision':>10} {'Recall':>10} {'F1':>10}  {'Khớp/Pipe/Ref'}")
    print(f"{'-'*22} {'-'*10} {'-'*10} {'-'*10}  {'-'*20}")

    for label in IMPORTANT_LABELS:
        s = label_stats[label]
        m, pt, rt = s["matched"], s["pipe_total"], s["ref_total"]

        precision = m / pt if pt > 0 else 0
        recall = m / rt if rt > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        print(f"  {label:<20} {precision:>9.1%} {recall:>9.1%} {f1:>9.1%}  ({m}/{pt}/{rt})")

    # Tổng hợp
    total_m = sum(s["matched"] for s in label_stats.values())
    total_p = sum(s["pipe_total"] for s in label_stats.values())
    total_r = sum(s["ref_total"] for s in label_stats.values())
    total_precision = total_m / total_p if total_p > 0 else 0
    total_recall = total_m / total_r if total_r > 0 else 0
    total_f1 = 2 * total_precision * total_recall / (total_precision + total_recall) \
        if (total_precision + total_recall) > 0 else 0

    print(f"{'-'*22} {'-'*10} {'-'*10} {'-'*10}")
    print(f"  {'TỔNG':<20} {total_precision:>9.1%} {total_recall:>9.1%} {total_f1:>9.1%}  ({total_m}/{total_p}/{total_r})")

    print(f"\n{'='*60}")
    print("GIẢI THÍCH:")
    print("  Precision = Regex trích đúng bao nhiêu? (cao = ít nhầm)")
    print("  Recall    = Regex bắt được bao nhiêu so với Gemini? (cao = ít bỏ sót)")
    print("  F1        = Điểm tổng hợp (càng cao càng tốt)")
    print("  Khớp/Pipe/Ref = Số entity khớp / Tổng pipe / Tổng reference")
    print(f"{'='*60}")

    # Spot-check: In vài ví dụ sai
    print(f"\n{'='*60}")
    print("VÍ DỤ SO SÁNH CHI TIẾT (3 chunk ngẫu nhiên)")
    print(f"{'='*60}")

    import random
    sample_keys = random.sample(list(common_keys), min(3, len(common_keys)))

    for key in sample_keys:
        dieu, khoan, diem = key
        loc = f"Điều {dieu}" + (f", Khoản {khoan}" if khoan else "") + (f", Điểm {diem}" if diem else "")
        print(f"\n--- {loc} ---")

        pipe_entities = {}
        for chunk in pipe_index[key]:
            for label, values in extract_entities(chunk).items():
                if label not in pipe_entities:
                    pipe_entities[label] = []
                pipe_entities[label].extend(values)

        ref_entities = {}
        for chunk in ref_index[key]:
            for label, values in extract_entities(chunk).items():
                if label not in ref_entities:
                    ref_entities[label] = []
                ref_entities[label].extend(values)

        for label in ["VIOLATION", "MONEY_AMOUNT", "SUBJECT"]:
            pv = pipe_entities.get(label, [])
            rv = ref_entities.get(label, [])
            if pv or rv:
                print(f"  {label}:")
                for v in pv[:2]:
                    print(f"    [Regex]  {v[:80]}")
                for v in rv[:2]:
                    print(f"    [Gemini] {v[:80]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đánh giá entity matching")
    parser.add_argument("pipeline_file", help="File JSONL pipeline")
    parser.add_argument("--ref", required=True, help="File JSONL tham chiếu (Gemini)")
    args = parser.parse_args()

    run_matching_evaluation(args.pipeline_file, args.ref)
