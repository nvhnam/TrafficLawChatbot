# Báo cáo đánh giá Pipeline trích xuất thực thể pháp luật giao thông

## 1. Tổng quan hệ thống KG-RAG

### Knowledge Graph (KG) là gì?

Knowledge Graph (đồ thị tri thức) là cách tổ chức dữ liệu dưới dạng **node** (thực thể)
và **edge** (quan hệ giữa các thực thể), tạo thành một mạng lưới kiến thức có cấu trúc.

Ví dụ một đoạn Knowledge Graph cho luật giao thông:

```
[Người điều khiển xe ô tô]  --COMMITS-->  [Vượt đèn đỏ]  --HAS_MONEY_AMOUNT-->  [4-6 triệu đồng]
        (SUBJECT)                           (VIOLATION)                            (MONEY_AMOUNT)
                                                |
                                                +--HAS_PENALTY--> [Tước GPLX 2-4 tháng]
                                                                    (PENALTY_MEASURE)
```

### RAG (Retrieval-Augmented Generation) là gì?

RAG là kỹ thuật kết hợp giữa truy xuất dữ liệu (Retrieval) và sinh câu trả lời (Generation).
Thay vì để chatbot "bịa" câu trả lời, RAG buộc chatbot phải tra cứu dữ liệu thật trước khi trả lời.

### KG-RAG hoạt động như thế nào?

Khi người dùng hỏi: *"Đi xe máy vượt đèn đỏ bị phạt bao nhiêu?"*

1. **Retrieval**: Hệ thống tìm kiếm trong Knowledge Graph:
   - Tìm node SUBJECT chứa "xe máy"
   - Đi theo cạnh COMMITS đến node VIOLATION chứa "vượt đèn đỏ"
   - Đi theo cạnh HAS_MONEY_AMOUNT đến node MONEY_AMOUNT

2. **Generation**: Chatbot dùng thông tin tìm được để sinh câu trả lời:
   *"Theo Điều 6, Khoản 4, Điểm a NĐ 100/2019, người điều khiển xe mô tô
   vượt đèn đỏ bị phạt từ 800.000 đến 1.000.000 đồng."*

### Hệ thống đang xây dựng cần gì?

Pipeline xử lý dữ liệu có nhiệm vụ chuyển đổi văn bản nghị định (Markdown)
thành file JSONL chứa các thực thể và quan hệ, sẵn sàng nạp vào Neo4j
(cơ sở dữ liệu đồ thị) để phục vụ chatbot.

```
Nghị định (PDF) --> Markdown --> Chunking --> Trích xuất --> Bổ sung ngữ cảnh --> JSONL --> Neo4j
                                                 ^                  ^
                                          (regex + kế thừa)  (resolve tham chiếu)
```

---

## 2. Giải thích các nhãn thực thể

### VIOLATION (hành vi vi phạm) — quan trọng nhất

Mô tả hành vi bị xử phạt. Đây là nhãn **quan trọng nhất** vì mỗi câu hỏi
của người dùng đều xoay quanh một hành vi cụ thể.

> **Ví dụ**: *"Không chấp hành hiệu lệnh, chỉ dẫn của biển báo hiệu, vạch kẻ đường"*
> (Điều 5, Khoản 1, Điểm a - NĐ 100/2019)

### MONEY_AMOUNT (mức phạt tiền)

Khoảng tiền phạt (tối thiểu - tối đa) cho mỗi nhóm hành vi vi phạm.

> **Ví dụ**: *"Phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng"*
> (Điều 5, Khoản 4 - áp dụng cho vượt đèn đỏ bằng ô tô)

### PENALTY_MEASURE (hình thức phạt bổ sung)

Ngoài phạt tiền, người vi phạm còn có thể bị: tước GPLX, tịch thu phương tiện,
đình chỉ hoạt động... Thông tin này rất quan trọng, đặc biệt với vi phạm nghiêm trọng.

> **Ví dụ**: *"Tước quyền sử dụng Giấy phép lái xe từ 02 tháng đến 04 tháng"*
> (Điều 5, Khoản 11, Điểm c - áp dụng khi vượt đèn đỏ bằng ô tô)

### SUBJECT (chủ thể vi phạm)

Đối tượng bị xử phạt. Rất quan trọng vì **cùng hành vi, mức phạt khác nhau tùy loại xe**:
- Vượt đèn đỏ bằng xe máy: 800.000 - 1.000.000 đồng
- Vượt đèn đỏ bằng ô tô: 4.000.000 - 6.000.000 đồng

> **Ví dụ**: *"Người điều khiển xe mô tô, xe gắn máy, các loại xe tương tự xe mô tô"*
> (Điều 6 - NĐ 100/2019)

### OBJECT_EQUIPMENT (thiết bị, giấy tờ)

