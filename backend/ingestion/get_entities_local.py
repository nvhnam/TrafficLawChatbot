"""
Local, regex-based entity/relation extractor — replaces GetEntitiesByGemini.

Ported from RelationKnowledge_CS2231.CH202-main/data_pipeline/step2_extract_local.py
(ImprovedLocalEntityExtractor), adapted for backend/chunking/legal_splitter.py's chunk
shape: unlike the original chunker, legal_splitter emits `khoan` on essentially every
chunk of a multi-khoan article (no dedicated khoan=None header chunk), so SUBJECT
extraction here keys off "first chunk seen for this dieu" instead of "khoan is falsy".
"""

import re
import uuid
import logging

logger = logging.getLogger(__name__)

# Từ điển thiết bị/giấy tờ để trích xuất OBJECT_EQUIPMENT
EQUIPMENT_DICT = [
    "giấy phép lái xe", "giấy đăng ký xe", "chứng nhận đăng ký xe",
    "giấy chứng nhận kiểm định", "tem kiểm định",
    "giấy chứng nhận bảo hiểm", "bảo hiểm trách nhiệm dân sự",
    "mũ bảo hiểm", "dây an toàn", "dây đai an toàn",
    "thiết bị giám sát hành trình", "camera",
    "gương chiếu hậu", "đèn tín hiệu", "đèn chiếu sáng",
    "còi xe", "phanh", "hệ thống phanh",
    "biển số xe", "biển số đăng ký",
    "phù hiệu", "giấy phép kinh doanh vận tải",
    "giấy phép lưu hành", "sổ nhật ký hành trình",
    "lệnh vận chuyển", "giấy vận tải",
    "ghế ngồi cho trẻ em", "thiết bị cứu sinh",
    "bình cứu hỏa", "bình chữa cháy",
    "giấy phép thi công", "giấy phép đào tạo lái xe",
]


