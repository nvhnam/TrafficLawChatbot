import json
import re
from unidecode import unidecode



class DataCleaner:
    def __init__(self):
        self.LEGAL_DOC_PATTERN = r"(Nghị định số \d+/\d+/[A-ZĐa-z0-9-]+|Thông tư số \d+/\d+/[A-ZĐa-z0-9-]+|(?:Bộ )?Luật [A-ZĐ][\w\s,]+?)(?=\s*(?:ngày|tháng|năm|đã|sửa|bổ|$))"
        self.PHYSICAL_DOCS = [
            "giấy phép lái xe", "chứng nhận đăng ký", "tem kiểm định",
            "phù hiệu", "bảo hiểm", "giấy chứng nhận", "biển số",
            "giấy phép lưu hành", "lệnh vận chuyển", "giấy vận tải", "chứng chỉ", "giấy phép kinh doanh", "giấy phép thi công", "giấy phép hoạt động"
        ]

        self.entity_categories = ["Level_3_Foundations", "Level_2_Rules_Actions", "Attributes_Measures"]

    def _read_jsonl(self, input_file):
        data_list = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    data_list.append(json.loads(line))
        return data_list

    def _get_dynamic_doc_name(self, data_list):
        if not data_list:
            return "Văn bản pháp luật"

        preamble_chunk = next((chunk for chunk in data_list if chunk.get("metadata", {}).get("type") == "PREAMBLE"), None)
        if not preamble_chunk:
            preamble_chunk = data_list[0]

        meta_doc_id = preamble_chunk.get("metadata", {}).get("document", "")
        content = preamble_chunk.get("original_content", preamble_chunk.get("content", ""))

        content = re.sub(r'^\[Văn bản:.*?\]\s*', '', content)

        header_part = content.split("Căn cứ")[0] if "Căn cứ" in content else content

        so_hieu = ""
        clean_header = header_part.replace('*', '').replace('#', '')

        # Bắt Số hiệu (Regex giờ sẽ không bị lừa bởi cái thẻ nhân tạo kia nữa)
        so_match = re.search(r"(?:Số|số|So|so|Luật số|Bộ luật số|Luat so|Bo luat so)\s*[:]?\s*([0-9]+(?:\s*/\s*[^\s,;]+)+)", clean_header, re.IGNORECASE)

        if so_match:
            so_hieu = so_match.group(1).strip()
            # Xóa bỏ khoảng trắng dư thừa trong số hiệu
            so_hieu = re.sub(r'\s*/\s*', '/', so_hieu)
        else:
            clean_content = content.replace('*', '').replace('#', '')
            so_match = re.search(r"(?:Số|số|So|so|Luật số|Bộ luật số|Luat so|Bo luat so)\s*[:]?\s*([0-9]+(?:\s*/\s*[^\s,;]+)+)", clean_content, re.IGNORECASE)
            if so_match:
                so_hieu = re.sub(r'\s*/\s*', '/', so_match.group(1).strip())

        blocks = content.split('\n\n')

        for i, block in enumerate(blocks):
            # Dọn dẹp sạch sẽ block
            clean_block = block.replace('*', '').replace('#', '').replace('\n', ' ').strip()
            clean_block = re.sub(r'\s+', ' ', clean_block)
            block_lower = clean_block.lower()

            # 🟢 SỬA: Chuẩn hóa Unidecode để chống lỗi OCR
            block_unaccented = unidecode(block_lower)

            if block_unaccented == "thong tu" or (block_unaccented.startswith("thong tu") and len(block_unaccented) < 20):
                return f"Thông tư số {so_hieu}" if so_hieu else "Thông tư"

            # Kiểm tra dựa trên Unidecode
            is_luat_inline = block_unaccented.startswith("luat ")
            is_bo_luat_inline = block_unaccented.startswith("bo luat ")

            def _clean_law_name(prefix, raw_text):
                text_clean = raw_text.capitalize()

                # Viết hoa số hiệu trong tên (nếu có)
                text_clean = re.sub(r'(\d+/[a-zđ0-9\-]+(?:/[a-zđ0-9\-]+)?)', lambda m: m.group(1).upper(), text_clean, flags=re.IGNORECASE)

                # Fix lại viết hoa chuẩn xác cho tên luật (Dùng regex để không phân biệt hoa/thường)
                text_clean = re.sub(r'(?i)bộ luật', 'Bộ luật', text_clean)
                text_clean = re.sub(r'(?i)hình sự', 'Hình sự', text_clean)
                text_clean = re.sub(r'(?i)dân sự', 'Dân sự', text_clean)
                text_clean = re.sub(r'(?i)lao động', 'Lao động', text_clean)

                full_name = f"{prefix} {text_clean}".strip()

                if so_hieu:
                    if " số " in full_name.lower() or "/" in text_clean:
                        return f"{full_name} (Số {so_hieu})"
                    return f"{full_name} số {so_hieu}"
                return full_name

            # TRƯỜNG HỢP 1: Chữ "Luật" và tên nằm trên CÙNG 1 block (VD: "Bộ luật hình sự")
            if (is_luat_inline or is_bo_luat_inline) and "so:" not in block_unaccented and "so " not in block_unaccented:
                # Dùng regex bóc tách tên luật từ chuỗi gốc để giữ nguyên dấu tiếng Việt
                match = re.match(r'(?i)(?:bộ\s*luật|luật|bo\s*luat|luat)\s+(.*)', clean_block)
                if match:
                    law_type = "Bộ luật" if is_bo_luat_inline else "Luật"
                    law_name = match.group(1).strip()
                    return _clean_law_name(law_type, law_name)

            # TRƯỜNG HỢP 2: Chữ "Luật" và tên nằm ở 2 block KHÁC NHAU (VD: Block 1: "BỘ LUẬT" - Block 2: "HÌNH SỰ")
            if block_unaccented == "luat" or block_unaccented == "bo luat":
                if i + 1 < len(blocks):
                    next_block = blocks[i + 1].replace('*', '').replace('#', '').replace('\n', ' ').strip()
                    next_block = re.sub(r'\s+', ' ', next_block)
                    next_unaccented = unidecode(next_block.lower())

                    if not next_unaccented.startswith("can cu"):
                        law_type = "Bộ luật" if block_unaccented == "bo luat" else "Luật"
                        return _clean_law_name(law_type, next_block)

            # TRƯỜNG HỢP 3: Xử lý Nghị định, Thông tư... (Sử dụng 100% Unidecode)
            if so_hieu:
                so_hieu_unidecode = unidecode(so_hieu).lower()

                if block_unaccented.startswith("nghi dinh") and ("nd" in so_hieu_unidecode or "cp" in so_hieu_unidecode):
                    return f"Nghị định số {so_hieu}"

                if block_unaccented.startswith("thong tu") and "tt" in so_hieu_unidecode:
                    return f"Thông tư số {so_hieu}"

                if block_unaccented.startswith("chi thi") and "ct" in so_hieu_unidecode:
                    return f"Chỉ thị số {so_hieu}"

                if block_unaccented.startswith("quyet dinh") and "qd" in so_hieu_unidecode:
                    return f"Quyết định số {so_hieu}"

                if block_unaccented.startswith("nghi quyet") and "nq" in so_hieu_unidecode:
                    return f"Nghị quyết số {so_hieu}"

        # FALLBACK CUỐI CÙNG
        if so_hieu:
            so_hieu_upper = so_hieu.upper()
            if "QH" in so_hieu_upper:
                return f"Luật số {so_hieu}"
            if "NĐ" in so_hieu_upper or "CP" in so_hieu_upper or "ND" in so_hieu_upper:
                return f"Nghị định số {so_hieu}"
            if "TT" in so_hieu_upper:
                return f"Thông tư số {so_hieu}"
            if "CT" in so_hieu_upper:
                return f"Chỉ thị số {so_hieu}"
            if "QĐ" in so_hieu_upper or "QD" in so_hieu_upper:
                return f"Quyết định số {so_hieu}"
            if "NQ" in so_hieu_upper:
                return f"Nghị quyết số {so_hieu}"

            return f"Văn bản số {so_hieu}"

        return meta_doc_id

    def clean_document_name(self, data_list):
        total_fixed_entities = 0
        total_fixed_metadata = 0
        global_chunk_id = 1
        real_doc_name = self._get_dynamic_doc_name(data_list)

        for data in data_list:
            # 1. Đánh lại chunk_id
            data["chunk_id"] = global_chunk_id
            global_chunk_id += 1

            meta = data.get("metadata", {})
            doc_id = meta.get("document", "")

            # Đảm bảo DOCUMENT_MAPPING hoạt động (tránh lỗi nếu chưa import biến này)

            current_dieu = meta.get("dieu", "")
            current_khoan = meta.get("khoan", "")
            current_diem = meta.get("diem", "")

            if "document" in meta and meta["document"] != real_doc_name:
                data["metadata"]["document"] = real_doc_name
                total_fixed_metadata += 1

                original_content = data.get("original_content", data.get("content", ""))
                context_parts = ["Văn bản: {}".format(real_doc_name)]
                if current_dieu and current_dieu.lower() != "none":
                    context_parts.append("Điều {}".format(current_dieu))
                if current_khoan and current_khoan.lower() != "none":
                    context_parts.append("Khoản {}".format(current_khoan))
                if current_diem and current_diem.lower() != "none":
                    context_parts.append("Điểm {}".format(current_diem))

                context_header = f"[{' - '.join(context_parts)}]\n"
                if not original_content.startswith("[Văn bản:"):
                    if "original_content" in data:
                        data["original_content"] = context_header + original_content
                    else:
                        data["content"] = context_header + original_content

                entity_categories = [
                    "Level_3_Foundations",
                    "Level_2_Rules_Actions",
                    "Attributes_Measures"
                ]

                for category in entity_categories:
                    for entity in data.get(category, []):
                        original_value = str(entity.get("value", "")).strip()
                        val_lower = original_value.lower()
                        new_value = original_value

                        new_value = re.sub(r"(?i)(Nghị định|Thông tư|Luật)\s+Số:\s*", r"\1 số ", new_value)

                        # 3.1 Xử lý các từ khóa chỉ định chung chung
                        if "nghị định này" in val_lower:
                            new_value = original_value.replace("Nghị định này", real_doc_name).replace("nghị định này", real_doc_name)
                        elif "thông tư này" in val_lower:
                            new_value = original_value.replace("Thông tư này", real_doc_name).replace("thông tư này", real_doc_name)
                        elif "luật này" in val_lower:
                            new_value = original_value.replace("Luật này", real_doc_name).replace("luật này", real_doc_name)

                        elif "bộ luật này" in val_lower:
                            new_value = original_value.replace("Bộ luật này", real_doc_name).replace("bộ luật này", real_doc_name)

                        elif val_lower in ["nghị định", "thông tư", "luật", "bộ luật"]:
                            new_value = real_doc_name
                        elif "quyết định này" in val_lower:
                            new_value = original_value.replace("Quyết định này", real_doc_name).replace("quyết định này", real_doc_name)
                        elif "điều này" in val_lower:
                            if current_dieu:
                                str_replace = "Điều {} {}".format(current_dieu, real_doc_name)
                                new_value = original_value.replace("Điều này", str_replace).replace("điều này", str_replace)
                        elif "khoản này" in val_lower:
                            if current_dieu:
                                if current_khoan:
                                    str_replace = "khoản {} Điều {} {}".format(current_khoan, current_dieu, real_doc_name)
                                else:
                                    str_replace = "khoản này Điều {} {}".format(current_dieu, real_doc_name)
                                new_value = original_value.replace("Khoản này", str_replace).replace("khoản này", str_replace)
                        elif "điểm này" in val_lower:
                            if current_dieu:
                                diem_str = f"điểm {current_diem}" if current_diem else "điểm này"
                                khoan_str = f" khoản {current_khoan}" if current_khoan else ""
                                str_replace = f"{diem_str}{khoan_str} Điều {current_dieu} {real_doc_name}"
                                new_value = original_value.replace("Điểm này", str_replace).replace("điểm này", str_replace)

                        val_lower_temp = new_value.lower()
                        if val_lower_temp in ["hàng nguy hiểm (hàng hóa nguy hiểm)", "hàng nguy hiểm"]:
                            new_value = "hàng hóa nguy hiểm"

                        if re.search(r"(?i)\b(điều|khoản|điểm)\s+(\d+[a-z]?|[a-zđ])\b", new_value.lower()):
                            if not re.search(r"(?i)(nghị định|bộ luật|luật|thông tư)", new_value.lower()):
                                new_value = f"{new_value} của {real_doc_name}"

                        if new_value != original_value:
                            entity["value"] = new_value
                            # Nếu có trường name, cũng update name để merge node được chuẩn
                            if "name" in entity:
                                entity["name"] = new_value
                            total_fixed_entities += 1

        return data_list

    def resolve_amendment_context(self, data_list):
        total_auto_context = 0
        total_label_fixed = 0

        current_target_doc = None
        current_amendment_dieu = None

        for data in data_list:
            meta = data.get("metadata", {})
            content = data.get("original_content", data.get("content", ""))

            real_doc_name = meta.get("document", "")
            current_dieu = meta.get("dieu", "")

            if current_dieu != current_amendment_dieu:
                current_target_doc = None
                current_amendment_dieu = current_dieu

            content_lower = content.lower()
            if "sửa đổi" in content_lower or "bãi bỏ" in content_lower or "thay thế" in content_lower:
                matches = re.findall(self.LEGAL_DOC_PATTERN, content)
                for match in matches:
                    doc_found = match.strip()
                    if doc_found != real_doc_name:
                        current_target_doc = doc_found
                        break

            for category in self.entity_categories:
                for entity in data.get(category, []):
                    label = entity.get("label", "")
                    original_value = str(entity.get("value", "")).strip()
                    val_lower = original_value.lower()

                    if label == "DOCUMENT_RECORD" and val_lower.startswith("cụm từ"):
                        entity['label'] = "TEXT_SEGMENT"
                        total_label_fixed += 1
                        continue

                    if label == "DOCUMENT_RECORD" and current_target_doc:
                        if any(k in val_lower for k in ["điều", "khoản", "điểm"]):
                            clean_value = re.sub(r"\s*của (Nghị định số|Bộ luật|Luật|Thông tư).*$", "", original_value)
                            entity['value'] = f"{clean_value} của {current_target_doc}"
                            total_auto_context += 1

        return data_list

    def refine_graph_schema(self, data_list):
        total_refined_subjects = 0
        total_refined_docs = 0

        for data in data_list:
            content_lower = data.get("original_content", data.get("content", "")).lower()
            dieu_name = data.get("metadata", {}).get("dieu", "")

            # Quét phương tiện
            vehicle_tags = []
            if "xe ô tô" in content_lower or "máy kéo" in content_lower:
                vehicle_tags.append("ô tô")
            if "xe mô tô" in content_lower or "xe gắn máy" in content_lower:
                vehicle_tags.append("mô tô, xe máy")
            if "xe máy chuyên dùng" in content_lower:
                vehicle_tags.append("xe máy chuyên dùng")
            if "xe thô sơ" in content_lower or "xe đạp" in content_lower:
                vehicle_tags.append("xe đạp, xe thô sơ")
            if "xe cứu hộ" in content_lower or "xe cứu thương" in content_lower:
                vehicle_tags.append("xe ưu tiên, cứu hộ")

            context_tag = f" ({', '.join(vehicle_tags)})" if vehicle_tags else ""

            general_context_tag = ""
            if "kết cấu hạ tầng" in content_lower or "đường bộ" in content_lower:
                general_context_tag = " (hạ tầng đường bộ)"
            if "trạm thu phí" in content_lower or "thanh toán điện tử" in content_lower:
                general_context_tag = " (thu phí ETC)"
            if "đào tạo" in content_lower or "sát hạch" in content_lower:
                general_context_tag = " (đào tạo lái xe)"

            for category in self.entity_categories:
                for entity in data.get(category, []):
                    label = entity.get("label", "")
                    original_value = str(entity.get("value", "")).strip()
                    val_lower = original_value.lower()

                    if label == "SUBJECT" and val_lower in ["người điều khiển xe", "chủ phương tiện", "người điều khiển phương tiện"]:
                        if context_tag and context_tag not in original_value:
                            entity['value'] = original_value + context_tag
                            if "name" in entity: entity["name"] = entity["value"]
                            total_refined_subjects += 1

                    elif label == "SUBJECT" and val_lower in ["cá nhân", "tổ chức", "cá nhân, tổ chức"]:
                        if general_context_tag and general_context_tag not in original_value:
                            entity['value'] = original_value + general_context_tag
                            if "name" in entity: entity["name"] = entity["value"]
                            total_refined_subjects += 1

                    if label == "DOCUMENT_RECORD":
                        if any(doc in val_lower for doc in self.PHYSICAL_DOCS):
                            if not any(law in val_lower for law in ['nghị định', 'luật', "thông tư"]):
                                entity['label'] = "PHYSICAL_DOCUMENT"
                                total_refined_docs += 1

        return data_list

    def link_isolated_islands(self, data_list):
        total_linked = 0

        violation_map = {}
        for data in data_list:
            meta = data.get("metadata", {})
            dieu = str(meta.get("dieu") or "").strip().lower()
            khoan = str(meta.get("khoan") or "").strip().lower()
            diem = str(meta.get("diem") or "").strip().lower()

            if dieu not in violation_map:
                violation_map[dieu] = {}
            if khoan not in violation_map[dieu]:
                violation_map[dieu][khoan] = {}
            if diem not in violation_map[dieu][khoan]:
                violation_map[dieu][khoan][diem] = []

            for category in self.entity_categories:
                for entity in data.get(category, []):
                    val = str(entity.get("value", ""))
                    if entity.get("label") == "VIOLATION" and "quy định tại" not in val.lower():
                        violation_map[dieu][khoan][diem].append(val)

        def get_real_violations(d_dieu, d_khoan, d_diem=""):
            results = []
            try:
                d_dieu = str(d_dieu).lower()
                d_khoan = str(d_khoan).lower()
                d_diem = str(d_diem).lower()

                if d_diem:
                    results.extend(violation_map.get(d_dieu, {}).get(d_khoan, {}).get(d_diem, []))
                elif d_khoan:
                    for k, v_list in violation_map.get(d_dieu, {}).get(d_khoan, {}).items():
                        results.extend(v_list)
            except Exception:
                pass
            return results

        for data in data_list:
            for category in self.entity_categories:
                for entity in data.get(category, []):
                    val_lower = str(entity.get("value", "")).lower()

                    if any(kw in val_lower for kw in ["quy định tại", "vi phạm tại", "tương ứng tại"]):
                        real_texts = []
                        dieu_matches = list(re.finditer(r"điều\s+(\d+[a-z]?)", val_lower))
                        if dieu_matches:
                            # Lấy Điều cuối cùng làm mặc định (VD: điểm a khoản 1, điểm b khoản 2 Điều 5 -> Mặc định là Điều 5)
                            default_dieu = dieu_matches[-1].group(1)

                            # Quét các cụm "(điểm A, B, C...) khoản X (Điều Y)"
                            for m in re.finditer(r"(?:điểm\s+(.*?))?khoản\s+(\d+[a-z]?)(?:\s*(?:của\s+)?điều\s+(\d+[a-z]?))?", val_lower):
                                diem_str = m.group(1)  # Ví dụ: "b, điểm c "
                                d_khoan = m.group(2)  # Ví dụ: "2"
                                d_dieu = m.group(3) if m.group(3) else default_dieu  # Ví dụ: "5"

                                if diem_str:
                                    # Dùng Regex biên từ (\b) để xúc sạch mọi chữ cái đơn (a, b, c, đ...)
                                    diems = re.findall(r"\b([a-zđ])\b", diem_str)
                                    for d_diem in diems:
                                        real_texts.extend(get_real_violations(d_dieu, d_khoan, d_diem))
                                else:
                                    # Không nhắc đến điểm, chỉ nhắc đến khoản
                                    real_texts.extend(get_real_violations(d_dieu, d_khoan, ""))

                        # Nếu tìm thấy nội dung thật, đắp thẳng vào chuỗi
                        if real_texts:
                            # Xóa trùng lặp (nếu có) nhưng vẫn giữ nguyên thứ tự
                            seen = set()
                            unique_texts = []
                            for text in real_texts:
                                if text not in seen:
                                    seen.add(text)
                                    unique_texts.append(text)

                            joined_text = "; ".join(unique_texts)
                            new_value = f"{entity['value']} (Cụ thể: {joined_text})"
                            entity['value'] = new_value
                            if "name" in entity: entity["name"] = new_value
                            total_linked += 1

        return data_list

    def extract_legal_hierarchy(self, data_list):
        if not data_list:
            return data_list

        preamble_chunk = next((chunk for chunk in data_list if chunk.get("metadata", {}).get("type") == "PREAMBLE"), None)

        if not preamble_chunk:
            return data_list

        content = preamble_chunk.get("original_content", preamble_chunk.get("content", ""))
        real_doc_name = preamble_chunk.get("metadata", {}).get("document", "Văn bản hiện tại")

        cleaned_foundations = [e for e in preamble_chunk.get("Level_3_Foundations", []) if not str(e.get("id")).startswith("doc_")]
        cleaned_relations = [r for r in preamble_chunk.get("Relationships", []) if not (str(r.get("source")).startswith("doc_") or str(r.get("target")).startswith("doc_"))]

        blocks = content.split('\n\n')

        can_cu_matches = []
        for block in blocks:
            clean_block = block.replace('*', '').replace('\n', ' ').strip()

            if clean_block.lower().startswith("căn cứ"):
                docs_string = clean_block[7:].strip()

                # 1. Chặt theo dấu chấm phẩy (;)
                parts = docs_string.split(';')
                for part in parts:
                    clean_doc = part.strip()
                    if not clean_doc:
                        continue

                    # 2. Xử lý trường hợp "được sửa đổi, bổ sung bởi..."
                    if "được sửa đổi" in clean_doc.lower() or "sửa đổi, bổ sung bởi" in clean_doc.lower():
                        sub_parts = re.split(r"(?i)\s+được sửa đổi, bổ sung(?: một số điều)?(?: bởi| theo)?\s+", clean_doc)
                        if len(sub_parts) > 0:
                            can_cu_matches.append(sub_parts[0].strip())  # Base law
                            if len(sub_parts) > 1:
                                # Chẻ các luật sửa đổi bằng dấu phẩy hoặc "và"
                                amending_laws = re.split(r"(?i),\s*|\s+và\s+", sub_parts[1])
                                for al in amending_laws:
                                    if al.strip(): can_cu_matches.append(al.strip())

                    # 3. Xử lý trường hợp dùng chữ "và" hoặc "," để nối 2 Luật độc lập
                    else:
                        # Tuyệt chiêu Lookahead: Cắt ở dấu phẩy hoặc chữ "và", NẾU theo sau là "Luật", "Nghị định"
                        nested_parts = re.split(r"(?i)(?:,\s*|\s+và\s+)(?=Luật\b|Nghị định\b|Bộ luật\b)", clean_doc)
                        for np in nested_parts:
                            if np.strip(): can_cu_matches.append(np.strip())

        # Lọc bỏ trùng lặp (nếu có) nhưng giữ nguyên thứ tự
        seen = set()
        unique_matches = []
        for doc in can_cu_matches:
            if doc not in seen:
                seen.add(doc)
                unique_matches.append(doc)

        if unique_matches:
            doc_entity_id = "doc_root_0"
            cleaned_foundations.append({
                "id": doc_entity_id,
                "label": "DOCUMENT_RECORD",
                "name": real_doc_name,
                "value": real_doc_name
            })

            for idx, target_doc_name in enumerate(unique_matches):
                target_id = f"doc_base_{idx}"
                cleaned_foundations.append({
                    "id": target_id,
                    "label": "DOCUMENT_RECORD",
                    "name": target_doc_name,
                    "value": target_doc_name
                })
                cleaned_relations.append({
                    "source": doc_entity_id,
                    "type": "BASES_ON",
                    "target": target_id
                })

        preamble_chunk["Level_3_Foundations"] = cleaned_foundations
        preamble_chunk["Relationships"] = cleaned_relations
        return data_list

    def clean_data(self, data_list):
        # Đọc dữ liệu lên RAM
        # data_list = self._read_jsonl(input_file)

        # Chạy Pipeline
        data_list = self.clean_document_name(data_list)
        data_list = self.resolve_amendment_context(data_list)
        data_list = self.refine_graph_schema(data_list)
        data_list = self.extract_legal_hierarchy(data_list)
        data_list = self.link_isolated_islands(data_list)

        return data_list