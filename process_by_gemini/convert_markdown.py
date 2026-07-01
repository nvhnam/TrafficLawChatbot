import random
import time
import os
import glob
import io
import logging
from datetime import datetime
from pypdf import PdfReader, PdfWriter
import google.genai as genai
from google.genai import types
from config import API_KEY, MODEL_PRO

logger = logging.getLogger(__name__)

class PdfToMarkdownConverter(object):
    def __init__(self):
        self.model_name = MODEL_PRO
        self.api_key = API_KEY
        self.client = genai.Client(api_key=self.api_key)

        self.prompt = """
        Bạn là một chuyên gia số hóa văn bản pháp luật Việt Nam.
        Nhiệm vụ: Chuyển đổi chính xác 100% nội dung trong file PDF này thành định dạng Markdown thuần túy.

        YÊU CẦU NGHIÊM NGẶT (PHẢI TUÂN THỦ 100%):
        1. ĐỊNH DẠNG TEXT:
           - Giữ nguyên toàn bộ nội dung luật, không tóm tắt, không bình luận.
           - Cấu trúc thẻ Heading: Tên Chương dùng `##`, Tên Điều dùng `###`.
           - TUYỆT ĐỐI KHÔNG thêm câu giao tiếp (VD: "Đây là kết quả..."). Chỉ trả về raw Markdown.

        2. LỌC RÁC (NOISE REDUCTION):
           - BỎ QUA HOÀN TOÀN các Header/Footer của trang (ví dụ: số trang 1, 2, 3... nằm trơ trọi, dấu mộc, chữ ký). Không được đưa chúng vào Markdown.

        3. XỬ LÝ BẢNG BIỂU PHỨC TẠP (QUAN TRỌNG NHẤT):
           - Mọi bảng biểu phải được vẽ bằng Markdown Table.
           - LƯU Ý: Markdown không hỗ trợ gộp ô (Colspan/Rowspan). Nếu PDF có bảng gộp cột ở Tiêu đề (Header), bạn BẮT BUỘC PHẢI "làm phẳng" (flatten) nó thành 1 hàng Tiêu đề duy nhất bằng cách gộp tên các cột lại với nhau cho rõ nghĩa.
           - Ví dụ bảng tốc độ: Cột 1 là "Loại xe", Cột 2 là "Tốc độ (Đường đôi)", Cột 3 là "Tốc độ (Đường 2 chiều)". TUYỆT ĐỐI không được để hàng Sub-header rơi xuống làm hàng dữ liệu.

        4. GHÉP NỐI: Nếu đoạn cuối của trang bị cắt ngang giữa câu, hãy trích xuất đúng phần bị cắt đó, hệ thống sẽ tự ghép nối sau.
        """

    def _split_pdf_in_memory(self, pdf_bytes, chunk_size=3):
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            total_pages = len(reader.pages)
            split_bytes_list = []

            for start in range(0, total_pages, chunk_size):
                end = min(start + chunk_size, total_pages)
                writer = PdfWriter()

                for page_num in range(start, end):
                    writer.add_page(reader.pages[page_num])

                output_stream = io.BytesIO()
                writer.write(output_stream)
                split_bytes_list.append(output_stream.getvalue())

            return split_bytes_list
        except Exception as e:
            logger.error("Lỗi cắt PDF trong bộ nhớ: %s", e)
            return []

    def _call_api_with_retry(self, chunk_bytes, max_retries=3):
        delay = 5
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        types.Part.from_bytes(data=chunk_bytes, mime_type="application/pdf"),
                        self.prompt,
                    ],
                )
                return response.text

            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "resource" in error_msg or "quota" in error_msg:
                    logger.critical("Đã hết hạn mức API (QUOTA_EXCEEDED).")
                    return "QUOTA_EXCEEDED"

                logger.error("Lỗi API (Thử lại %d/3): %s", attempt + 1, e)
                time.sleep(10 if "504" in error_msg or "503" in error_msg else 5)

        return None

    def process_content(self, pdf_bytes, output_file_path, chunk_size=3):
        progress_file = f"{output_file_path}.progress"
        temp_data_file = f"{output_file_path}.temp"

        file_identifier = os.path.basename(output_file_path)

        chunk_bytes_list = self._split_pdf_in_memory(pdf_bytes, chunk_size=chunk_size)
        if not chunk_bytes_list:
            return None

        total_chunks = len(chunk_bytes_list)

        while True:
            start_idx = 0
            if os.path.exists(progress_file):
                with open(progress_file, "r") as f:
                    content = f.read().strip()
                    start_idx = int(content) if content.isdigit() else 0

            if start_idx >= total_chunks:
                break

            remaining_chunks = chunk_bytes_list[start_idx:]
            current_count = start_idx
            is_crashed = False

            with open(temp_data_file, "a", encoding="utf-8") as f_temp:
                for chunk_bytes in remaining_chunks:
                    result_text = self._call_api_with_retry(chunk_bytes)

                    if result_text == "QUOTA_EXCEEDED":
                        return "QUOTA_EXCEEDED"

                    if result_text is None:
                        is_crashed = True
                        break

                    f_temp.write(result_text.strip() + "\n\n")
                    f_temp.flush()

                    current_count += 1
                    with open(progress_file, "w") as f_prog:
                        f_prog.write(str(current_count))

                    time.sleep(3)

            if is_crashed:
                logger.error("CRASHED tại: %s | Chunk: %d/%d. Hệ thống ngủ 60s rồi tự động chạy lại...", file_identifier, current_count, total_chunks)
                time.sleep(60)
                continue

        final_markdown = ""
        if os.path.exists(temp_data_file):
            with open(temp_data_file, "r", encoding="utf-8") as f_temp:
                final_markdown = f_temp.read()

        if os.path.exists(progress_file): os.remove(progress_file)
        if os.path.exists(temp_data_file): os.remove(temp_data_file)

        return final_markdown.strip()

def process_single_file(input_file, output_file, chunk_size=3):
    if os.path.exists(output_file):
        return

    with open(input_file, "rb") as f_in:
        pdf_raw_bytes = f_in.read()

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    extractor = PdfToMarkdownConverter()

    extracted_content = extractor.process_content(
        pdf_bytes=pdf_raw_bytes,
        output_file_path=output_file,
        chunk_size=chunk_size
    )

    if extracted_content == "QUOTA_EXCEEDED":
        logger.critical("HẾT HẠN MỨC API (QUOTA EXCEEDED). Hệ thống đã dừng lại an toàn.")
        return

    if not extracted_content:
        return

    with open(output_file, "w", encoding="utf-8") as f_out:
        f_out.write(extracted_content)