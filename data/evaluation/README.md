# Bộ đánh giá (Evaluation) — So sánh LLM thô vs Hệ thống Graph-RAG

Thư mục này chứa **toàn bộ dữ liệu và mã** phục vụ luận điểm khoa học của đồ án:
so sánh hiệu quả giữa **LLM gọi API trực tiếp** và **hệ thống Graph-RAG** trên cùng một
bộ 300 câu hỏi luật giao thông, chấm bằng cùng một tập gold chuẩn hóa.

> Nguồn tri thức: NĐ 100/2019, 123/2021, 168/2024. Entity 100 & 168 dùng bản Gemini
> (tác giả gốc), entity 123 dùng bản **regex** của nhóm (rẻ, tái lập, Precision mức phạt 100%).

## Cấu trúc thư mục

```
data/evaluation/
├── gold/                       # LỚP A — sự thật để chấm
│   ├── violations_gold.csv     #   300 lỗi chuẩn hóa (dựng từ jsonl, $0 API)
│   └── violation_aliases.csv   #   cách nói đời thường (test semantic)
├── test/                       # LỚP B — bộ đo
│   ├── test_questions.csv      #   300 câu hỏi, nối khóa ngoại về gold
│   └── annotation_guideline.md #   quy tắc gán nhãn + Cohen's κ
├── results/                    # KẾT QUẢ chạy (cache 1 lần, không chạy lại)
│   ├── system_A1_results.csv   #   LLM thô #1 (vd Gemini flash, KHÔNG RAG)
│   ├── system_A2_results.csv   #   LLM thô #2 (vd GPT) — "so sánh giữa các LLMs"
│   ├── system_B_results.csv    #   Graph-RAG của nhóm
│   └── comparison_report.csv   #   tổng hợp metric + kiểm định
├── harness/                    # MÃ chạy đánh giá
│   ├── build_gold.py           #   jsonl -> violations_gold.csv
│   ├── gen_questions.py        #   gold -> test_questions.csv (+ review tay)
│   ├── run_systems.py          #   chạy 300 câu qua A1/A2/B, xuất JSON có cấu trúc
│   └── score.py                #   join gold -> metric + McNemar + Wilson CI
└── neo4j_db/                   # (tự sinh) volume dữ liệu Neo4j của Docker
```

## Quyết định kiến trúc: dựng Neo4j, KHÔNG chấm "chay" qua jsonl

**Chọn: dựng Neo4j bằng Docker.** Lý do khoa học (bắt buộc để bảo vệ được):

- System B = **Neo4j vector index + full-text + truy vết đồ thị** (xem `backend/chatbot/bot.py`).
  Nếu chấm "chay" bằng một cách truy xuất tự chế trên jsonl thì **đó không còn là System B** —
  so sánh sẽ vô nghĩa, hội đồng bác ngay. Muốn đo hệ thống thì phải chạy đúng hệ thống.
- Dựng Neo4j **không tốn API**: entity đã trích xuất sẵn; embedding chạy **local** bằng
  `AITeamVN/Vietnamese_Embedding` (SentenceTransformer, CPU, 1024 chiều). Chỉ 1 lần nạp.
- DB này **dùng lại được cho phần demo giao diện** mà đề bài yêu cầu → không phí công.

## Chiến lược tiết kiệm API / token

| Giai đoạn | Chi phí API | Cách tiết kiệm |
|---|---|---|
| Dựng `violations_gold` từ jsonl | **0đ** | thuần Python, không LLM |
| Nạp Neo4j + embedding node | **0đ** | embedding local, entity có sẵn |
| Sinh 300 câu hỏi | ~0đ | template + alias + review tay; nếu cần LLM thì 1 lượt flash |
| Chạy System A (LLM thô) | 1 call/câu | dùng **flash**, temperature 0 |
| Chạy System B (Graph-RAG) | ~2 call/câu | rewrite + generate (đo thật trên code hiện tại) |
| **Chấm điểm** | **0đ** | ép model trả **JSON có cấu trúc** → chấm bằng **join lập trình**, KHÔNG dùng LLM-judge |

Nguyên tắc: **chạy 1 lần, lưu ra CSV, không chạy lại.** Mọi phân tích/biểu đồ đọc từ CSV đã cache.
Ép cả A và B xuất JSON `{violation, fine_min, fine_max, doc, article, clause, point, answer_type}`
→ chấm khách quan bằng so trường, khỏi tốn token cho việc "chấm bằng LLM".

## Độ đo & luận điểm (%)

Chấm **theo từng trường** (không chấm cả câu):
`fine_accuracy`, `legal_basis_accuracy`, `violation_match_accuracy`,
`additional_penalty_accuracy`, `no_data_accuracy`, `clarification_accuracy`,
và **`hallucination_rate`** (chỉ số ăn tiền nhất).

Báo cáo tách theo `question_type` (keyword/semantic/conditional/missing_info/out_of_scope),
kèm **McNemar test** (p-value, so ghép cặp A vs B) và **Wilson CI** (n=300).
Kỳ vọng chứng minh: B ≫ A ở **căn cứ điều luật** và **chống bịa (hallucination)**.

## Lộ trình

```
[ ] 1. docker compose up -d           # dựng Neo4j ($0)
[ ] 2. build_gold.py                  # 3 jsonl -> violations_gold.csv ($0)
[ ] 3. nạp Neo4j + embedding node     # local ($0)
[ ] 4. gen_questions.py + review tay  # 300 câu, đủ 5 nhóm
[ ] 5. run_systems.py                 # A1/A2/B -> results/*.csv (cache)
[ ] 6. score.py                       # metric + McNemar + CI -> comparison_report.csv
```

Xem định hướng đầy đủ ở `../../../TAI_LIEU_DINH_HUONG_300TEST.md`.