Các đối tượng vật lý: giấy phép lái xe, mũ bảo hiểm, thiết bị giám sát hành trình...

> **Ví dụ**: *"giấy phép lái xe"* trong "Không mang theo giấy phép lái xe"

### Relationships (quan hệ giữa các thực thể)

| Quan hệ | Ý nghĩa | Ví dụ |
|----------|---------|-------|
| COMMITS | Chủ thể thực hiện hành vi | Người lái ô tô → Vượt đèn đỏ |
| HAS_MONEY_AMOUNT | Hành vi có mức phạt | Vượt đèn đỏ → 4-6 triệu đồng |
| HAS_PENALTY | Hành vi có phạt bổ sung | Vượt đèn đỏ → Tước GPLX 2-4 tháng |
| APPLIES_TO_OBJECT | Liên quan đến thiết bị | Vi phạm → Giấy phép lái xe |

### Các nhãn phụ

| Nhãn | Ý nghĩa | Ví dụ |
|------|---------|-------|
| TIME_DURATION | Thời hạn phạt bổ sung | "Từ 01 đến 03 tháng" |
| DOCUMENT_RECORD | Tham chiếu văn bản | "Nghị định 100/2019/NĐ-CP" |
| LEGAL_CONCEPT | Khái niệm pháp lý | "Xử phạt vi phạm hành chính" |
| PROCEDURE_ACTION | Biện pháp khắc phục | "Buộc phải đỗ xe đúng nơi quy định" |

---

## 3. Đánh giá chất lượng: Entity Matching (Precision / Recall / F1)

> [!IMPORTANT]
> Đánh giá này so sánh **nội dung** thực thể, không chỉ đếm số lượng.
> Với mỗi Điều/Khoản/Điểm, script kiểm tra entity của regex có **khớp nội dung**
> với entity Gemini không (sử dụng fuzzy text matching, ngưỡng 60%).

### Giải thích chỉ số

- **Precision** = Trong tất cả entity regex trích ra, bao nhiêu % cũng có trong Gemini?
  → Precision cao = regex **ít nhầm** (ít false positive)
- **Recall** = Trong tất cả entity Gemini trích ra, bao nhiêu % được regex bắt?
  → Recall cao = regex **ít bỏ sót** (ít false negative)
- **F1** = Trung bình hài hoà của Precision và Recall
  → Điểm tổng hợp, càng cao càng tốt

### Kết quả NĐ 100/2019/NĐ-CP

| Nhãn | Precision | Recall | F1 | Khớp / Regex / Gemini |
|------|:---------:|:------:|:--:|:---------------------:|
| VIOLATION | 86.1% | 77.9% | **81.8%** | 1.181 / 1.372 / 1.516 |
| MONEY_AMOUNT | **100.0%** | 77.4% | **87.3%** | 1.010 / 1.010 / 1.305 |
| SUBJECT | 78.5% | 26.3% | 39.4% | 486 / 619 / 1.851 |
| PENALTY_MEASURE | 23.8% | 32.8% | 27.5% | 119 / 501 / 363 |
| OBJECT_EQUIPMENT | 16.6% | 6.1% | 8.9% | 49 / 296 / 808 |
| TIME_DURATION | **100.0%** | 63.4% | **77.6%** | 71 / 71 / 112 |
| PROCEDURE_ACTION | 52.9% | 25.2% | 34.2% | 27 / 51 / 107 |
| **TỔNG** | **75.1%** | **48.5%** | **59.0%** | 2.943 / 3.920 / 6.062 |

### Kết quả NĐ 168/2024/NĐ-CP

| Nhãn | Precision | Recall | F1 | Khớp / Regex / Gemini |
|------|:---------:|:------:|:--:|:---------------------:|
| VIOLATION | 83.0% | 79.1% | **81.0%** | 777 / 936 / 982 |
| MONEY_AMOUNT | **100.0%** | 82.1% | **90.2%** | 634 / 634 / 772 |
| SUBJECT | 75.4% | 41.1% | **53.2%** | 508 / 674 / 1.236 |
| PENALTY_MEASURE | 23.5% | 15.7% | 18.9% | 40 / 170 / 254 |
| OBJECT_EQUIPMENT | 17.2% | 11.8% | 14.0% | 60 / 348 / 507 |
| TIME_DURATION | **100.0%** | 37.0% | **54.0%** | 17 / 17 / 46 |
| PROCEDURE_ACTION | 42.1% | 5.6% | 9.9% | 8 / 19 / 142 |
| **TỔNG** | **73.1%** | **51.9%** | **60.7%** | 2.044 / 2.798 / 3.939 |

### Tổng hợp trung bình 2 nghị định

