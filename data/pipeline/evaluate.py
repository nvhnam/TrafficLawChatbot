"""
Script đánh giá chất lượng trích xuất thực thể.

Hai cách đánh giá:
1. So sánh nội bộ: Kiểm tra tỷ lệ chunk có entity, phân bổ nhãn, coverage
2. So sánh với dữ liệu tham chiếu: So sánh output của pipeline với JSONL
   đã có từ dự án gốc (NĐ 100, NĐ 168) nếu chạy lại cùng file

Cách dùng:
    python evaluate.py output/entities_cleaned/123-2021nd-cp.jsonl
    python evaluate.py output/entities_cleaned/123-2021nd-cp.jsonl --ref /path/to/reference.jsonl
"""

import json
import os
import sys
import re
import argparse


def load_jsonl(filepath):
    """Đọc file JSONL."""
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def intrinsic_evaluation(data, filepath):
    """
    Đánh giá nội bộ (không cần dữ liệu tham chiếu).

    Kiểm tra:
    - Tỷ lệ chunk có ít nhất 1 entity (coverage)
    - Phân bổ nhãn (label distribution)
    - Tỷ lệ chunk có MONEY_AMOUNT (cho văn bản xử phạt)
    - Tỷ lệ chunk có VIOLATION
    - Tỷ lệ relationship/entity (graph density)
    - Chunks trống (không trích xuất được gì)
    """
    total_chunks = len(data)
    entity_categories = ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]

    # Đếm thống kê
    label_counts = {}
    total_entities = 0
    total_relationships = 0
    chunks_with_entities = 0
    chunks_with_money = 0
    chunks_with_violation = 0
    chunks_with_penalty = 0
    chunks_empty = 0
    money_values = []

    for chunk in data:
        chunk_entities = 0
        has_money = False
        has_violation = False
        has_penalty = False

        for cat in entity_categories:
            for entity in chunk.get(cat, []):
                chunk_entities += 1
                total_entities += 1
                label = entity.get("label", "UNKNOWN")
                label_counts[label] = label_counts.get(label, 0) + 1

                if label == "MONEY_AMOUNT":
                    has_money = True
                    min_val = entity.get("min", 0)
                    max_val = entity.get("max", 0)
                    if max_val > 0:
                        money_values.append({"min": min_val, "max": max_val})
                elif label == "VIOLATION":
                    has_violation = True
                elif label == "PENALTY_MEASURE":
                    has_penalty = True

        rels = len(chunk.get("Relationships", []))
        total_relationships += rels

        if chunk_entities > 0:
            chunks_with_entities += 1
        else:
            chunks_empty += 1

        if has_money:
            chunks_with_money += 1
        if has_violation:
            chunks_with_violation += 1
        if has_penalty:
            chunks_with_penalty += 1

    # Tính các chỉ số
    coverage = chunks_with_entities / total_chunks * 100 if total_chunks > 0 else 0
    density = total_relationships / total_entities if total_entities > 0 else 0
    avg_entities = total_entities / total_chunks if total_chunks > 0 else 0

    # In báo cáo
    print("=" * 60)
    print("BAO CAO DANH GIA CHAT LUONG TRICH XUAT THUC THE")
    print(f"File: {os.path.basename(filepath)}")
    print("=" * 60)

    print(f"\n--- TONG QUAN ---")
    print(f"  Tong chunks:              {total_chunks}")
    print(f"  Tong thuc the:            {total_entities}")
    print(f"  Tong quan he:             {total_relationships}")
    print(f"  Trung binh entity/chunk:  {avg_entities:.1f}")
    print(f"  Mat do do thi (rel/ent):  {density:.2f}")

    print(f"\n--- DO BAO PHU (COVERAGE) ---")
    print(f"  Chunk co entity:          {chunks_with_entities}/{total_chunks} ({coverage:.1f}%)")
    print(f"  Chunk trong:              {chunks_empty}/{total_chunks} ({chunks_empty / total_chunks * 100:.1f}%)")
    print(f"  Chunk co VIOLATION:       {chunks_with_violation}/{total_chunks} ({chunks_with_violation / total_chunks * 100:.1f}%)")
    print(f"  Chunk co MONEY_AMOUNT:    {chunks_with_money}/{total_chunks} ({chunks_with_money / total_chunks * 100:.1f}%)")
    print(f"  Chunk co PENALTY_MEASURE: {chunks_with_penalty}/{total_chunks} ({chunks_with_penalty / total_chunks * 100:.1f}%)")

    print(f"\n--- PHAN BO NHAN ---")
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        pct = count / total_entities * 100 if total_entities > 0 else 0
        bar = "#" * int(pct / 2)
        print(f"  {label:<22} {count:>4} ({pct:>5.1f}%)  {bar}")

    if money_values:
        min_fine = min(m["min"] for m in money_values if m["min"] > 0)
        max_fine = max(m["max"] for m in money_values)
        print(f"\n--- THONG KE MUC PHAT ---")
        print(f"  So luong muc phat:        {len(money_values)}")
        print(f"  Muc phat nho nhat:        {min_fine:>15,} VND")
        print(f"  Muc phat lon nhat:        {max_fine:>15,} VND")

    return {
        "total_chunks": total_chunks,
        "total_entities": total_entities,
        "total_relationships": total_relationships,
        "coverage": coverage,
        "density": density,
        "label_counts": label_counts
    }


