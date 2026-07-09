#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_systems.py — Chạy 300 câu hỏi qua các hệ thống và LƯU KẾT QUẢ TỪNG CÂU MỘT.

Hệ thống hỗ trợ:
  A  = LLM thô (Gemini gọi thẳng, KHÔNG RAG)          -> đại diện "LLM API trực tiếp"
  B  = Graph-RAG của nhóm (backend/chatbot/bot.py)     -> hệ thống của bạn

Tiết kiệm token: dùng model flash; chạy 1 lần, LƯU NGAY mỗi câu (append JSONL).
An toàn: nếu dừng giữa chừng, chạy lại sẽ BỎ QUA các câu đã có -> tiếp tục, không mất tiến độ.
Chấm điểm KHÔNG tốn token: câu trả lời được rút trường (tiền/điều-khoản-điểm/không-biết)
bằng regex chung cho cả A và B (xem score.py).

CÁCH CHẠY (venv backend, có .env với API_KEY):
    python data/evaluation/harness/run_systems.py --systems A B
    python data/evaluation/harness/run_systems.py --systems A          # chỉ LLM thô
    python data/evaluation/harness/run_systems.py --systems B --limit 10  # thử 10 câu
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
os.environ.setdefault("USER_NEO4J", "neo4j")
os.environ.setdefault("PASSWORD_NEO4J", "trafficlaw123")

TEST = REPO / "data/evaluation/test/test_questions.csv"
RESULTS = REPO / "data/evaluation/results"
RESULTS.mkdir(parents=True, exist_ok=True)

# Prompt cho LLM thô: công bằng (cho cơ hội trả lời) nhưng buộc nói rõ khi không chắc,
# để đo được hiện tượng "bịa" (hallucination).
SYSTEM_A_PROMPT = (
    "Bạn là trợ lý pháp luật giao thông đường bộ Việt Nam. "
    "Hãy trả lời câu hỏi sau. Nếu biết, nêu rõ MỨC PHẠT (bằng VND) và CĂN CỨ theo "
    "Điều/Khoản/Điểm của nghị định. Nếu KHÔNG chắc chắn hoặc không có căn cứ pháp lý, "
    "hãy nói rõ \"Tôi không có dữ liệu về vấn đề này\" thay vì đoán. "
    "Nếu câu hỏi thiếu thông tin (ví dụ chưa nói loại phương tiện), hãy hỏi lại cho rõ.\n\n"
    "Câu hỏi: {q}"
)


def load_questions(limit=None):
    import csv
    rows = list(csv.DictReader(open(TEST, encoding="utf-8-sig")))
    return rows[:limit] if limit else rows


def done_ids(path: Path):
    """Câu coi là 'đã xong' để bỏ qua khi resume — NHƯNG record lỗi ([ERROR]) thì
    KHÔNG tính là xong, để lần chạy sau tự retry."""
    ids = set()
    if path.exists():
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                    if not str(r.get("answer", "")).startswith("[ERROR]"):
                        ids.add(r["question_id"])
                except Exception:
                    pass
    return ids


def append(path: Path, record: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()                      # <-- ghi tới đâu lưu tới đó


# ----------------------------- System A: LLM thô -----------------------------
class SystemA:
    name = "A_llm_only"

    def __init__(self):
        import google.generativeai as genai
        from backend.config import API_KEY, MODEL_FLASH
        if not API_KEY:
            raise RuntimeError("Thiếu API_KEY trong .env — cần cho System A.")
        genai.configure(api_key=API_KEY)
        self.model = genai.GenerativeModel(MODEL_FLASH)

    def answer(self, q):
        for attempt in range(3):
            try:
                resp = self.model.generate_content(SYSTEM_A_PROMPT.format(q=q))
                return (resp.text or "").strip()
            except Exception as e:
                if attempt == 2:
                    return f"[ERROR] {e}"
                time.sleep(5 * (attempt + 1))


# --------------------------- System B: Graph-RAG -----------------------------
class SystemB:
    name = "B_graph_rag"

    def __init__(self):
        from backend.chatbot.bot import GraphRAG_Bot
        self.bot = GraphRAG_Bot()

    def answer(self, q):
        try:
            return "".join(self.bot.run_chatbot(q, history=[])).strip()
        except Exception as e:
            return f"[ERROR] {e}"


SYSTEMS = {"A": SystemA, "B": SystemB}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="+", default=["A", "B"], choices=["A", "B"])
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    questions = load_questions(args.limit)

    for key in args.systems:
        sys_obj = SYSTEMS[key]()
        out_path = RESULTS / f"{sys_obj.name}_results.jsonl"
        already = done_ids(out_path)
        todo = [q for q in questions if q["question_id"] not in already]
        print(f"\n=== System {key} ({sys_obj.name}) === đã có {len(already)} câu, "
              f"cần chạy {len(todo)}/{len(questions)}")

        for i, q in enumerate(todo, 1):
            t0 = time.time()
            ans = sys_obj.answer(q["question"])
            rec = {
                "question_id": q["question_id"],
                "system": sys_obj.name,
                "question": q["question"],
                "question_type": q["question_type"],
                "answer": ans,
                "latency_s": round(time.time() - t0, 2),
            }
            append(out_path, rec)                     # LƯU NGAY từng câu
            print(f"  [{i}/{len(todo)}] {q['question_id']} ({rec['latency_s']}s) "
                  f"{q['question'][:50]}...")

        if hasattr(sys_obj, "bot"):
            try:
                sys_obj.bot.close()
            except Exception:
                pass
        print(f"  -> đã lưu: {out_path}")

    print("\nXong. Chạy tiếp: python data/evaluation/harness/score.py")


if __name__ == "__main__":
    main()
