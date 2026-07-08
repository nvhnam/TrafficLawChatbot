import json
import base64
from flask import Blueprint, request, Response, jsonify, stream_with_context
from flask_cors import cross_origin

from backend.core.container import ServiceContainer

bp = Blueprint("chat", __name__)


def _get_bot():
    from backend.chatbot.bot import GraphRAG_Bot
    return ServiceContainer.get("bot", GraphRAG_Bot)


def _get_ocr():
    from backend.ocr.predictor import OCRGeneralPredictor
    return ServiceContainer.get("ocr", OCRGeneralPredictor)


def _stream_headers() -> dict:
    return {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }


def _base64_to_bgr(b64: str):
    import numpy as np
    import cv2
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    im_bytes = base64.b64decode(b64)
    arr = np.frombuffer(im_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, flags=cv2.IMREAD_COLOR)


@bp.route("/chat_stream", methods=["POST"])
@cross_origin()
def chat_stream():
    data = request.json
    if not data:
        return jsonify({"text": "", "code": "1", "message": "Du lieu khong hop le"})

    question = str(data.get("current_question", data.get("question", ""))).strip(" ,.-:;\n)(+[]/\\_*...-")
    history = data.get("history", [])

    if len(question) < 2:
        return jsonify({"text": "", "code": "2", "message": "Vui long dat cau hoi chi tiet hon."})

    bot = _get_bot()

    def generate():
        sources_emitted = False
        try:
            for frame in bot.run_chatbot_ndjson(question, history):
                if not sources_emitted and frame.get("type") == "sources":
                    sources_emitted = True
                yield json.dumps(frame, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "data": str(e)}) + "\n"
        finally:
            yield json.dumps({"type": "done"}) + "\n"

    return Response(stream_with_context(generate()), mimetype="text/plain", headers=_stream_headers())


@bp.route("/answer_with_image_input", methods=["POST"])
@cross_origin()
def answer_with_image_input():
    data = request.json
    if not data:
        return jsonify({"text": "", "code": "1", "message": "Khong co du lieu gui len"})

    question = data.get("current_question", data.get("question", "")).strip()
    history = data.get("history", [])
    b64 = data.get("image", "")

    if not b64:
        return jsonify({"text": "", "code": "3", "message": "Khong tim thay du lieu anh Base64"})

    try:
        img = _base64_to_bgr(b64)
        ocr = _get_ocr()
        texts = ocr.predict_ocr(img)
        extracted = " ".join(texts).strip() if texts else ""
    except Exception as e:
        return jsonify({"text": "", "code": "500", "message": f"Loi xu ly anh: {str(e)}"})

    if not extracted:
        return jsonify({"text": "Khong nhan dien duoc chu trong anh. Vui long chup ro net hon.", "code": "0"})

    try:
        bot = _get_bot()
        preprocess_resp = bot.llm_model.generate_content(
            f'Bạn là chuyên gia phân tích tài liệu. Văn bản quét được: "{extracted}"\n'
            "Nhiệm vụ: Nếu là biên bản vi phạm, trích xuất mô tả hành vi vi phạm. "
            "Ngược lại tóm tắt nội dung. Chỉ trả về kết quả, không giải thích."
        )
        context = preprocess_resp.text.strip()
    except Exception:
        context = extracted

    final_q = (
        f"Thong tin vi pham tu anh: '{context}'.\nCau hoi: {question}"
        if question
        else f"Toi bi lap bien ban: '{context}'. Hay cho biet muc xu phat."
    )

    def generate():
        try:
            for frame in bot.run_chatbot_ndjson(final_q, history):
                yield json.dumps(frame, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "data": str(e)}) + "\n"
        finally:
            yield json.dumps({"type": "done"}) + "\n"

    return Response(stream_with_context(generate()), mimetype="text/plain", headers=_stream_headers())