def compare_with_reference(our_data, ref_data, our_file, ref_file):
    """
    So sánh output của pipeline với dữ liệu tham chiếu.

    So sánh theo:
    - Tỷ lệ entity mỗi nhãn
    - Trung bình entity/chunk
    - Tỷ lệ relationship/entity
    """
    entity_categories = ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]

    def get_stats(data):
        label_counts = {}
        total_ent = 0
        total_rel = 0
        for chunk in data:
            for cat in entity_categories:
                for entity in chunk.get(cat, []):
                    total_ent += 1
                    label = entity.get("label", "?")
                    label_counts[label] = label_counts.get(label, 0) + 1
            total_rel += len(chunk.get("Relationships", []))
        return {
            "chunks": len(data),
            "entities": total_ent,
            "relationships": total_rel,
            "label_counts": label_counts,
            "avg_ent": total_ent / len(data) if data else 0,
            "density": total_rel / total_ent if total_ent > 0 else 0,
        }

    our_stats = get_stats(our_data)
    ref_stats = get_stats(ref_data)

    print(f"\n{'=' * 60}")
    print(f"SO SANH VOI DU LIEU THAM CHIEU")
    print(f"  Pipeline:    {os.path.basename(our_file)}")
    print(f"  Tham chieu:  {os.path.basename(ref_file)}")
    print(f"{'=' * 60}")

    print(f"\n--- SO SANH TONG QUAN ---")
    print(f"  {'Chi so':<25} {'Pipeline':>10} {'Tham chieu':>12} {'Chenh lech':>12}")
    print(f"  {'-' * 59}")

    metrics = [
        ("Tong chunks", our_stats["chunks"], ref_stats["chunks"]),
        ("Tong thuc the", our_stats["entities"], ref_stats["entities"]),
        ("Tong quan he", our_stats["relationships"], ref_stats["relationships"]),
    ]
    for name, ours, theirs in metrics:
        diff = ours - theirs
        sign = "+" if diff >= 0 else ""
        print(f"  {name:<25} {ours:>10} {theirs:>12} {sign}{diff:>11}")

    print(f"  {'TB entity/chunk':<25} {our_stats['avg_ent']:>10.1f} {ref_stats['avg_ent']:>12.1f}")
    print(f"  {'Mat do (rel/ent)':<25} {our_stats['density']:>10.2f} {ref_stats['density']:>12.2f}")

    # So sánh phân bổ nhãn
    all_labels = sorted(set(list(our_stats["label_counts"].keys()) + list(ref_stats["label_counts"].keys())))
    print(f"\n--- SO SANH PHAN BO NHAN ---")
    print(f"  {'Nhan':<22} {'Pipeline':>10} {'Tham chieu':>12} {'Ti le':>10}")
    print(f"  {'-' * 54}")
    for label in all_labels:
        ours = our_stats["label_counts"].get(label, 0)
        theirs = ref_stats["label_counts"].get(label, 0)
        ratio = ours / theirs * 100 if theirs > 0 else float('inf')
        ratio_str = f"{ratio:.0f}%" if ratio != float('inf') else "moi"
        print(f"  {label:<22} {ours:>10} {theirs:>12} {ratio_str:>10}")


def main():
    parser = argparse.ArgumentParser(
        description="Danh gia chat luong trich xuat thuc the",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_file",
        help="Duong dan toi file JSONL can danh gia"
    )
    parser.add_argument(
        "--ref",
        help="Duong dan toi file JSONL tham chieu (tu du an goc)\n"
             "Vi du: ../data/data_called_entities_best/100.signed.jsonl"
    )

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Loi: Khong tim thay file {args.input_file}")
        sys.exit(1)

    data = load_jsonl(args.input_file)
    stats = intrinsic_evaluation(data, args.input_file)

    if args.ref:
        if not os.path.exists(args.ref):
            print(f"\nLoi: Khong tim thay file tham chieu {args.ref}")
            sys.exit(1)
        ref_data = load_jsonl(args.ref)
        compare_with_reference(data, ref_data, args.input_file, args.ref)

    print(f"\n{'=' * 60}")
    print("HOAN TAT DANH GIA")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