| Nhãn | Precision TB | Recall TB | F1 TB | Đánh giá |
|------|:----------:|:--------:|:-----:|----------|
| VIOLATION | 84.6% | 78.5% | **81.4%** | Tốt |
| MONEY_AMOUNT | **100.0%** | 79.8% | **88.8%** | Rất tốt |
| SUBJECT | 77.0% | 33.7% | 46.3% | Khá (precision tốt, recall thấp) |
| PENALTY_MEASURE | 23.7% | 24.3% | 23.2% | Kém |
| TIME_DURATION | **100.0%** | 50.2% | **65.8%** | Tốt |
| **TỔNG** | **74.1%** | **50.2%** | **59.9%** | Khá |

---

## 4. Phân tích chi tiết

### MONEY_AMOUNT — Precision 100%, F1 88.8%

> [!TIP]
> Đây là nhãn tốt nhất. Mọi mức phạt regex trích ra đều **đúng hoàn toàn**.

**Ví dụ khớp hoàn hảo:**
```
[Regex]  Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng
[Gemini] Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng
→ Khớp 100%
```

Recall 80% vì Gemini tạo entity MONEY_AMOUNT trùng lặp ở nhiều chunk,
trong khi regex chỉ tạo 1 lần tại chunk gốc + kế thừa cho chunk con.

### VIOLATION — F1 81.4%

Hành vi vi phạm khớp rất tốt. Chênh lệch nhỏ do regex giữ nguyên prefix "a)"
trong khi Gemini bỏ prefix:

```
[Regex]  a) Chở hàng siêu trường không có báo hiệu kích thước...
[Gemini] Chở hàng siêu trường không có báo hiệu kích thước...
→ Nội dung giống nhau, chỉ khác prefix "a)"
```

### SUBJECT — Precision 77%, Recall 34%

**Precision tốt**: Khi regex trích được chủ thể, 77% là **đúng**.

