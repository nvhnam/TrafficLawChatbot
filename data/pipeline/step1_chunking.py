"""
Bước 1: Tách văn bản pháp luật (Markdown) thành các chunk nhỏ.

Mỗi chunk tương ứng với một đơn vị pháp lý nhỏ nhất có ý nghĩa:
Điểm > Khoản > Điều > Mục > Chương > Phần.

Metadata của mỗi chunk ghi lại vị trí chính xác trong cây phân cấp văn bản,
giúp việc truy xuất nguồn gốc (trích dẫn) chính xác hơn khi chatbot trả lời.
"""

import re
import json
import uuid
import os
import logging

logger = logging.getLogger(__name__)


class LegalSemanticSplitter:
    """
    Tách văn bản pháp luật Markdown thành các chunk theo cấu trúc phân cấp:
    Phần -> Chương -> Mục -> Điều -> Khoản -> Điểm.

    Mỗi chunk đầu ra chứa:
    - content: nội dung văn bản (có bơm ngữ cảnh Chương/Mục vào đầu)
    - metadata: vị trí trong cây phân cấp (document, phan, chuong, muc, dieu, khoan, diem, type)
    """

    def __init__(self, document_name):
        """
        Khởi tạo bộ tách.

        Tham số:
            document_name: Tên định danh của văn bản (VD: "100.signed", "123-2021nd-cp")
        """
        self.document_name = document_name

        # Trạng thái theo dõi vị trí hiện tại trong cây phân cấp
        self.current_phan = None
        self.current_chuong = None
        self.current_muc = None
        self.current_dieu = None

        # Regex nhận diện các cấp cấu trúc văn bản pháp luật
        self.PHAN_PATTERN = re.compile(
            r"^(?:Phần|PHẦN)\s+(?:thứ\s+)?(nhất|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|"
            r"một|I{1,3}V?|VI{0,3}|IX|X{0,3})\b",
            re.IGNORECASE | re.MULTILINE
        )
        self.CHUONG_PATTERN = re.compile(
            r"^(?:Chương|CHƯƠNG)\s+([IVXLCDM]+|\d+)\b",
            re.IGNORECASE | re.MULTILINE
        )
        self.MUC_PATTERN = re.compile(
            r"^(?:Mục|MỤC)\s+(\d+)\b",
            re.IGNORECASE | re.MULTILINE
        )
        self.DIEU_PATTERN = re.compile(
            r"^(?:#{1,4}\s+)?Điều\s+(\d+[a-zđ]?)\.?\s*",
            re.MULTILINE
        )
        self.KHOAN_PATTERN = re.compile(
            r"^(\d+[a-z]?)\.\s+",
            re.MULTILINE
        )
        self.DIEM_PATTERN = re.compile(
            r"^([a-zđ]+)\)\s+",
            re.MULTILINE
        )

    def _build_context_header(self):
        """
        Xây dựng chuỗi ngữ cảnh từ vị trí hiện tại trong cây phân cấp.
        Chuỗi này được bơm vào đầu mỗi chunk để cải thiện chất lượng tìm kiếm vector.

        Ví dụ: "[Phần thứ nhất, Chương II: Xử phạt VPHC, Mục 1: Xe ô tô]"
        """
        parts = []
        if self.current_phan:
            parts.append(self.current_phan)
        if self.current_chuong:
            parts.append(self.current_chuong)
        if self.current_muc:
            parts.append(self.current_muc)
        if parts:
            return "[" + ", ".join(parts) + "]\n"
        return ""

    def _build_chunk(self, content, dieu=None, khoan=None, diem=None, chunk_type="LEGAL_RULE"):
        """
        Tạo một chunk với đầy đủ metadata và ngữ cảnh.

        Tham số:
            content: Nội dung văn bản gốc của chunk
            dieu: Số điều (VD: "5", "5a")
            khoan: Số khoản (VD: "1", "2a")
            diem: Ký hiệu điểm (VD: "a", "b", "đ")
            chunk_type: Loại chunk (PREAMBLE, LEGAL_RULE, ACTION_BLOCK, ...)
        """
        context_header = self._build_context_header()
        full_content = f"[Văn bản: {self.document_name}, Điều {dieu or '?'}] {context_header}{content}"

        return {
            "content": full_content.strip(),
            "metadata": {
                "document": self.document_name,
                "phan": self.current_phan,
                "chuong": self.current_chuong,
                "muc": self.current_muc,
                "dieu": dieu,
                "khoan": khoan,
                "diem": diem,
                "type": chunk_type,
                "chunk_uuid": uuid.uuid4().hex
            }
        }

    def _clean_markdown(self, text):
        """
        Dọn dẹp các nhiễu từ file Markdown (số trang, header dư thừa, ...).
        """
        # Xoá các dòng chỉ chứa số trang (## 2, ## 15, ...)
        text = re.sub(r"^##\s+\d+\s*$", "", text, flags=re.MULTILINE)
        # Xoá dấu ## dư thừa
        text = re.sub(r"^##\s*_{3,}\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^##\s*$", "", text, flags=re.MULTILINE)
        # Xoá dòng trống liên tiếp
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _split_articles(self, text):
        """
        Tách văn bản thành danh sách các Điều.
        Mỗi phần tử là tuple (số_điều, nội_dung).
        Phần trước Điều đầu tiên được gán số điều là None (preamble).
        """
        matches = list(self.DIEU_PATTERN.finditer(text))
        if not matches:
            return [(None, text)]

        articles = []
        # Phần trước Điều đầu tiên (preamble)
        preamble = text[:matches[0].start()].strip()
        if preamble:
            articles.append((None, preamble))

        for i, match in enumerate(matches):
            dieu_number = match.group(1)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            article_text = text[start:end].strip()
            articles.append((dieu_number, article_text))

        return articles

    def _split_clauses(self, article_text, dieu):
        """
        Tách một Điều thành các Khoản.
        Nếu không tìm thấy Khoản, trả về toàn bộ Điều như một chunk duy nhất.
        """
        matches = list(self.KHOAN_PATTERN.finditer(article_text))
        if not matches:
            return [self._build_chunk(article_text, dieu=dieu)]

        chunks = []
        # Phần mở đầu của Điều (trước Khoản 1)
        header = article_text[:matches[0].start()].strip()
        if header and len(header) > 30:
            chunks.append(self._build_chunk(header, dieu=dieu, chunk_type="ARTICLE_HEADER"))

        for i, match in enumerate(matches):
            khoan_number = match.group(1)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(article_text)
            clause_text = article_text[start:end].strip()

            # Tiếp tục tách thành Điểm nếu có
            point_chunks = self._split_points(clause_text, dieu, khoan_number)
            if point_chunks:
                chunks.extend(point_chunks)
            else:
                chunks.append(self._build_chunk(clause_text, dieu=dieu, khoan=khoan_number))

        return chunks

    def _split_points(self, clause_text, dieu, khoan):
        """
        Tách một Khoản thành các Điểm (a, b, c, đ, ...).
        Nếu không có Điểm, trả về None để hàm gọi tự xử lý.
        """
        matches = list(self.DIEM_PATTERN.finditer(clause_text))
        if not matches:
            return None

        chunks = []
        # Phần mở đầu của Khoản (trước Điểm a)
        header = clause_text[:matches[0].start()].strip()
        if header and len(header) > 20:
            chunks.append(self._build_chunk(header, dieu=dieu, khoan=khoan, chunk_type="CLAUSE_HEADER"))

        for i, match in enumerate(matches):
            diem_letter = match.group(1)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(clause_text)
            point_text = clause_text[start:end].strip()
            chunks.append(self._build_chunk(point_text, dieu=dieu, khoan=khoan, diem=diem_letter))

        return chunks

    def _update_hierarchy(self, text):
        """
        Quét văn bản để cập nhật vị trí hiện tại trong cây phân cấp
        (Phần, Chương, Mục). Được gọi trước khi xử lý mỗi Điều.
        """
        for line in text.split("\n"):
            line_clean = line.strip()

            phan_match = self.PHAN_PATTERN.match(line_clean)
            if phan_match:
                self.current_phan = line_clean
                self.current_chuong = None
                self.current_muc = None
                continue

            chuong_match = self.CHUONG_PATTERN.match(line_clean)
            if chuong_match:
                # Lấy cả tiêu đề Chương (dòng tiếp theo nếu có)
                self.current_chuong = line_clean
                self.current_muc = None
                continue

            muc_match = self.MUC_PATTERN.match(line_clean)
            if muc_match:
                self.current_muc = line_clean
                continue

    def split(self, markdown_text):
        """
        Hàm chính: Tách toàn bộ văn bản Markdown thành danh sách các chunk.

        Tham số:
            markdown_text: Nội dung file Markdown đầy đủ

        Trả về:
            Danh sách các dict, mỗi dict chứa 'content' và 'metadata'
        """
        cleaned = self._clean_markdown(markdown_text)
        articles = self._split_articles(cleaned)
        all_chunks = []

        for dieu, article_text in articles:
            # Cập nhật ngữ cảnh phân cấp
            self._update_hierarchy(article_text)

            if dieu is None:
                # Phần preamble (mở đầu trước Điều 1)
                chunk = self._build_chunk(article_text, chunk_type="PREAMBLE")
                all_chunks.append(chunk)
            else:
                # Tách Điều thành Khoản -> Điểm
                chunks = self._split_clauses(article_text, dieu)
                all_chunks.extend(chunks)

        logger.info(f"Đã tách '{self.document_name}' thành {len(all_chunks)} chunks")
        return all_chunks


def run_chunking(input_file, output_file):
    """
    Thực thi bước chunking cho một file markdown.

    Tham số:
        input_file: Đường dẫn tuyệt đối tới file .md đầu vào
        output_file: Đường dẫn tuyệt đối tới file .json đầu ra
    """
    doc_name = os.path.splitext(os.path.basename(input_file))[0]

    with open(input_file, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    splitter = LegalSemanticSplitter(doc_name)
    chunks = splitter.split(markdown_text)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"[Bước 1] Đã tách {len(chunks)} chunks -> {output_file}")
    return chunks


if __name__ == "__main__":
    import sys
    from config import INPUT_DIR, CHUNKS_DIR

    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        # Mặc định xử lý tất cả file .md trong thư mục input/
        md_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".md")]
        if not md_files:
            print(f"Không tìm thấy file .md nào trong {INPUT_DIR}")
            sys.exit(1)
        filename = md_files[0]

    input_path = os.path.join(INPUT_DIR, filename)
    output_name = os.path.splitext(filename)[0] + ".json"
    output_path = os.path.join(CHUNKS_DIR, output_name)

    run_chunking(input_path, output_path)
