import json
import os
from PIL import Image

try:
    from docx2pdf import convert as docx_convert
except ImportError:
    docx_convert = None

from chunk_generator.create_chunk_text import LegalSemanticSplitter
from process_by_gemini.convert_markdown import PdfToMarkdownConverter
from process_by_gemini.get_entities_gemini import GetEntitiesByGemini
from data_processing.data_cleaner import DataCleaner
# from markdown_coverter.doc_processor import DocProcessor


class DataProcessorGraphRAG:
    def __init__(self):
        self.model_convert_to_md = PdfToMarkdownConverter()
        # self.model_convert_to_md = DocProcessor()
        self.model_create_chunk = LegalSemanticSplitter()
        self.model_extract_entities = GetEntitiesByGemini()
        self.model_data_cleaner = DataCleaner()

    def convert_input2pdf(self, input_path):
        if not os.path.exists(input_path):
            return None

        ext = os.path.splitext(input_path)[1].lower()

        if ext == ".pdf":
            return input_path

        output_pdf_path = os.path.splitext(input_path)[0] + ".pdf"

        try:
            if ext in [".doc", ".docx"]:
                if docx_convert is None:
                    return None
                docx_convert(input_path, output_pdf_path)
                return output_pdf_path

            elif ext in [".jpg", ".jpeg", ".png"]:
                image = Image.open(input_path)
                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")
                image.save(output_pdf_path, "PDF", resolution=100.0)
                return output_pdf_path

            else:
                return None

        except Exception as e:
            return None

    def process_file(self, input_path, doc_uuid):
        if not os.path.exists(input_path):
            return None

        with open(input_path, "rb") as f_in:
            pdf_raw_bytes = f_in.read()

        temp_workspace = os.path.join("/home/manh/Code/my_final_project/folder_check/temp_workspace", doc_uuid)
        os.makedirs(temp_workspace, exist_ok=True)

        dummy_md_id = os.path.join(temp_workspace, f"{doc_uuid}_md")
        markdown_text = self.model_convert_to_md.process_content(
            pdf_bytes=pdf_raw_bytes,
            output_file_path=dummy_md_id
        )

        if not markdown_text or markdown_text == "QUOTA_EXCEEDED":
            return None

        #  BƯỚC 1
        # step1_md_path = os.path.join(temp_workspace, f"step1_markdown.md")
        # with open(step1_md_path, "w", encoding="utf-8") as f:
        #     f.write(markdown_text)
        # print("Da luu : {}".format(step1_md_path))

        # BƯỚC 2: Split text into chunks
        chunks_data = self.model_create_chunk.split_text(
            text=markdown_text,
            doc_name=doc_uuid
        )

        if not chunks_data:
            return None

        # BƯỚC 2
        # step2_chunks_path = os.path.join(temp_workspace, f"step2_chunks.json")
        # with open(step2_chunks_path, "w", encoding="utf-8") as f:
        #     json.dump(chunks_data, f, ensure_ascii=False, indent=4)

        # BƯỚC 3: Extract Entities (Gemini)
        dummy_entity_id = os.path.join(temp_workspace, f"{doc_uuid}_entities")
        list_entities = self.model_extract_entities.process_content(
            all_chunks=chunks_data,
            output_file_path=dummy_entity_id
        )

        if not list_entities or list_entities == "QUOTA_EXCEEDED":
            return None

        # LƯU FILE BƯỚC 3: Lưu list_entities ban đầu dạng JSON
        # step3_entities_path = os.path.join(temp_workspace, f"step3_entities.json")
        # with open(step3_entities_path, "w", encoding="utf-8") as f:
        #     json.dump(list_entities, f, ensure_ascii=False, indent=4)
        # print("Da luu : {}".format(step3_entities_path))

        # BƯỚC 4: Data Cleaner (Suy luận tên thật & dọn rác)
        list_entities_cleaned = self.model_data_cleaner.clean_data(list_entities)
        if not list_entities_cleaned:
            return None

        # LƯU FILE BƯỚC 4: Lưu entities đã được làm sạch dạng JSON
        # step4_cleaned_path = os.path.join(temp_workspace, f"step4_entities_cleaned.json")
        # with open(step4_cleaned_path, "w", encoding="utf-8") as f:
        #     json.dump(list_entities_cleaned, f, ensure_ascii=False, indent=4)
        # print("Da luu : {}".format(step4_cleaned_path))

        # BƯỚC 5: G UUID CHO TẤT CẢ CHUNK
        for chunk in list_entities_cleaned:
            if "metadata" not in chunk:
                chunk["metadata"] = {}
            chunk["metadata"]["file_uuid"] = doc_uuid

        # LƯU FILE BƯỚC 5: Lưu kết quả cuối cùng dạng JSON
        # step5_final_path = os.path.join(temp_workspace, f"step5_final_output.json")
        # with open(step5_final_path, "w", encoding="utf-8") as f:
        #     json.dump(list_entities_cleaned, f, ensure_ascii=False, indent=4)
        # print("Da luu : {}".format(step5_final_path))

        return list_entities_cleaned