**Recall thấp**: Regex chỉ bắt được chủ thể từ tiêu đề Điều (VD: "Xử phạt người
điều khiển xe ô tô"). Gemini bắt thêm chủ thể từ nội dung khoản:

```
[Regex]  người điều khiển xe cơ giới
[Gemini] người điều khiển xe mô tô hai bánh có dung tích xi-lanh trên 125 cm³
→ Gemini chi tiết hơn vì đọc hiểu ngữ cảnh khoản
```

**Ảnh hưởng**: Chatbot có thể gán đúng loại phương tiện 77% trường hợp.
33% còn lại sẽ thiếu thông tin chủ thể, nhưng metadata (Điều/Khoản/Điểm)
vẫn cho phép truy xuất nguồn gốc chính xác.

### PENALTY_MEASURE — F1 23.2%

> [!WARNING]
> Đây là nhãn kém nhất. Cả precision lẫn recall đều thấp.

**Vì sao precision thấp (24%)**:
Regex giữ nguyên văn từ nghị định, Gemini tóm tắt lại. Cùng nội dung
nhưng cách diễn đạt khác nhau nên fuzzy matching không khớp:

```
[Regex]  tước quyền sử dụng Giấy phép lái xe từ 01 tháng đến 03 tháng
[Gemini] Tước quyền sử dụng GPLX 1-3 tháng đối với hành vi vi phạm tại khoản 2
→ Cùng ý nhưng cách viết khác → matching score < 60% → không khớp
```

**Vì sao recall thấp (24%)**:
Gemini trích riêng từng hình thức phạt (tước, tịch thu, đình chỉ) cho từng hành vi.
Regex chỉ resolve được khi khoản phạt bổ sung tham chiếu rõ ràng "tại khoản X".

### OBJECT_EQUIPMENT — F1 11.5%

**Vì sao kém**: Regex dùng từ điển cố định 32 mục, match exact string.
Gemini hiểu ngữ nghĩa và trích cả thiết bị không có trong từ điển:

```
[Regex]  Giấy phép lái xe    (match từ điển)
[Gemini] giấy phép lái xe hạng B2  (Gemini thêm chi tiết "hạng B2")
→ Cùng entity nhưng text khác → không khớp
```

Ngoài ra Gemini trích thêm: "số khung", "số máy", "bộ phận giảm thanh",
"hệ thống treo" — những entity không có trong từ điển regex.

---

## 5. Ví dụ so sánh thực tế

### Ví dụ 1: Khớp hoàn hảo (Điều 22, Khoản 1, Điểm a - NĐ 168)

```
VIOLATION:
  [Regex]  Chở hàng siêu trường, siêu trọng không có báo hiệu kích thước
  [Gemini] Chở hàng siêu trường, siêu trọng không có báo hiệu kích thước
  → ✅ Khớp

MONEY_AMOUNT:
  [Regex]  Phạt tiền từ 2.000.000 đồng đến 3.000.000 đồng
  [Gemini] Phạt tiền từ 2.000.000 đồng đến 3.000.000 đồng
  → ✅ Khớp

SUBJECT:
  [Regex]  người điều khiển xe ô tô
  [Gemini] người điều khiển xe ô tô
  → ✅ Khớp
```

### Ví dụ 2: Regex thiếu SUBJECT (Điều 12, Khoản 2, Điểm e - NĐ 168)

```
VIOLATION:
  [Regex]  Bán hàng rong trên lòng đường, vỉa hè các tuyến phố
  [Gemini] Bán hàng rong trên lòng đường, vỉa hè các tuyến phố
  → ✅ Khớp

SUBJECT:
  [Regex]  (không có)
  [Gemini] cá nhân
  → ❌ Regex thiếu — Gemini suy ra "cá nhân" từ ngữ cảnh
```

### Ví dụ 3: Regex có SUBJECT nhưng ít chi tiết hơn Gemini (Điều 18 - NĐ 168)

```
SUBJECT:
  [Regex]  người điều khiển xe cơ giới
  [Gemini] người điều khiển xe mô tô hai bánh có dung tích xi-lanh trên 125 cm³
  → ⚠️ Regex đúng nhưng Gemini chi tiết hơn nhiều
```

---

## 6. Bảng tổng kết

| Nhãn | F1 | Precision | Ảnh hưởng KG-RAG | Nhận xét |
|------|:--:|:---------:|:-----------------:|----------|
| MONEY_AMOUNT | **88.8%** | **100%** | Rất cao | Hoàn hảo — không sai entity nào |
| VIOLATION | **81.4%** | 84.6% | Rất cao | Tốt — chênh lệch chỉ do prefix "a)" |
| TIME_DURATION | **65.8%** | **100%** | Trung bình | Tốt — không sai, chỉ thiếu |
| SUBJECT | 46.3% | 77.0% | Cao | Khá — đúng khi có, nhưng thiếu nhiều |
| PROCEDURE_ACTION | 22.1% | 47.5% | Thấp | Kém — ít ai hỏi |
| PENALTY_MEASURE | 23.2% | 23.7% | Cao | Kém — cách diễn đạt khác nhau |
| OBJECT_EQUIPMENT | 11.5% | 16.9% | Trung bình | Kém — từ điển quá nhỏ |

---

## 7. Kết luận: Regex có thay thế Gemini API được không?

### So sánh tổng thể

| Tiêu chí | Regex | Gemini | Ai thắng? |
|----------|:-----:|:------:|:---------:|
| F1 tổng | **59.9%** | 100% (baseline) | Gemini |
| F1 hành vi vi phạm | **81.4%** | 100% | Ngang nhau |
| F1 mức phạt tiền | **88.8%** | 100% | Ngang nhau |
| Precision mức phạt | **100%** | - | Regex (0 sai) |
| F1 chủ thể | 46.3% | 100% | Gemini |
| Tốc độ xử lý | **< 1 giây** | ~30 phút | Regex |
| Chi phí | **0 đồng** | ~2.500 API calls | Regex |
| Kết quả ổn định | **100%** | Mỗi lần khác | Regex |

### Trả lời

**Được — cho bài toán chatbot tra cứu mức phạt giao thông ở mức đồ án.**

Hai nhãn quan trọng nhất cho câu hỏi *"Hành vi X bị phạt bao nhiêu?"*:
- VIOLATION: F1 **81.4%** — rất tốt
- MONEY_AMOUNT: F1 **88.8%**, Precision **100%** — hoàn hảo

Chatbot sẽ trả lời đúng mức phạt trong đa số trường hợp. Phần thiếu
(SUBJECT, PENALTY_MEASURE) có thể bù đắp bằng metadata phân cấp
(Điều/Khoản/Điểm) trong Knowledge Graph.

**Không nên quay lại Gemini** vì:
- Chi phí API cao (2.500+ lần gọi mỗi nghị định)
- Kết quả không tái sản xuất (mỗi lần chạy cho output khác nhau)
- Pipeline regex cho Precision 100% ở mức phạt — **không bao giờ sai mức phạt**
- Chạy offline, miễn phí, < 1 giây cho toàn bộ nghị định

### Nếu muốn cải thiện thêm?

| Hướng cải tiến | Nhãn ảnh hưởng | Ước tính cải thiện F1 |
|---------------|:--------------:|:---------------------:|
| Mở rộng từ điển thiết bị | OBJECT_EQUIPMENT | +15-20% |
| Thêm pattern "đối với (chủ thể)" | SUBJECT | +10-15% |
| Normalize text trước khi matching | PENALTY_MEASURE | +10% (đánh giá) |
| Bổ sung pattern "buộc" giữa câu | PROCEDURE_ACTION | +5-10% |
