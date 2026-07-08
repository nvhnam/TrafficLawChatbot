from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from backend.core.container import ServiceContainer

bp = Blueprint("ocr", __name__)


def _get_ocr():
    from backend.ocr.predictor import OCRGeneralPredictor
    return ServiceContainer.get("ocr", OCRGeneralPredictor)


@bp.route("/ocr_text", methods=["POST"])
@cross_origin()
def ocr_text():
    if "image" not in request.files:
        return jsonify({"text": "", "code": "3", "message": "Khong tim thay du lieu hinh anh"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"text": "", "code": "4", "message": "Ten file khong hop le"}), 400

    try:
        import numpy as np
        import cv2
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        texts = _get_ocr().predict_ocr(img)
        extracted = " ".join(texts).strip() if texts else ""

        if not extracted:
            return jsonify({"text": "", "code": "5", "message": "Khong tim thay chu trong anh"})

        return jsonify({"text": extracted, "code": "0", "message": "Thanh cong"})
    except Exception as e:
        return jsonify({"text": "", "code": "500", "message": f"Loi xu ly anh: {str(e)}"}), 500
