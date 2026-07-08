import logging
import os.path
import re

import numpy as np
import torch
from pathlib import Path
from typing import Iterable, Type, List, Literal
from PIL import Image

# Docling Core & Datamodel
from docling_core.types.doc import BoundingBox, CoordOrigin
from docling_core.types.doc.page import BoundingRectangle, TextCell
from docling.models.base_ocr_model import BaseOcrModel
from docling.datamodel.pipeline_options import OcrOptions, PdfPipelineOptions
from docling.datamodel.base_models import Page, InputFormat
from docling.datamodel.document import ConversionResult
from docling.document_converter import DocumentConverter, PdfFormatOption
from backend.config import *
# Thêm import BaseFactory để thực hiện Monkey Patch
from docling.models.factories.base_factory import BaseFactory

# --- IMPORT CÁC CLASS CỦA BẠN ---
from backend.ocr.detector_text.detector_text import TextDetector
from backend.ocr.ocr_text.ocr_predictor import OCRPredictor

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

# --- 1. ĐỊNH NGHĨA OPTIONS ---
class VietnameseOcrOptions(OcrOptions):
    kind: Literal["yolo_crnn_vietnamese"] = "yolo_crnn_vietnamese"
    lang: List[str] = ["vi"]
    yolo_path: str = os.path.join(folder_weight, "weight_detect_text/weight_detect_text.pt")
    crnn_path: str = os.path.join(folder_weight, "weight_ocr_text/weight_ocr_text.pth")


