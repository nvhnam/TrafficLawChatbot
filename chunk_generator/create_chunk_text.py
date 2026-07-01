import re


class LegalSemanticSplitter:
    def __init__(self):
        pass

    def _process_accumulated_dieu(self, current_dieu_lines, doc_name, chunks, current_phan, current_chuong, current_muc):
        if not current_dieu_lines: return
        dieu_text = '\n'.join(current_dieu_lines).strip()

        dieu_match = re.search(r'^(?i)(?:#+\s*)?(?:Điều|Dieu|Đieu)\s+(\d+[a-zA-Z]*)[.,]\s*(?:[\*\#\s]*)(.*?)(?:[\*\#\s]*)(?=\n|$)', dieu_text)
        if not dieu_match: return

        dieu_num = dieu_match.group(1)
        dieu_title = dieu_match.group(2).strip()
        dieu_content = dieu_text[dieu_match.end():].strip()

        khoan_splits = re.split(r'\n(?=\d+\.\s*)', '\n' + dieu_content)

        if len(khoan_splits) == 1:
            diem_splits = re.split(r'\n(?=(?i)[a-zđ]\)\s+)', '\n' + dieu_content)
            if len(diem_splits) > 1:
                dieu_intro_text = diem_splits[0].strip()
                for diem_text in diem_splits[1:]:
                    diem_text = diem_text.strip()
                    diem_match = re.search(r'^(?i)([a-zđ])\)\s+', diem_text)
                    diem_char = diem_match.group(1) if diem_match else None

                    final_chunk_text = f"Điều {dieu_num}. {dieu_title}\n"
                    if dieu_intro_text: final_chunk_text += f"{dieu_intro_text}\n"
                    final_chunk_text += diem_text

                    chunks.append(self._build_chunk(doc_name, dieu_num, None, diem_char, final_chunk_text,
                                                    phan=current_phan, chuong=current_chuong, muc=current_muc))
            else:
                chunks.append(self._build_chunk(doc_name, dieu_num, None, None, f"Điều {dieu_num}. {dieu_title}\n{dieu_content}",
                                                phan=current_phan, chuong=current_chuong, muc=current_muc))
            return

        dieu_intro_text = khoan_splits[0].strip()

        for khoan_text in khoan_splits[1:]:
            khoan_text = khoan_text.strip()
            if not khoan_text: continue

            khoan_match = re.search(r'^(\d+)\.\s*', khoan_text)
            if not khoan_match: continue
            khoan_num = khoan_match.group(1)

            is_amendment = bool(re.search(r'^(?i)\d+\.\s+(Sửa đổi|Sua doi|Bổ sung|Bo sung|Bãi bỏ|Bai bo|Thay thế|Thay the)', khoan_text))
            diem_splits = re.split(r'\n(?=(?i)[a-zđ]\)\s+)', '\n' + khoan_text)

            if len(diem_splits) == 1:
                final_chunk_text = f"Điều {dieu_num}. {dieu_title}\n"
                if dieu_intro_text: final_chunk_text += f"{dieu_intro_text}\n"
                final_chunk_text += khoan_text
                chunks.append(self._build_chunk(doc_name, dieu_num, khoan_num, None, final_chunk_text, is_action_block=is_amendment,
                                                phan=current_phan, chuong=current_chuong, muc=current_muc))
            else:
                khoan_lead = diem_splits[0].strip()
                for diem_text in diem_splits[1:]:
                    diem_text = diem_text.strip()
                    diem_match = re.search(r'^(?i)([a-zđ])\)\s+', diem_text)
                    diem_char = diem_match.group(1) if diem_match else None

                    is_sub_amendment = bool(re.search(r'^(?i)[a-zđ]\)\s+(Sửa đổi|Sua doi|Bổ sung|Bo sung|Bãi bỏ|Bai bo|Thay thế|Thay the)', diem_text))

                    final_chunk_text = f"Điều {dieu_num}. {dieu_title}\n"
                    if dieu_intro_text: final_chunk_text += f"{dieu_intro_text}\n"
                    final_chunk_text += f"{khoan_lead}\n{diem_text}"

                    chunks.append(self._build_chunk(doc_name, dieu_num, khoan_num, diem_char, final_chunk_text, is_action_block=is_sub_amendment,
                                                    phan=current_phan, chuong=current_chuong, muc=current_muc))

    def split_text(self, text, doc_name):
        text = re.split(r'(?i)\n\s*(?:Nơi nhận:|TM\. CHÍNH PHỦ|VĂN PHÒNG CHÍNH PHỦ XUẤT BẢN)', text)[0].strip()

        chunks = []

        phu_luc_splits = re.split(r'\n(?=(?i)(?:\*\*|#+\s*)?(?:Phụ lục|Phu luc)\s+)', text)
        main_legal_text = phu_luc_splits[0]
        phu_luc_texts = phu_luc_splits[1:]

        current_phan = None
        current_chuong = None
        current_muc = None

        lines = main_legal_text.split('\n')

        current_dieu_lines = []
        preamble_lines = []
        found_first_dieu = False

        for line in lines:
            line_stripped = line.strip()

            if re.match(r'^(?i)PHẦN\s+(THỨ\s+)?[A-ZĐ]+', line_stripped):
                current_phan = line_stripped
                continue

            if re.match(r'^(?i)Chương\s+[IVXLCDM]+', line_stripped):
                current_chuong = line_stripped
                current_muc = None
                continue

            if re.match(r'^(?i)Mục\s+\d+', line_stripped):
                current_muc = line_stripped
                continue

            if re.match(r'^(?i)(?:#+\s*)?(?:Điều|Dieu|Đieu)\s+\d+[a-zA-Z]*[.,]', line_stripped):
                found_first_dieu = True
                self._process_accumulated_dieu(current_dieu_lines, doc_name, chunks, current_phan, current_chuong, current_muc)
                current_dieu_lines = [line]
            else:
                if found_first_dieu:
                    if current_dieu_lines:
                        current_dieu_lines.append(line)
                else:
                    preamble_lines.append(line)

        self._process_accumulated_dieu(current_dieu_lines, doc_name, chunks, current_phan, current_chuong, current_muc)

        preamble_text = '\n'.join(preamble_lines).strip()
        if preamble_text:
            chunks.insert(0, {
                "metadata": {
                    "document": doc_name,
                    "phan": None,
                    "chuong": None,
                    "muc": None,
                    "dieu": "Phần mở đầu",
                    "khoan": None,
                    "diem": None,
                    "type": "PREAMBLE"
                },
                "content": preamble_text
            })

        for pl_text in phu_luc_texts:
            pl_text = pl_text.strip()
            pl_match = re.search(r'^(?i)(?:\*\*|#+\s*)?((?:Phụ lục|Phu luc)\s+[A-Za-z0-9]+)', pl_text)
            pl_name = pl_match.group(1) if pl_match else "Phụ lục"

            table_pattern = re.compile(r'(?:^[ \t]*\|.*(?:\n|$))+', re.MULTILINE)
            tables = table_pattern.finditer(pl_text)

            last_end = 0
            table_count = 1

            for match in tables:
                start = match.start()
                end = match.end()

                text_before_table = pl_text[last_end:start].strip()
                if text_before_table:
                    chunks.append(self._build_chunk(doc_name,
                                                    dieu=pl_name, khoan=None, diem=None,
                                                    text=f"{pl_name}\n{text_before_table}",
                                                    chunk_type="APPENDIX_TEXT"
                                                    ))

                table_content = match.group(0).strip()
                context_header = ""
                lines_before = text_before_table.split('\n')
                if lines_before and lines_before[-1].strip():
                    context_header = lines_before[-1].strip() + "\n"

                chunks.append(self._build_chunk(doc_name,
                                                dieu=pl_name, khoan=f"Bảng {table_count}", diem=None,
                                                text=f"{pl_name}\n{context_header}{table_content}",
                                                chunk_type="APPENDIX_TABLE"
                                                ))

                last_end = end
                table_count += 1

            text_after_tables = pl_text[last_end:].strip()
            if text_after_tables:
                chunks.append(self._build_chunk(doc_name,
                                                dieu=pl_name, khoan="Phần cuối", diem=None,
                                                text=f"{pl_name}\n{text_after_tables}",
                                                chunk_type="APPENDIX_TEXT"
                                                ))

        return chunks

    # 🚀 CẬP NHẬT HÀM BUILD_CHUNK ĐỂ NHẬN THÊM METADATA PHÂN CẤP
    def _build_chunk(self, doc_name, dieu, khoan, diem, text, is_action_block=False, chunk_type=None, phan=None, chuong=None, muc=None):
        ctype = chunk_type if chunk_type else ("ACTION_BLOCK" if is_action_block else "LEGAL_RULE")

        # [BÍ QUYẾT GraphRAG]: Bơm Tên Chương vào đầu Text để Vector Search luôn bắt trúng ngữ cảnh
        context_header = ""
        if chuong: context_header += f"[{chuong}]\n"
        if muc: context_header += f"[{muc}]\n"

        final_content = context_header + text if context_header else text

        return {
            "metadata": {
                "document": doc_name,
                "phan": phan,  # Thêm Metadata Phần
                "chuong": chuong,  # Thêm Metadata Chương
                "muc": muc,  # Thêm Metadata Mục
                "dieu": dieu,
                "khoan": khoan,
                "diem": diem,
                "type": ctype
            },
            "content": final_content
        }