class ImprovedLocalEntityExtractor:
    """Trích xuất thực thể với kế thừa ngữ cảnh từ cấu trúc phân cấp văn bản."""

    def __init__(self):
        self.MONEY_PATTERN = re.compile(
            r"[Pp]hạt tiền từ\s+([\d.]+(?:\.\d+)*)\s*đồng\s+đến\s+([\d.]+(?:\.\d+)*)\s*đồng",
            re.IGNORECASE
        )
        self.LICENSE_REVOKE_PATTERN = re.compile(
            r"[Tt]ước quyền sử dụng\s+(.+?)\s+(?:có thời hạn\s+)?từ\s+(\d+)\s*tháng\s+đến\s+(\d+)\s*tháng",
            re.IGNORECASE
        )
        self.SUSPEND_PATTERN = re.compile(
            r"[Đđ]ình chỉ\s+(.+?)\s+từ\s+(\d+)\s*tháng\s+đến\s+(\d+)\s*tháng",
            re.IGNORECASE
        )
        self.CONFISCATE_PATTERN = re.compile(
            r"[Tt]ịch thu\s+(.+?)(?:\.|;|$)", re.IGNORECASE
        )
        self.REMEDY_PATTERN = re.compile(
            r"[Bb]uộc\s+(.+?)(?:\.|;|$)", re.IGNORECASE
        )
        self.DURATION_PATTERN = re.compile(
            r"từ\s+(\d+)\s*(tháng|năm|ngày)\s+đến\s+(\d+)\s*(tháng|năm|ngày)",
            re.IGNORECASE
        )
        self.POINT_DEDUCTION_PATTERN = re.compile(
            r"[Tt]rừ\s+(\d+)\s*điểm", re.IGNORECASE
        )
        # Pattern trích xuất SUBJECT từ tiêu đề Điều
        self.ARTICLE_SUBJECT_PATTERNS = [
            # Pattern 1: "Xử phạt, trừ điểm ... của (chủ thể)" (NĐ 168)
            re.compile(
                r"(?:Xử phạt|xử phạt)(?:,\s*trừ điểm[^.]*?)\s+(?:của|đối với)\s+"
                r"((?:người|chủ|nhân viên|hành khách)[^.]*?)(?:\s+vi phạm|\s+thực hiện|\s*$)",
                re.IGNORECASE | re.MULTILINE
            ),
            # Pattern 2: "Xử phạt (chủ thể) vi phạm..." (NĐ 100)
            re.compile(
                r"(?:Xử phạt|xử phạt)\s+"
                r"((?:người|chủ|nhân viên|hành khách)[^.]*?)(?:\s+vi phạm|\s+thực hiện|\s*$)",
                re.IGNORECASE | re.MULTILINE
            ),
            # Pattern 3: "Xử phạt đối với chủ phương tiện..."
            re.compile(
                r"(?:Xử phạt|xử phạt)\s+(?:đối với\s+)?"
                r"((?:người|chủ|nhân viên|hành khách)[^.]*?)(?:\s+vi phạm|\s+thực hiện|\s*$)",
                re.IGNORECASE | re.MULTILINE
            ),
        ]

    def _parse_money(self, money_str):
        clean = money_str.replace(".", "").replace(",", "").strip()
        try:
            return int(clean)
        except ValueError:
            return 0

    def _truncate(self, text, max_len=300):
        text = re.sub(r'\s+', ' ', text.strip())
        return text[:max_len] + "..." if len(text) > max_len else text

    def _short_name(self, value, max_len=80):
        name = re.sub(r'\s+', ' ', value.strip())
        return name[:max_len] + "..." if len(name) > max_len else name

    def _strip_prefix(self, content):
        """Loại bỏ prefix [Văn bản: ...] và context header."""
        text = re.sub(r'^\[Văn bản:.*?\]\s*', '', content)
        text = re.sub(r'^\[.*?\]\s*', '', text)  # context header [Chương..., Mục...]
        return text

    # =========================================================================
    # PASS 1: Xây dựng bản đồ ngữ cảnh từ cấu trúc phân cấp
    # =========================================================================

    def build_context_maps(self, chunks):
        """
        Quét toàn bộ chunks để xây dựng bản đồ:
        - article_subjects[dieu] = tên chủ thể (từ tiêu đề Điều)
        - clause_money[(dieu, khoan)] = {min, max, text} (từ đầu Khoản)

        legal_splitter.py repeats the "Điều N. Title" text at the top of every
        chunk of that dieu (not just a dedicated header chunk), so SUBJECT is
        extracted from the first chunk seen for each dieu rather than requiring
        khoan to be empty.
        """
        article_subjects = {}  # dieu -> subject text
        article_subject_tried = set()  # dieu đã thử trích xuất (dù thành công hay không)
        clause_money = {}      # (dieu, khoan) -> {min, max, text}

        for chunk in chunks:
            meta = chunk.get("metadata", {})
            dieu = meta.get("dieu")
            khoan = meta.get("khoan")
            diem = meta.get("diem")
            raw = self._strip_prefix(chunk.get("content", ""))

            # --- Trích SUBJECT từ tiêu đề Điều ---
            # Lấy từ chunk đầu tiên gặp của mỗi Điều (title được lặp lại ở mọi chunk con)
            if dieu and dieu not in article_subject_tried:
                article_subject_tried.add(dieu)
                for pattern in self.ARTICLE_SUBJECT_PATTERNS:
                    match = pattern.search(raw)
                    if match:
                        subject_text = match.group(1).strip()
                        subject_text = subject_text.replace('*', '').replace('#', '').strip()
                        subject_text = re.sub(r'\s+', ' ', subject_text)
                        if len(subject_text) > 5:
                            article_subjects[dieu] = subject_text
                            break

            # --- Trích MONEY_AMOUNT từ đầu Khoản ---
            # Chỉ lấy từ CLAUSE_HEADER hoặc chunk khoản không có điểm
            if dieu and khoan and not diem:
                key = (dieu, khoan)
                if key not in clause_money:
                    money_match = self.MONEY_PATTERN.search(raw)
                    if money_match:
                        clause_money[key] = {
                            "min": self._parse_money(money_match.group(1)),
                            "max": self._parse_money(money_match.group(2)),
                            "text": money_match.group(0)
                        }

        logger.info(
            "Ngữ cảnh: %d Điều có SUBJECT, %d Khoản có MONEY_AMOUNT",
            len(article_subjects), len(clause_money)
        )
        return article_subjects, clause_money

    # =========================================================================
    # PASS 2: Trích xuất thực thể cho từng chunk với ngữ cảnh kế thừa
    # =========================================================================

    def extract_from_chunk(self, chunk, article_subjects, clause_money):
        content = chunk.get("content", "")
        metadata = dict(chunk.get("metadata", {}))
        chunk_uuid = metadata.get("chunk_uuid") or uuid.uuid4().hex
        metadata["chunk_uuid"] = chunk_uuid

        dieu = metadata.get("dieu")
        khoan = metadata.get("khoan")
        diem = metadata.get("diem")

        raw = self._strip_prefix(content)

        foundations = []
        rules_actions = []
        measures = []
        relationships = []
        counter = [0]

        def next_id():
            counter[0] += 1
            return f"{chunk_uuid}_e{counter[0]}"

        # === 1. SUBJECT (kế thừa từ tiêu đề Điều) ===
        subject_id = None
        if dieu and dieu in article_subjects:
            subject_text = article_subjects[dieu]
            subject_id = next_id()
            foundations.append({
                "id": subject_id,
                "label": "SUBJECT",
                "name": self._short_name(subject_text, 60),
                "value": subject_text
            })

        # === 2. MONEY_AMOUNT (trực tiếp trong chunk hoặc kế thừa từ Khoản) ===
        money_ids = []
        direct_money = list(self.MONEY_PATTERN.finditer(raw))

        if direct_money:
            for match in direct_money:
                min_val = self._parse_money(match.group(1))
                max_val = self._parse_money(match.group(2))
                eid = next_id()
                measures.append({
                    "id": eid, "label": "MONEY_AMOUNT",
                    "name": f"Từ {match.group(1)} đến {match.group(2)} đồng",
                    "value": match.group(0), "min": min_val, "max": max_val
                })
                money_ids.append(eid)
        elif diem and dieu and khoan:
            # Chunk Điểm không có mức phạt riêng -> kế thừa từ Khoản cha
            key = (dieu, khoan)
            if key in clause_money:
                m = clause_money[key]
                eid = next_id()
                measures.append({
                    "id": eid, "label": "MONEY_AMOUNT",
                    "name": f"Từ {m['min']:,} đến {m['max']:,} đồng".replace(",", "."),
                    "value": m["text"], "min": m["min"], "max": m["max"]
                })
                money_ids.append(eid)

        # === 3. VIOLATION ===
        violation_ids = []
        starts_with_point = re.match(r'^[a-zđ]\)\s+', raw)

        if starts_with_point:
            violation_text = raw.strip()
            # Chỉ tạo VIOLATION nếu KHÔNG phải biện pháp khắc phục/phạt bổ sung
            is_remedy = re.match(r'^[a-zđ]\)\s*(?:Buộc|Tước|Tịch thu|Đình chỉ)', violation_text)
            if not is_remedy and len(violation_text) > 10:
                eid = next_id()
                rules_actions.append({
                    "id": eid, "label": "VIOLATION",
                    "name": self._short_name(violation_text),
                    "value": self._truncate(violation_text, 500)
                })
                violation_ids.append(eid)
        else:
            # Tìm hành vi trong nội dung (pattern "đối với hành vi...")
            v_match = re.search(
                r"(?:đồng\s+)?đối với\s+(?:mỗi\s+)?(?:hành vi\s+)?(?:vi phạm\s+)?(.+?)(?:\.|;|$)",
                raw, re.IGNORECASE | re.DOTALL
            )
            if v_match:
                v_text = v_match.group(1).strip()
                if len(v_text) > 15 and "phạt tiền" not in v_text.lower():
                    eid = next_id()
                    rules_actions.append({
                        "id": eid, "label": "VIOLATION",
                        "name": self._short_name(v_text),
                        "value": self._truncate(v_text, 500)
                    })
                    violation_ids.append(eid)

        # === 4. XÂY DỰNG QUAN HỆ CỐT LÕI ===
        # SUBJECT -> COMMITS -> VIOLATION -> HAS_MONEY_AMOUNT -> MONEY_AMOUNT
        if subject_id:
            for vid in violation_ids:
                relationships.append({"source": subject_id, "type": "COMMITS", "target": vid})
        for vid in violation_ids:
            for mid in money_ids:
                relationships.append({"source": vid, "type": "HAS_MONEY_AMOUNT", "target": mid})

        # === 5. PENALTY_MEASURE (tước GPLX, tịch thu, đình chỉ) ===
        penalty_ids = []
        for lm in self.LICENSE_REVOKE_PATTERN.finditer(raw):
            eid = next_id()
            measures.append({
                "id": eid, "label": "PENALTY_MEASURE",
                "name": f"Tước quyền sử dụng {self._short_name(lm.group(1), 50)}",
                "value": lm.group(0).strip()
            })
            penalty_ids.append(eid)

        for sm in self.SUSPEND_PATTERN.finditer(raw):
            eid = next_id()
            measures.append({
                "id": eid, "label": "PENALTY_MEASURE",
                "name": f"Đình chỉ {self._short_name(sm.group(1), 50)}",
                "value": sm.group(0).strip()
            })
            penalty_ids.append(eid)

        for cm in self.CONFISCATE_PATTERN.finditer(raw):
            text = cm.group(0).strip()
            if len(text) > 10:
                eid = next_id()
                measures.append({
                    "id": eid, "label": "PENALTY_MEASURE",
                    "name": self._short_name(text, 80), "value": self._truncate(text)
                })
                penalty_ids.append(eid)

        for vid in violation_ids:
            for pid in penalty_ids:
                relationships.append({"source": vid, "type": "HAS_PENALTY", "target": pid})

        # === 6. PROCEDURE_ACTION (buộc...) ===
        if re.match(r'^[a-zđ]\)\s*[Bb]uộc', raw):
            for rm in self.REMEDY_PATTERN.finditer(raw):
                text = rm.group(0).strip()
                if len(text) > 10:
                    eid = next_id()
                    rules_actions.append({
                        "id": eid, "label": "PROCEDURE_ACTION",
                        "name": self._short_name(text, 80),
                        "value": self._truncate(text, 400)
                    })
                    break

        # === 7. TIME_DURATION ===
        for dm in self.DURATION_PATTERN.finditer(raw):
            eid = next_id()
            measures.append({
                "id": eid, "label": "TIME_DURATION",
                "name": f"Từ {dm.group(1)} đến {dm.group(3)} {dm.group(4)}",
                "value": dm.group(0).strip()
            })
            for pid in penalty_ids:
                relationships.append({"source": pid, "type": "HAS_DURATION", "target": eid})
            break

        # === 8. POINT_DEDUCTION (trừ điểm GPLX - NĐ 168) ===
        for pm in self.POINT_DEDUCTION_PATTERN.finditer(raw):
            eid = next_id()
            measures.append({
                "id": eid, "label": "POINT_DEDUCTION",
                "name": f"Trừ {pm.group(1)} điểm giấy phép lái xe",
                "value": pm.group(0).strip()
            })
            for vid in violation_ids:
                relationships.append({"source": vid, "type": "DEDUCTS_POINT", "target": eid})

        # === 9. OBJECT_EQUIPMENT (từ điển) ===
        raw_lower = raw.lower()
        found_equip = set()
        for equip in EQUIPMENT_DICT:
            if equip in raw_lower and equip not in found_equip:
                found_equip.add(equip)
                eid = next_id()
                foundations.append({
                    "id": eid, "label": "OBJECT_EQUIPMENT",
                    "name": equip.capitalize(), "value": equip
                })
                # Nối với VIOLATION nếu có
                for vid in violation_ids:
                    relationships.append({"source": vid, "type": "APPLIES_TO_OBJECT", "target": eid})

        # === 10. DOCUMENT_RECORD (tham chiếu văn bản) ===
        doc_match = re.search(
            r"((?:Nghị định|Thông tư|Luật|Bộ luật)\s+(?:số\s+)?\d+/\d+/[A-ZĐa-zđ0-9-]+)",
            raw, re.IGNORECASE
        )
        if doc_match:
            eid = next_id()
            foundations.append({
                "id": eid, "label": "DOCUMENT_RECORD",
                "name": self._short_name(doc_match.group(1), 60),
                "value": doc_match.group(1)
            })

        # Sửa đổi/bãi bỏ
        amend_match = re.search(
            r"((?:[Ss]ửa đổi|[Bb]ổ sung|[Bb]ãi bỏ|[Tt]hay thế)[^.]*?(?:Điều\s+\d+[a-zđ]?|khoản\s+\d+[a-z]?)[^.]*)",
            raw, re.IGNORECASE
        )
        if amend_match:
            eid = next_id()
            foundations.append({
                "id": eid, "label": "DOCUMENT_RECORD",
                "name": self._short_name(amend_match.group(1), 80),
                "value": self._truncate(amend_match.group(1))
            })

        # Fallback: nếu không trích được gì, tạo LEGAL_CONCEPT
        if not foundations and not rules_actions and not measures and len(raw) > 20:
            eid = next_id()
            foundations.append({
                "id": eid, "label": "LEGAL_CONCEPT",
                "name": self._short_name(raw, 80),
                "value": self._truncate(raw, 500)
            })

        return {
            "Level_3_Foundations": foundations,
            "Level_2_Rules_Actions": rules_actions,
            "Attributes_Measures": measures,
            "Relationships": relationships,
            "metadata": metadata,
            "original_content": content
        }


class GetEntitiesLocal:
    """Drop-in replacement for GetEntitiesByGemini — same process_content interface,
    but runs entirely locally via regex, with no API calls/quota/retry logic needed."""

    def __init__(self):
        self.extractor = ImprovedLocalEntityExtractor()

    def process_content(self, all_chunks, output_file_path=None, num_chunk_per_batch=None):
        article_subjects, clause_money = self.extractor.build_context_maps(all_chunks)
        results = [
            self.extractor.extract_from_chunk(chunk, article_subjects, clause_money)
            for chunk in all_chunks
        ]
        logger.info("GetEntitiesLocal: extracted entities for %d chunks.", len(results))
        return results