# --- 2. WRAPPER MODEL CHO DOCLING ---
class VietnameseOcrModel(BaseOcrModel):
    def __init__(self, enabled: bool, options: VietnameseOcrOptions, **kwargs):
        super().__init__(enabled=enabled, options=options, **kwargs)

        if self.enabled:
            _log.info("Đang khởi tạo TextDetector (YOLOv8) và OCRPredictor (CRNN)...")
            self.detector = TextDetector()
            self.predictor = OCRPredictor()

        # Scale 2 giúp Docling render ảnh 144 DPI (72*2), đủ nét cho OCR
        self.scale = 2

    @classmethod
    def get_options_type(cls) -> Type[VietnameseOcrOptions]:
        return VietnameseOcrOptions

    def align_margins(self, cells: List[TextCell], threshold=10.0) -> List[TextCell]:
        """
        Tìm các lề trái phổ biến và ép các cell về lề đó để tránh lỗi layout.
        """
        if not cells:
            return cells

        return cells

    def __call__(self, conv_res: ConversionResult, page_batch: Iterable[Page]) -> Iterable[Page]:
        for page in page_batch:
            if not self.enabled or not page._backend.is_valid():
                yield page
                continue

            ocr_rects = self.get_ocr_rects(page)
            all_ocr_cells = []
            page_w, page_h = page.size.width, page.size.height

            for ocr_rect in ocr_rects:
                if ocr_rect.area() == 0:
                    continue

                page_img_pil = page._backend.get_page_image(scale=self.scale, cropbox=ocr_rect)
                lines = self.detector.predict(page_img_pil)

                if not lines:
                    continue

                # BƯỚC 1: LẤY CÁC DÒNG (LINES) NGUYÊN BẢN TỪ YOLO
                yolo_blocks = []
                img_w = page.size.width * self.scale  # Lấy chiều rộng ảnh

                for line in lines:
                    if not line: continue

                    sorted_line = sorted(line, key=lambda item: item['box'][0])

                    line_text = ""
                    x1_list, y1_list, x2_list, y2_list = [], [], [], []
                    min_score = 1.0

                    for item in sorted_line:
                        x1, y1, x2, y2 = item['box']
                        text = self.predictor.predict_crnn(item['crop'])

                        if text and text.strip() != "":
                            text_clean = text.strip()

                            # ---------------------------------------------------------
                            # BỘ LỌC 1: TIÊU DIỆT RÁC Ở 2 MÉP LỀ TRÁI/PHẢI (MỚI)
                            # Nếu ký tự nằm trong 12% lề trái hoặc 12% lề phải, và là ký tự ngắn rác -> Vứt!
                            if (x1 < img_w * 0.12 or x1 > img_w * 0.88) and len(text_clean) <= 2:
                                if text_clean in ['1', 'I', 'l', 'i', '|', '!', '^', ':', ';', '.', ',', '-']:
                                    continue

                            # BỘ LỌC 2: TIÊU DIỆT VỆT DỌC
                            box_w = x2 - x1
                            box_h = y2 - y1
                            if text_clean in ['l', '|', ':', ';', '.', ',', '!']:
                                if box_h > 4.0 * box_w:
                                    continue

                            line_text += text_clean + " "
                            x1_list.append(x1)
                            y1_list.append(y1)
                            x2_list.append(x2)
                            y2_list.append(y2)
                            min_score = min(min_score, item['score'])

                    if not x1_list: continue

                    yolo_blocks.append({
                        'text': line_text.strip(),
                        'score': min_score,
                        'x1': min(x1_list), 'y1': min(y1_list),
                        'x2': max(x2_list), 'y2': max(y2_list)
                    })

                # BƯỚC 2: GOM CÁC KHỐI YOLO BỊ ĐỨT ĐOẠN NGANG
                yolo_blocks.sort(key=lambda b: b['y1'])

                merged_blocks = []
                for block in yolo_blocks:
                    added = False
                    for m_block in reversed(merged_blocks):
                        overlap_top = max(block['y1'], m_block['y1'])
                        overlap_bottom = min(block['y2'], m_block['y2'])

                        if overlap_bottom > overlap_top:
                            overlap_h = overlap_bottom - overlap_top
                            min_h = min(block['y2'] - block['y1'], m_block['y2'] - m_block['y1'])

                            if overlap_h / (min_h + 1e-5) > 0.5:
                                if block['x1'] > m_block['x1']:
                                    m_block['text'] = m_block['text'] + " " + block['text']
                                    m_block['x2'] = max(m_block['x2'], block['x2'])
                                else:
                                    m_block['text'] = block['text'] + " " + m_block['text']
                                    m_block['x1'] = min(m_block['x1'], block['x1'])

                                m_block['y1'] = min(m_block['y1'], block['y1'])
                                m_block['y2'] = max(m_block['y2'], block['y2'])
                                m_block['score'] = min(m_block['score'], block['score'])
                                added = True
                                break

                    if not added:
                        merged_blocks.append(block)

                # BƯỚC 3: TIỀN XỬ LÝ & TẠO TEXTCELL
                for block in merged_blocks:
                    # 2. FIX LỖI DẤU HAI CHẤM: Sửa "1:" thành "1." ngay tại nguồn
                    text = block['text']
                    text = re.sub(r'^(\d+)\s*[:;]\s+', r'\1. ', text)
                    block['text'] = text
                    # ---------------------------------------------------------

                    l = (block['x1'] / self.scale) + ocr_rect.l
                    r = (block['x2'] / self.scale) + ocr_rect.l
                    t = (block['y1'] / self.scale) + ocr_rect.t
                    b = (block['y2'] / self.scale) + ocr_rect.t

                    l = max(0.0, float(l))
                    r = min(float(page_w), float(r))
                    t = max(0.0, float(t))
                    b = min(float(page_h), float(b))

                    if t >= b: b = t + 1.0
                    if l >= r: r = l + 1.0

                    cell = TextCell(
                        index=len(all_ocr_cells),
                        text=block['text'],
                        confidence=block['score'],
                        orig=block['text'],
                        from_ocr=True,
                        rect=BoundingRectangle.from_bounding_box(
                            BoundingBox(l=l, t=t, r=r, b=b, coord_origin=CoordOrigin.TOPLEFT)
                        )
                    )
                    all_ocr_cells.append(cell)

            self.post_process_cells(all_ocr_cells, page)
            yield page