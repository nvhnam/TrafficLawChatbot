# Bộ GOLD — 300 lỗi giao thông chuẩn hóa

Đây là **cơ sở tri thức chuẩn (gold knowledge base)** dùng làm "đáp án đúng" để chấm điểm
hệ thống. Dữ liệu được trích + chuẩn hóa **tự động từ JSONL đã trích xuất thực thể**
(không tốn API), bằng `../harness/build_gold.py` và `../harness/sample_gold.py`.

## Các file trong thư mục

| File | Ý nghĩa |
|---|---|
| `violations_gold.csv` | **Bản đầy đủ**: toàn bộ ~2.682 lỗi trích được từ 3 nghị định (đã dedup trong cùng văn bản). Là kho để chọn mẫu, tra cứu, tái lập. |
| `violations_gold_300.csv` | **Gold chính thức**: 300 lỗi được chọn cân bằng theo loại phương tiện + phủ nhóm hành vi. Đây là bản dùng để sinh câu hỏi & chấm điểm. Có thêm cột `behavior_category`. |
| `violation_aliases.csv` | Danh sách alias (cách nói) của mỗi lỗi. Hiện mỗi lỗi có 1 dòng `canonical`; **nhóm bổ sung tay** các cách nói đời thường (`colloquial`) để tăng chất lượng test ngữ nghĩa. |

## Từ điển cột — `violations_gold.csv` / `violations_gold_300.csv`

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| `violation_id` | Mã lỗi duy nhất, tự truy vết: `{DOC}_{Điều}_{Khoản}_{Điểm}_{stt}` | `ND168_6_1_a_0012` |
| `legal_doc` | Nghị định căn cứ | `Nghị định 168/2024/NĐ-CP` |
| `article` | Điều | `6` |
| `clause` | Khoản | `1` |
| `point` | Điểm | `a` |
| `vehicle_type` | Loại phương tiện đã chuẩn hóa (ô tô / xe máy / máy kéo·chuyên dùng / xe đạp·thô sơ / người đi bộ / xe súc vật kéo / chủ phương tiện / tổ chức·cá nhân khác / không xác định) | `ô tô` |
| `actor` | Chủ thể vi phạm nguyên văn (từ SUBJECT) | `người điều khiển xe ô tô...` |
| `behavior_canonical` | Tên hành vi rút gọn (VIOLATION.name) — dùng để đối chiếu ngữ nghĩa | `Không chấp hành hiệu lệnh đèn tín hiệu` |
| `behavior_raw` | Hành vi nguyên văn trong luật (VIOLATION.value) | `không chấp hành hiệu lệnh của đèn tín hiệu giao thông` |
| `condition_text` | Điều kiện áp dụng (STANDARD_CONDITION), nếu có | |
| `fine_min` | **Mức phạt thấp nhất (số nguyên VND)** | `4000000` |
| `fine_max` | **Mức phạt cao nhất (số nguyên VND)** | `6000000` |
| `fine_text` | Nguyên văn mức phạt (để đối chiếu/hiển thị) | `Phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng` |
| `additional_penalty` | Hình thức xử phạt bổ sung (tước GPLX, tịch thu...), nối bằng ` \| ` | `tước quyền sử dụng GPLX từ 01 đến 03 tháng` |
| `penalty_duration` | Thời hạn của hình thức bổ sung (TIME_DURATION) | `từ 02 tháng đến 04 tháng` |
| `point_deduction` | Trừ điểm GPLX (đặc thù NĐ 168/2024), nếu có | |
| `remedial_measure` | Biện pháp khắc phục hậu quả (PROCEDURE_ACTION), nếu có | |
| `effective_status` | Trạng thái hiệu lực: `current` (168/2024) · `amendment` (123/2021) · `old_base` (100/2019) | `current` |
| `source_text` | Trích nguyên văn điều luật (cắt ≤600 ký tự) để truy vết căn cứ | |
| `note` | Ghi chú kỹ thuật; `fine_fallback_chunk` = mức phạt lấy theo chunk khi không nối trực tiếp | |
| `behavior_category` *(chỉ ở bản 300)* | Nhóm hành vi để phân tích: cồn/ma túy · tốc độ · tín hiệu/biển báo · giấy tờ/GPLX · dừng/đỗ · làn/phần đường · chở hàng/chở người · khác | `tín hiệu/biển báo` |

## Từ điển cột — `violation_aliases.csv`

| Cột | Ý nghĩa |
|---|---|
| `alias_id` | Mã alias (`{violation_id}_a{n}`) |
| `violation_id` | Khóa ngoại trỏ về lỗi trong `violations_gold` |
| `alias_text` | Cách diễn đạt của hành vi |
| `alias_type` | `canonical` (tên chuẩn, tự sinh) hoặc `colloquial` (cách nói đời thường, nhóm thêm tay) |

## Lưu ý chất lượng (minh bạch để bảo vệ)

- **Trường mạnh nhất là mức phạt tiền** (`fine_min/max`): ~100% các lỗi được chọn có mức phạt
  dạng số → là trục chấm điểm chính, khách quan.
- `additional_penalty` / `point_deduction` **thưa** vì luật VN thường quy định hình thức bổ sung
  ở *khoản khác* (tham chiếu "áp dụng với hành vi tại khoản X"), không nằm cùng chunk với hành vi.
  → câu hỏi về mức phạt & căn cứ điều luật là chủ đạo; câu về bổ sung/trừ điểm số lượng ít hơn.
- NĐ 123/2021 (bản regex) đóng góp ít lỗi độc lập vì là **nghị định sửa đổi** và regex có recall
  chủ thể thấp — đã chấp nhận và ghi nhận trong báo cáo pipeline.
