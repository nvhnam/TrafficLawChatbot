# Backend – Vietnam Road Traffic Law Chatbot

Tài liệu này mô tả chi tiết **pipeline xử lý dữ liệu (ingestion pipeline)**, cơ chế **embedding**, và **cấu trúc tổ chức lưu trữ** (Neo4j Graph Database và Vector Database) của hệ thống backend. Toàn bộ nội dung được kiểm chứng trực tiếp trên source code hiện có trong thư mục `backend/`, không suy đoán.

> Hệ thống là một **Legal Graph-RAG** (Retrieval-Augmented Generation trên nền đồ thị tri thức): dữ liệu pháp luật giao thông (Nghị định, Luật, Thông tư...) được số hoá thành một **property graph** trong Neo4j, kết hợp **vector search** + **full-text search** + **truy vết quan hệ đồ thị** để trả lời câu hỏi của người dùng bằng LLM (Gemini) với ngữ cảnh trích dẫn chính xác từ database, hạn chế tối đa hiện tượng "ảo giác" (hallucination).

---

## Mục lục

1. [Kiến trúc tổng quan](#1-kiến-trúc-tổng-quan)
2. [Pipeline nạp dữ liệu (Ingestion Pipeline) — chi tiết từng bước](#2-pipeline-nạp-dữ-liệu-ingestion-pipeline--chi-tiết-từng-bước)
3. [Embedding — mô hình, cách sinh vector, nơi lưu trữ](#3-embedding--mô-hình-cách-sinh-vector-nơi-lưu-trữ)
4. [Cấu trúc tổ chức trong Neo4j (Graph Database)](#4-cấu-trúc-tổ-chức-trong-neo4j-graph-database)
5. [Cấu trúc tổ chức trong Vector Database](#5-cấu-trúc-tổ-chức-trong-vector-database)
6. [Từ mô hình khái niệm "ViolationRecord" sang Property Graph thực tế](#6-từ-mô-hình-khái-niệm-violationrecord-sang-property-graph-thực-tế)
7. [Luồng truy vấn thời gian thực (Query-time RAG)](#7-luồng-truy-vấn-thời-gian-thực-query-time-rag)
8. [Khả năng chịu lỗi & resume khi gián đoạn](#8-khả-năng-chịu-lỗi--resume-khi-gián-đoạn)
9. [Cấu hình & biến môi trường](#9-cấu-hình--biến-môi-trường)

---

## 1. Kiến trúc tổng quan

```
                 ┌────────────────────────────────────────────────────────────┐
                 │                   INGESTION PIPELINE (offline)              │
  PDF upload ──▶ │ OCR/Markdown ─▶ Chunking ─▶ Entity/Relation Extraction ─▶   │
                 │  Data Cleaning ─▶ Upload Neo4j ─▶ Post-processing/Embedding │
                 └────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │   Neo4j Graph DB       │
                              │  (Property Graph +     │
                              │   Native Vector Index + │
                              │   Full-text Index)      │
                              └───────────────────────┘
                                          ▲
                                          │  Hybrid Search (vector + full-text + graph traversal)
                 ┌────────────────────────┴─────────────────────────┐
  User question ▶│           QUERY-TIME RAG (online, per request)    │▶ Streaming answer (Gemini)
                 └─────────────────────────────────────────────────┘
```

Backend là một ứng dụng **Flask** (`backend/main.py` khởi động app qua `backend/api/__init__.py`, các route được tổ chức theo Blueprint trong `backend/api/blueprints/`: `ingest.py`, `chat.py`, `documents.py`, `ocr_bp.py`). Toàn bộ dữ liệu tri thức được lưu **tập trung trong một Neo4j duy nhất** — hệ thống **không dùng vector database rời** (không có FAISS/Chroma/Pinecone/Qdrant...); vector search được thực hiện bằng **tính năng Vector Index gốc (native) của Neo4j**.

### Thư mục quan trọng

| Thư mục | Vai trò |
|---|---|
| `api/blueprints/` | Các REST endpoint (upload file, chat, quản lý tài liệu, OCR) |
| `ingestion/` | Orchestrator nạp dữ liệu: OCR→Markdown, trích xuất thực thể, upload Neo4j |
| `chunking/` | Bộ chia nhỏ văn bản luật theo cấu trúc Điều/Khoản/Điểm |
| `data_processing/` | Làm sạch dữ liệu, sinh embedding, xây quan hệ liên văn bản |
| `markdown_converter/`, `ocr/` | Engine OCR cục bộ (Docling + YOLOv8 + CRNN tuỳ biến cho tiếng Việt) |
| `core/` | Model embedding dùng chung, cơ chế fallback Gemini, dependency container |
| `chatbot/` | Logic RAG thời gian thực (truy vấn đồ thị + sinh câu trả lời) |
| `config.py`, `config.yaml` | Cấu hình model, Neo4j, prompt trích xuất, cờ bật/tắt pipeline local |

---

## 2. Pipeline nạp dữ liệu (Ingestion Pipeline) — chi tiết từng bước

Điểm vào: `POST /process_folder_and_build` (`api/blueprints/ingest.py`) → `DataProcessorGraphRAG.process_file()` (`ingestion/data_processor.py`).

### Bước 0 — Định danh file (content-hash)

Mỗi file upload được băm bằng **SHA-256** trên toàn bộ nội dung byte để tạo `doc_uuid` (`ingest.py`):

```python
doc_uuid = hashlib.sha256(file_bytes).hexdigest()[:32]
```

Vì `doc_uuid` phụ thuộc **nội dung** (không phải ngẫu nhiên), upload lại đúng file cũ luôn cho ra cùng `doc_uuid` → cùng thư mục workspace tạm (`folder_check/temp_workspace/{doc_uuid}/`) → là nền tảng cho cơ chế **resume** (xem mục 8).

### Bước 1 — OCR / Chuyển PDF sang Markdown

Hai lựa chọn, chọn bằng cờ cấu hình `ingestion.use_local_ocr` trong `config.yaml`:

- **Local (mặc định, khuyến nghị)** — `markdown_converter/doc_processor.py::DocProcessor`: dùng **IBM Docling** làm pipeline OCR, nhưng **thay thế model OCR mặc định** bằng bộ đôi tự huấn luyện cho tiếng Việt:
  - `ocr/detector_text/` — **YOLOv8** phát hiện vùng chứa chữ (text detection).
  - `ocr/ocr_text/` — **CRNN** (Convolutional Recurrent Neural Network) nhận dạng ký tự (text recognition), trọng số tại `weight/weight_detect_text/*.pt` và `weight/weight_ocr_text/*.pth`.
  - Sau OCR, một chuỗi hàm `clean_vietnamese_markdown()` dọn rác đặc thù (số trang lạc, danh sách bị OCR sai định dạng, tiêu đề "Điều" bị lệch...).
  - Chạy hoàn toàn trên **CPU**, không tốn token API, nhưng chậm hơn (~30 giây/trang theo đo đạc thực tế).
- **Gemini (dự phòng)** — `ingestion/convert_markdown.py::PdfToMarkdownConverter`: cắt PDF thành từng lô 3 trang, gửi trực tiếp file PDF (bytes) tới Gemini multimodal API kèm prompt "chuyên gia số hóa văn bản pháp luật" để chuyển thành Markdown chuẩn.

Cả hai lớp đều expose cùng interface `process_content(pdf_bytes, output_file_path, chunk_size)` nên `DataProcessorGraphRAG` có thể hoán đổi qua lại mà không ảnh hưởng các bước sau.

### Bước 2 — Chunking (phân đoạn theo cấu trúc pháp lý)

`chunking/legal_splitter.py::LegalSemanticSplitter` dùng **regex thuần**, không gọi LLM, để tách Markdown thành các "chunk" bám theo cấu trúc văn bản luật Việt Nam:

- Phân cấp: `Phần` → `Chương` → `Mục` → `Điều` → `Khoản` → `Điểm`.
- Mỗi chunk **lá** (thường ở cấp Điểm hoặc Khoản) luôn được lặp lại tiêu đề "Điều N. Tên điều" ở đầu nội dung, để đảm bảo mỗi đoạn văn bản độc lập vẫn giữ đủ ngữ cảnh khi tìm kiếm vector.
- Phụ lục (bảng biểu mức phạt, hạn mức tốc độ...) được nhận diện và tách riêng thành `APPENDIX_TEXT` / `APPENDIX_TABLE`.
- Mỗi chunk có `metadata`:

```python
{
  "document": "168-nd-cp.signed",     # tên file gốc, sẽ được DataCleaner chuẩn hoá lại
  "phan": None, "chuong": "...", "muc": None,
  "dieu": "6", "khoan": "1", "diem": "a",
  "type": "LEGAL_RULE",               # hoặc ACTION_BLOCK / PREAMBLE / APPENDIX_TEXT / APPENDIX_TABLE
  "chunk_uuid": "3f9a1c..."           # UUID ổn định cho chunk, dùng làm khoá node Chunk trong Neo4j
}
```

### Bước 3 — Trích xuất Thực thể & Quan hệ (Entity/Relation Extraction)

Chọn bằng cờ `ingestion.use_local_extraction`:

- **Local (mặc định)** — `ingestion/get_entities_local.py::GetEntitiesLocal`: dùng **regex có kế thừa ngữ cảnh phân cấp** (không gọi LLM). Trích SUBJECT từ tiêu đề Điều rồi kế thừa xuống mọi chunk con của Điều đó; trích MONEY_AMOUNT từ đầu Khoản rồi kế thừa xuống các Điểm không có mức phạt riêng. Chỉ tạo ra **10 nhãn**: `SUBJECT, MONEY_AMOUNT, VIOLATION, PENALTY_MEASURE, PROCEDURE_ACTION, TIME_DURATION, POINT_DEDUCTION, OBJECT_EQUIPMENT, DOCUMENT_RECORD, LEGAL_CONCEPT`.
- **Gemini (dự phòng)** — `ingestion/get_entities_gemini.py::GetEntitiesByGemini`: gọi Gemini **một lần cho mỗi chunk** với prompt cấu trúc hoá (`config.py::PROMPT_EXTRACT_ENTITIES`), có thể trả về đầy đủ **17 nhãn** (gồm cả `DEFINITION`, `RIGHT_OBLIGATION`, `PROHIBITED_EXCLUDED`, `STANDARD_CONDITION`, `PERCENTAGE` mà bản local không có).

Kết quả mỗi chunk có cấu trúc JSON **3 tầng thực thể + 1 danh sách quan hệ** (đây là "hợp đồng dữ liệu" xuyên suốt toàn bộ pipeline, được `upload2neo4j.py` đọc trực tiếp):

```json
{
  "Level_3_Foundations":   [ {"id": "e1", "label": "SUBJECT", "name": "...", "value": "..."} ],
  "Level_2_Rules_Actions": [ {"id": "e2", "label": "VIOLATION", "name": "...", "value": "..."} ],
  "Attributes_Measures":   [ {"id": "e3", "label": "MONEY_AMOUNT", "name": "...", "value": "...", "min": 400000, "max": 600000} ],
  "Relationships":         [ {"source": "e1", "type": "COMMITS", "target": "e2"},
                              {"source": "e2", "type": "HAS_MONEY_AMOUNT", "target": "e3"} ],
  "metadata": { ... },          // metadata của chunk (xem Bước 2)
  "original_content": "..."     // văn bản gốc của chunk
}
```

Bảng quan hệ (edge type) do tầng trích xuất sinh ra:

| Edge | Chiều | Ý nghĩa |
|---|---|---|
| `COMMITS` | SUBJECT → VIOLATION | Chủ thể thực hiện hành vi vi phạm |
| `HAS_MONEY_AMOUNT` | VIOLATION → MONEY_AMOUNT | Hành vi tương ứng mức phạt tiền |
| `HAS_PENALTY` | VIOLATION → PENALTY_MEASURE | Hành vi tương ứng hình phạt bổ sung (tước GPLX, tịch thu, đình chỉ...) |
| `DEDUCTS_POINT` | VIOLATION → POINT_DEDUCTION | Hành vi bị trừ điểm giấy phép lái xe |
| `APPLIES_TO_OBJECT` | VIOLATION → OBJECT_EQUIPMENT | Hành vi liên quan tới thiết bị/giấy tờ cụ thể |
| `HAS_DURATION` | PENALTY_MEASURE → TIME_DURATION | Thời hạn áp dụng hình phạt bổ sung |

### Bước 4 — Làm sạch & Chuẩn hoá dữ liệu (`data_processing/data_cleaner.py::DataCleaner`)

Chạy tuần tự 5 bước xử lý trên **toàn bộ danh sách chunk đã trích xuất** (không cần LLM, thuần regex/heuristic):

1. **`clean_document_name`** — Tự động dò tên định danh chuẩn của văn bản (vd `"Nghị định số 168/2024/NĐ-CP"`) từ phần mở đầu văn bản, thay thế các cụm chỉ định mơ hồ trong nội dung thực thể như *"Nghị định này"*, *"Điều này"*, *"khoản này"* bằng tên/số hiệu Điều-Khoản tuyệt đối; gán lại `chunk_id` tuần tự toàn cục.
2. **`resolve_amendment_context`** — Với các đoạn có từ khoá *"sửa đổi/bãi bỏ/thay thế"*, xác định văn bản **mục tiêu** đang bị sửa đổi (khác văn bản gốc) và gắn lại ngữ cảnh đó vào các thực thể `DOCUMENT_RECORD` liên quan.
3. **`refine_graph_schema`** — Bổ sung ngữ cảnh loại phương tiện (ô tô / mô tô, xe máy / xe đạp, xe thô sơ / xe máy chuyên dùng / xe ưu tiên) vào `SUBJECT.value` dựa trên từ khoá xuất hiện trong chunk; tái phân loại `DOCUMENT_RECORD` thành `PHYSICAL_DOCUMENT` nếu nội dung thực chất là giấy tờ vật lý (GPLX, đăng ký xe...).
4. **`extract_legal_hierarchy`** — Đọc phần "Căn cứ ..." ở đầu văn bản để dựng quan hệ `BASES_ON` giữa văn bản hiện tại và các văn bản pháp lý làm căn cứ ban hành.
5. **`link_isolated_islands`** — Với các câu tham chiếu chéo dạng *"vi phạm quy định tại điểm a, b khoản 2 Điều 5"*, tra ngược lại nội dung VIOLATION thật sự tại đúng Điều/Khoản/Điểm đó và nối thẳng vào giá trị thực thể, tránh tạo "đảo cô lập" (node không có ngữ nghĩa đầy đủ) trong đồ thị.

### Bước 5 — Nạp lên Neo4j (`ingestion/upload2neo4j.py::Neo4jUploader`)

Xem chi tiết cấu trúc ở mục 4. Tóm tắt luồng: với mỗi chunk, `MERGE` (tạo nếu chưa có) chuỗi node phân cấp `Document → Article → Clause → Point`, sau đó `MERGE` node `Chunk` gắn vào node phân cấp thấp nhất tương ứng, cuối cùng `MERGE` từng thực thể và quan hệ đã trích xuất, liên kết thực thể với chunk qua quan hệ `MENTIONED_IN`.

### Bước 6 — Hậu xử lý (`ingestion/post_processor.py::Neo4jPostProcessor.run_all()`)

Chạy tuần tự sau khi **toàn bộ** file trong lượt upload đã được nạp xong:

1. `DocumentEdgesBuilder.extract_and_link_relationships()` (`data_processing/build_edges.py`) — với các Chunk có chứa từ khoá sửa đổi/bãi bỏ **và chưa được xử lý** (`c.is_rel_extracted IS NULL`), gọi Gemini để trích quan hệ **liên văn bản** (`BAI_BO`, `SUA_DOI`, `THAY_THE`, `HUONG_DAN`) giữa các node `Document`, rồi đánh dấu `is_rel_extracted = true` để không xử lý lại.
2. `VectorEmbeddingBuilder.run_embedding_process()` — sinh embedding cho từng `Chunk` (xem mục 3).
3. `NodeEmbeddingBuilder.run_embedding_node()` — sinh embedding cho các node thực thể quan trọng và tạo Vector Index tương ứng (xem mục 5).

---

## 3. Embedding — mô hình, cách sinh vector, nơi lưu trữ

### Mô hình

- **Model:** [`AITeamVN/Vietnamese_Embedding`](https://huggingface.co/AITeamVN/Vietnamese_Embedding) — mô hình embedding tiếng Việt, tải qua thư viện `sentence-transformers`.
- **Nạp model:** `core/embedding.py::get_embedding_model()` — dùng `ServiceContainer` (singleton, chỉ nạp model **một lần** cho toàn app) và **ưu tiên nạp từ cache cục bộ** (`local_files_only=True`, không gọi mạng); chỉ fallback sang tải online nếu cache cục bộ chưa có.
- **Thiết bị:** CPU (`device="cpu"`).
- **Số chiều vector (dimension):** **1024** — được cấu hình cứng khi tạo `chunk_vector_index` (`upload2neo4j.py`) và được xác nhận động qua `model.get_sentence_embedding_dimension()` khi tạo các index thực thể khác (`build_embedding_node.py`).
- **Chuẩn hoá:** mọi lệnh `model.encode(...)` trong hệ thống đều dùng `normalize_embeddings=True` → vector đã chuẩn hoá L2, phù hợp để so khớp bằng **cosine similarity**.

### Nơi sinh embedding & tần suất gọi

Không có bước embedding nào gọi Gemini — **100% cục bộ, không tốn token API cho embedding**. Có 2 tiến trình sinh embedding, đều chạy **sau khi** dữ liệu đã nằm trong Neo4j (không sinh embedding ở tầng JSON trung gian):

| Tiến trình | File | Đối tượng embed | Trường nguồn | Batch size |
|---|---|---|---|---|
| `VectorEmbeddingBuilder.run_embedding_process()` | `data_processing/build_vector_embeddings.py` | Node `Chunk` | `Chunk.content` | 4 |
| `NodeEmbeddingBuilder.run_embedding_node()` | `data_processing/build_embedding_node.py` | Node `VIOLATION`, `SUBJECT`, `PROHIBITED_EXCLUDED`, `LEGAL_CONCEPT`, `Document`, `Article`, `Clause`, `Point`, `Chunk` | `value` (thực thể) hoặc `name`/`content` (node phân cấp) | 1 |

**Đặc điểm quan trọng — tự phục hồi khi gián đoạn (idempotent):** cả hai truy vấn Cypher lấy dữ liệu cần embed đều lọc `WHERE ... embedding IS NULL`, và ghi kết quả `SET n.embedding = ...` ngay sau mỗi batch nhỏ. Vì vậy nếu tiến trình bị dừng giữa chừng (tắt máy, lỗi mạng...), chỉ cần gọi lại `run_embedding_process()` / `run_embedding_node()` — hệ thống tự động bỏ qua các node đã có `embedding` và tiếp tục đúng chỗ dừng, **không cần file checkpoint riêng** vì bản thân Neo4j đóng vai trò checkpoint.

### Lưu trữ vector ở đâu?

Vector **không được lưu ở một kho dữ liệu riêng** — nó được ghi **trực tiếp làm một property** trên chính node Neo4j:

```
(c:Chunk {id: "...", content: "...", embedding: [0.0123, -0.0456, ...]})   // 1024 số thực
(v:VIOLATION {id_name: "...", value: "...", embedding: [...]})
```

Việc tìm kiếm theo vector được thực hiện bằng **Neo4j Vector Index** (mục 5) — không cần đồng bộ dữ liệu giữa hai hệ thống như kiến trúc vector-DB-tách-rời truyền thống (Chroma/Pinecone/FAISS...).

---

## 4. Cấu trúc tổ chức trong Neo4j (Graph Database)

Schema được khởi tạo trong `Neo4jUploader.create_schema_templates()` (constraint) và `NodeEmbeddingBuilder.create_vector_index()` (vector index). Đây là một **property graph**, không phải bảng quan hệ — không có "bảng ViolationRecord" đơn lẻ nào, mà là một VIOLATION-node được bao quanh bởi các node liên quan qua nhiều cạnh (xem mục 6 để đối chiếu trực quan).

### 4.1. Node "khung xương" (Document Hierarchy)

| Label | Property | Nguồn/Ý nghĩa |
|---|---|---|
| `Document` | `id` (khoá, = tên văn bản viết thường) | `name` (tên đầy đủ, vd *"Nghị định số 168/2024/NĐ-CP"*), `type` (loại chunk gốc, ít dùng), `year` (năm ban hành, trích bằng regex 4 chữ số từ tên) |
| `Article` (Điều) | `id` = `"điều {n} của {document}"` (thường hoá) | `name` |
| `Clause` (Khoản) | `id` = `"khoản {n} {article_name}"` | `name` |
| `Point` (Điểm) | `id` = `"điểm {x} {clause_name}"` | `name` |
| `Chunk` | `id` = `chunk_uuid` (ổn định, gán từ bước Chunking) | `content` (nội dung gốc dùng để trả lời), `name` (đường dẫn đọc được, vd `"[Điểm a Khoản 1 Điều 6 - Nghị định số 168/2024/NĐ-CP]"`), `metadata_document`, `metadata_dieu`, `metadata_khoan`, `metadata_diem` (lưu phẳng ngay trên Chunk để truy vấn nhanh, không cần join), `embedding` (vector 1024 chiều, gán ở bước hậu xử lý) |

Quan hệ phân cấp (một chiều, từ cha xuống con), tạo bằng `MERGE ... ON CREATE`:

```
(Document)-[:HAS_ARTICLE]->(Article)-[:HAS_CLAUSE]->(Clause)-[:HAS_POINT]->(Point)-[:HAS_CHUNK]->(Chunk)
```

> Lưu ý: nếu một Điều không có Khoản (văn bản đơn giản), Chunk sẽ gắn thẳng vào `Article` qua `HAS_CHUNK`; tương tự nếu Khoản không chia Điểm, Chunk gắn thẳng vào `Clause`. Cấp thấp nhất tồn tại luôn là điểm neo (`lowest_parent_label`) cho Chunk.

Ràng buộc: `CREATE CONSTRAINT ... FOR (n:{Document|Article|Clause|Point|Chunk}) REQUIRE n.id IS UNIQUE`.

### 4.2. Node thực thể pháp lý (Entity nodes)

17 nhãn khả dụng (định nghĩa trong `Neo4jUploader.entity_labels`), cộng nhãn dự phòng `UNKNOWN` cho các nhãn lạ không nằm trong danh sách:

```
SUBJECT, LEGAL_CONCEPT, DEFINITION, RIGHT_OBLIGATION, PROHIBITED_EXCLUDED,
VIOLATION, PENALTY_MEASURE, PROCEDURE_ACTION, STANDARD_CONDITION, MONEY_AMOUNT,
POINT_DEDUCTION, OBJECT_EQUIPMENT, DOCUMENT_RECORD, PHYSICAL_DOCUMENT,
TIME_DURATION, PERCENTAGE, TEXT_SEGMENT
```

*(Với pipeline **local** mặc định, chỉ 10 nhãn đầu — `SUBJECT, MONEY_AMOUNT, VIOLATION, PENALTY_MEASURE, PROCEDURE_ACTION, TIME_DURATION, POINT_DEDUCTION, OBJECT_EQUIPMENT, DOCUMENT_RECORD, LEGAL_CONCEPT` — thực sự được sinh ra; `PHYSICAL_DOCUMENT`/`TEXT_SEGMENT` do bước Data Cleaning tái phân loại; `DEFINITION, RIGHT_OBLIGATION, PROHIBITED_EXCLUDED, STANDARD_CONDITION, PERCENTAGE` chỉ xuất hiện khi dùng pipeline Gemini.)*

Property chung cho mọi node thực thể:

| Property | Ý nghĩa |
|---|---|
| `id_name` (**khoá duy nhất toàn cục**) | = `name` (hoặc `value` nếu thiếu `name`) viết thường, giới hạn 1000 ký tự. Đây chính là cơ chế **khử trùng lặp thực thể toàn hệ thống**: hai chunk khác nhau nhắc tới cùng một khái niệm (vd cùng nói "người điều khiển xe ô tô") sẽ `MERGE` vào **đúng một node**, biến nhiều văn bản rời rạc thành một mạng lưới liên kết. |
| `name` | Tên rút gọn, dùng làm nhãn hiển thị / định danh vector search |
| `value` | **Nguyên văn** đoạn luật gốc (không tóm tắt) |
| `min`, `max` | Chỉ có ý nghĩa với `MONEY_AMOUNT` (đơn vị VNĐ, kiểu Integer) |
| `embedding` | Chỉ có ở 4 nhãn được embed riêng (xem mục 5) |

Ràng buộc: `CREATE CONSTRAINT ... FOR (n:{label}) REQUIRE n.id_name IS UNIQUE`.

Quan hệ nối thực thể vào chunk chứa nó:

```
(entity)-[:MENTIONED_IN]->(Chunk)
```

Quan hệ **giữa các thực thể với nhau** — được tạo động theo đúng nhãn `type` mà tầng trích xuất sinh ra (không giới hạn danh sách cố định, xem bảng ở mục 2 Bước 3), ví dụ:

```
(SUBJECT)-[:COMMITS]->(VIOLATION)-[:HAS_MONEY_AMOUNT]->(MONEY_AMOUNT)
(VIOLATION)-[:HAS_PENALTY]->(PENALTY_MEASURE)-[:HAS_DURATION]->(TIME_DURATION)
(VIOLATION)-[:DEDUCTS_POINT]->(POINT_DEDUCTION)
(VIOLATION)-[:APPLIES_TO_OBJECT]->(OBJECT_EQUIPMENT)
(DOCUMENT_RECORD)-[:BASES_ON]->(DOCUMENT_RECORD)          // do DataCleaner sinh, cấp văn bản
```

### 4.3. Quan hệ liên văn bản (cross-document)

Sinh bởi `build_edges.py` ở bước hậu xử lý, cấp độ **Document ↔ Document** (không phải Chunk hay Entity):

```
(Document)-[:BAI_BO]->(Document)      // bãi bỏ
(Document)-[:SUA_DOI]->(Document)     // sửa đổi
(Document)-[:THAY_THE]->(Document)    // thay thế
(Document)-[:HUONG_DAN]->(Document)   // hướng dẫn thi hành
```

> Trong Cypher truy vấn thời gian thực (`cypher_query`, mục 7), hệ thống còn tham chiếu quan hệ `AMENDS`/`REPEALS` giữa các node `DOCUMENT_RECORD` (không phải giữa `Document`) để cảnh báo "quy định đã bị sửa đổi/bãi bỏ" ngay trong câu trả lời — quan hệ này xuất phát từ nhãn tiếng Anh gán thủ công trong dữ liệu mẫu ban đầu hoặc do LLM sinh ra khi trích xuất (tên loại quan hệ do LLM tự đặt theo prompt, không được chuẩn hoá cứng bằng code).

### 4.4. Index & Constraint — tổng hợp

| Loại | Tên | Trên | Ghi chú |
|---|---|---|---|
| Uniqueness Constraint | (tự sinh) | `Document/Article/Clause/Point/Chunk.id` | |
| Uniqueness Constraint | (tự sinh) | `{EntityLabel}.id_name` (17 nhãn) | |
| Full-text Index | `chunk_content_index` | `Chunk.content` | Dùng Lucene, phục vụ tìm kiếm từ khoá (BM25-style) |
| Vector Index | `chunk_vector_index` | `Chunk.embedding` | 1024 chiều, cosine |
| Vector Index | `{label}_vector_index` (vd `violation_vector_index`, `subject_vector_index`...) | Xem mục 5 | |

---

## 5. Cấu trúc tổ chức trong Vector Database

**Không tồn tại vector database độc lập.** Toàn bộ tính năng vector search dùng **Neo4j Vector Index** (native, có từ Neo4j 5.x) — vector là property trên node, index được Neo4j quản lý nội bộ (HNSW).

### Danh sách Vector Index thực tế được tạo

| Index | Node label | Property vector | Trường văn bản nguồn | Tạo bởi |
|---|---|---|---|---|
| `chunk_vector_index` | `Chunk` | `embedding` | `content` | `Neo4jUploader.create_schema_templates()` + `VectorEmbeddingBuilder` |
| `violation_vector_index` | `VIOLATION` | `embedding` | `value` | `NodeEmbeddingBuilder` |
| `subject_vector_index` | `SUBJECT` | `embedding` | `value` | `NodeEmbeddingBuilder` |
| `prohibited_excluded_vector_index` | `PROHIBITED_EXCLUDED` | `embedding` | `value` | `NodeEmbeddingBuilder` |
| `legal_concept_vector_index` | `LEGAL_CONCEPT` | `embedding` | `value` | `NodeEmbeddingBuilder` |
| `document_vector_index` | `Document` | `embedding` | `name` | `NodeEmbeddingBuilder` |
| `article_vector_index` | `Article` | `embedding` | `name` | `NodeEmbeddingBuilder` |
| `clause_vector_index` | `Clause` | `embedding` | `name` | `NodeEmbeddingBuilder` |
| `point_vector_index` | `Point` | `embedding` | `name` | `NodeEmbeddingBuilder` |

Cấu hình mỗi index: `vector.dimensions = 1024`, `vector.similarity_function = 'cosine'`.

> **Lưu ý quan trọng — không phải mọi nhãn thực thể đều tìm được bằng vector.** Các nhãn `MONEY_AMOUNT, PENALTY_MEASURE, POINT_DEDUCTION, OBJECT_EQUIPMENT, DOCUMENT_RECORD, PHYSICAL_DOCUMENT, TIME_DURATION, PERCENTAGE, TEXT_SEGMENT, DEFINITION, RIGHT_OBLIGATION, PROCEDURE_ACTION, STANDARD_CONDITION` **không** nằm trong `NodeEmbeddingBuilder.schema` nên **không có embedding riêng và không có vector index**. Các node này chỉ được truy xuất gián tiếp thông qua **truy vết quan hệ đồ thị** (`MENTIONED_IN`, `HAS_MONEY_AMOUNT`, `HAS_PENALTY`...) xuất phát từ một `Chunk`/`VIOLATION`/`SUBJECT` đã được tìm thấy bằng vector/full-text search trước đó — đây chính là điểm khác biệt cốt lõi giữa **Graph-RAG** và **Vector-RAG thuần tuý**: không phải mọi thông tin cần tìm bằng vector, mà nhiều thông tin được "kéo theo" qua cạnh đồ thị.

---

## 6. Từ mô hình khái niệm "ViolationRecord" sang Property Graph thực tế

Nếu mô hình hoá theo kiểu bảng phẳng (relational) như dưới đây:

```
ViolationRecord {
  id:                 UUID
  description:        String          // mô tả tự nhiên
  canonical_text:      String          // văn bản pháp lý gốc
  vehicle_type:        Enum            // ô tô | xe máy | xe đạp | xe tải | ...
  violation_type:      Enum            // tốc độ | nồng độ cồn | đèn hiệu | ...
  fine_min:            Integer (VNĐ)
  fine_max:            Integer (VNĐ)
  additional_penalty:  String[]        // tước GPLX, trừ điểm, tạm giữ xe...
  legal_basis:         LegalReference  // Điều X, Khoản Y, Nghị định Z
  decree_version:      String          // "168/2024"
}
```

thì hệ thống **không lưu một bản ghi phẳng như vậy** — thay vào đó, mỗi trường được **phân rã thành node/quan hệ riêng** trong property graph. Bảng đối chiếu:

| Trường trong `ViolationRecord` | Đại diện thực tế trong hệ thống |
|---|---|
| `id` | `VIOLATION.id_name` — khoá dedupe toàn cục (không phải UUID ngẫu nhiên, mà là hash/chuẩn hoá của `name`), dùng để `MERGE` các lần nhắc tới cùng một hành vi thành một node duy nhất |
| `description` | `VIOLATION.name` (bản rút gọn, dùng cho hiển thị & vector search) |
| `canonical_text` | `VIOLATION.value` (nguyên văn luật, không tóm tắt — đúng quy tắc "BÁM SÁT NGUYÊN VĂN" trong prompt trích xuất) |
| `vehicle_type` (Enum) | **Không có trường Enum riêng.** Được nhúng như hậu tố ngữ cảnh trong `SUBJECT.value` (vd *"người điều khiển xe (ô tô)"*, *"...(mô tô, xe máy)"*, *"...(xe đạp, xe thô sơ)"*), do `DataCleaner.refine_graph_schema()` gắn vào dựa trên từ khoá xuất hiện trong chunk |
| `violation_type` (Enum) | **Không có Enum riêng.** Toàn bộ VIOLATION dùng chung 1 nhãn `VIOLATION`; loại vi phạm (tốc độ, nồng độ cồn...) nằm trong nội dung text `value`/`name` và có thể lọc bằng full-text search hoặc suy ra từ Điều/Chương cha |
| `fine_min` / `fine_max` | **Không nằm trên node VIOLATION.** Là node `MONEY_AMOUNT` riêng biệt, có property `min`/`max` (Integer, VNĐ), nối vào VIOLATION qua `(VIOLATION)-[:HAS_MONEY_AMOUNT]->(MONEY_AMOUNT)` |
| `additional_penalty` (mảng string) | Không phải 1 mảng trên cùng node, mà là **các node riêng** `PENALTY_MEASURE` (tước GPLX, tịch thu, đình chỉ...) và `POINT_DEDUCTION` (trừ điểm), nối qua `(VIOLATION)-[:HAS_PENALTY]->(PENALTY_MEASURE)` và `(VIOLATION)-[:DEDUCTS_POINT]->(POINT_DEDUCTION)` |
| `legal_basis` (Điều X, Khoản Y, Nghị định Z) | **Tái tạo được** bằng cách: (1) đọc trực tiếp `Chunk.metadata_dieu/metadata_khoan/metadata_diem` (đã lưu phẳng, không cần truy vết), hoặc (2) truy vết ngược `(Chunk)<-[:HAS_CHUNK\|HAS_POINT\|HAS_CLAUSE\|HAS_ARTICLE*]-(Document)` để lấy đủ Article/Clause/Point + tên Document |
| `decree_version` (`"168/2024"`) | Không lưu thành field riêng — suy ra từ `Document.name` (chuỗi đầy đủ, vd *"Nghị định số 168/2024/NĐ-CP"*) hoặc `Document.year` (Integer, trích bằng regex) |

### Ví dụ Cypher tái tạo một "ViolationRecord" từ đồ thị thực

```cypher
MATCH (s:SUBJECT)-[:COMMITS]->(v:VIOLATION)-[:MENTIONED_IN]->(c:Chunk)
OPTIONAL MATCH (v)-[:HAS_MONEY_AMOUNT]->(m:MONEY_AMOUNT)
OPTIONAL MATCH (v)-[:HAS_PENALTY]->(p:PENALTY_MEASURE)
OPTIONAL MATCH (v)-[:DEDUCTS_POINT]->(pd:POINT_DEDUCTION)
MATCH (doc:Document {id: toLower(c.metadata_document)})
WHERE v.value CONTAINS "vượt đèn đỏ"
RETURN
  s.value                              AS subject,          // vehicle_type nằm trong đây
  v.value                              AS canonical_text,
  m.min                                AS fine_min,
  m.max                                AS fine_max,
  collect(DISTINCT p.value) + collect(DISTINCT pd.value) AS additional_penalty,
  c.metadata_dieu + ' - ' + c.metadata_khoan + ' - ' + doc.name AS legal_basis,
  doc.year                             AS decree_version
```

Đây chính xác là logic mà `chatbot/utils.py::cypher_query` (mục 7) thực hiện ở quy mô lớn hơn (hybrid search + boosting), và kết quả trả về **đã có sẵn đúng 4 nhóm thông tin** mà đề bài mô tả — hiển thị trong câu trả lời cuối theo đúng format:

```
Hành vi: {canonical_text}
Mức phạt: {fine_min}–{fine_max} đồng
Hình thức bổ sung: {additional_penalty}
Căn cứ: {legal_basis}
```

Format này được ép buộc trực tiếp trong prompt hệ thống (`chatbot/utils.py::return_prompt_result`, mục "CÁCH A – câu hỏi về mức phạt"): *"BẮT BUỘC TRÍCH XUẤT MỨC PHẠT... nêu rõ con số phạt tiền cụ thể... và hình phạt bổ sung (trừ điểm, tước bằng)"*, cùng cơ chế trích dẫn nguồn `[[S1]]`, `[[S2]]`... ánh xạ tới từng `Chunk.content` gốc để người dùng truy vết lại đúng văn bản pháp luật.

---

## 7. Luồng truy vấn thời gian thực (Query-time RAG)

`chatbot/bot.py::GraphRAG_Bot.run_chatbot()` / `run_chatbot_ndjson()`:

1. **Viết lại câu hỏi (`rewrite_query`)** — Gemini chuẩn hoá câu hỏi tự nhiên (có xét lịch sử hội thoại để suy luận ngữ cảnh bị lược, vd "nó", "thế còn") thành từ khoá pháp lý chuẩn.
2. **Phân loại hình sự (`is_criminal_case`)** — heuristic từ khoá (chết người, tử vong, hình sự...) để quyết định có truy vấn thêm nhánh Bộ luật Hình sự (`cypher_query_criminal`) hay không.
3. **Sinh vector câu hỏi** — cùng model embedding (`AITeamVN/Vietnamese_Embedding`) dùng lúc ingest, đảm bảo cùng không gian vector.
4. **Hybrid Search** (`cypher_query`):
   - Top-8 theo **vector similarity** trên `chunk_vector_index` + Top-10 theo **full-text (Lucene)** trên `chunk_content_index` → gộp, khử trùng, lấy Top-10.
5. **Boosting điểm số theo lĩnh vực pháp lý** — nhân hệ số ưu tiên nếu chunk thuộc văn bản Hình sự (×1.5) hoặc Dân sự/bồi thường (×1.4) hoặc có "phạt tù"/"phạm tội" (×1.3).
6. **Lọc theo văn bản mới nhất** — nếu cùng một hành vi được quy định ở nhiều phiên bản Nghị định, chỉ giữ `doc.year = max(năm)`.
7. **Cảnh báo sửa đổi/bãi bỏ** — kiểm tra quan hệ `AMENDS`/`REPEALS` từ `DOCUMENT_RECORD` để chèn cảnh báo "quy định đã bị sửa đổi/bãi bỏ" nếu có.
8. **Truy vết "anh em" (sibling)** — với mỗi Chunk trúng, lấy thêm các Chunk cùng Điều (qua `HAS_CLAUSE|HAS_POINT|HAS_CHUNK`) để không bị cắt cụt ngữ cảnh khi một hành vi được diễn giải xuyên nhiều Điểm/Khoản.
9. **Sinh câu trả lời** — toàn bộ dữ liệu đồ thị (top 15–20 bản ghi) được nhúng dạng JSON vào prompt Gemini với chỉ thị "kỷ luật thép": chỉ dùng dữ liệu được cấp, cấm suy diễn chéo Điểm/Khoản, bắt buộc nêu rõ số tiền phạt và hình phạt bổ sung, trích dẫn nguồn `[[S1]]...` — trả lời dạng **stream** (SSE/NDJSON) về frontend.

---

## 8. Khả năng chịu lỗi & resume khi gián đoạn

| Giai đoạn | Có resume không? | Cơ chế |
|---|---|---|
| OCR cục bộ (`DocProcessor`) | **Có** | PDF được chia lô theo trang (`chunk_size`, mặc định 3 trang/lô); sau mỗi lô OCR thành công, tiến trình ghi `{output_file_path}.progress` (số lô đã xong) và `{output_file_path}.temp` (markdown thô tích luỹ). `output_file_path` được suy ra từ `doc_uuid` (băm nội dung file) nên **upload lại đúng file cũ sẽ tiếp tục từ lô chưa xong**, không OCR lại từ đầu. |
| OCR qua Gemini (`PdfToMarkdownConverter`) | Có (cơ chế tương tự, theo lô 3 trang gửi API) | |
| Trích xuất thực thể qua Gemini (`GetEntitiesByGemini`) | Có (theo từng chunk, cùng cơ chế `.progress`/`.temp`) | |
| Trích xuất thực thể cục bộ (`GetEntitiesLocal`) | Không cần — chạy regex thuần trong bộ nhớ, xử lý toàn văn bản trong vài giây kể cả với hàng nghìn chunk, chạy lại từ đầu không tốn chi phí đáng kể | |
| Upload lên Neo4j | **Có, tự nhiên** — mọi thao tác ghi đều dùng `MERGE` (không phải `CREATE`), nên chạy lại một file đã upload một phần sẽ không tạo trùng lặp | |
| Sinh embedding (Chunk & Entity) | **Có, tự nhiên** — lọc `WHERE embedding IS NULL`, ghi ngay sau mỗi batch nhỏ (4 hoặc 1 bản ghi); Neo4j chính là checkpoint | |
| Endpoint `/build_graph` | Cho phép upload lại các file JSON **chưa** upload thành công (file đã upload được đổi tên hậu tố `.uploaded` nên tự động bị loại khỏi danh sách quét lại) | |

---

## 9. Cấu hình & biến môi trường

`config.yaml` (không chứa bí mật, có thể commit) — các cờ quan trọng:

```yaml
ingestion:
  use_local_ocr: true          # true = OCR cục bộ (Docling+YOLOv8+CRNN); false = Gemini
  use_local_extraction: true   # true = trích xuất thực thể bằng regex cục bộ; false = Gemini
```

`.env` (KHÔNG commit — xem `.env.example` ở thư mục gốc dự án):

| Biến | Ý nghĩa |
|---|---|
| `API_KEY` | Gemini API key (dùng cho: OCR dự phòng, trích xuất dự phòng, xây quan hệ liên văn bản, và toàn bộ luồng chat thời gian thực) |
| `URI` | Địa chỉ kết nối Neo4j, vd `bolt://localhost:7687` |
| `USER_NEO4J`, `PASSWORD_NEO4J` | Thông tin đăng nhập Neo4j |

Yêu cầu hạ tầng để chạy được toàn bộ pipeline: **Neo4j**, trọng số OCR cục bộ trong thư mục `weight/` (không nằm trong Git, cần tải/copy riêng), Python venv với các thư viện trong `requirements.txt` (Docling, torch, sentence-transformers, neo4j-driver, google-generativeai/google-genai...).
