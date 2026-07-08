import base64
import os
import uuid

import cv2
import cv2 as cv
import numpy as np
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS, cross_origin
from PIL import Image
import json

import logging
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

from processor_main.data_processor import DataProcessorGraphRAG
from processor_main.post_processor import Neo4jPostProcessor
from processor_main.upload2neo4j import Neo4jUploader
from chatbot.bot import GraphRAG_Bot
from ocr_model.predictor import OCRGeneralPredictor

processor_data_model = DataProcessorGraphRAG()
post_processor_model = Neo4jPostProcessor()
model_chatbot = GraphRAG_Bot()
model_ocr = OCRGeneralPredictor()
uploader = Neo4jUploader()

app = Flask(__name__)
cors = CORS(app)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ================= CẤU HÌNH THƯ MỤC =================
# DATABASE 1: Nơi lưu file gốc an toàn
# ================= CẤU HÌNH THƯ MỤC =================
FILE_STORAGE_DB = './cloud_file_storage'
os.makedirs(FILE_STORAGE_DB, exist_ok=True)

# Thư mục lưu JSON để bạn check và chờ đẩy lên DB
FILE_STORAGE_JSON_DB = './cloud_file_json_prepare_upload_storage'
os.makedirs(FILE_STORAGE_JSON_DB, exist_ok=True)


# ================= CẤU HÌNH DATABASE NGƯỜI DÙNG =================
DB_USER_PATH = './users.db'


def init_user_db():
    """Khởi tạo database và bảng users nếu chưa có"""
    conn = sqlite3.connect(DB_USER_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')

    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin')
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('admin', hashed_pw, 'admin'))
        print("👑 Đã khởi tạo tài khoản Admin mặc định (admin/admin)")

    conn.commit()
    conn.close()


init_user_db()

@app.route("/register", methods=['POST'])
@cross_origin()
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"code": "1", "message": "Vui lòng nhập đủ tài khoản và mật khẩu"})

    hashed_pw = generate_password_hash(password)

    try:
        conn = sqlite3.connect(DB_USER_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
        conn.commit()
        conn.close()
        return jsonify({"code": "0", "message": "Đăng ký thành công!"})
    except sqlite3.IntegrityError:
        return jsonify({"code": "2", "message": "Tên đăng nhập này đã tồn tại!"})
    except Exception as e:
        return jsonify({"code": "500", "message": f"Lỗi DB: {str(e)}"})


@app.route("/login", methods=['POST'])
@cross_origin()
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    conn = sqlite3.connect(DB_USER_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, role FROM users WHERE username=?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user[2], password):
        user_info = {
            "id": user[0],
            "username": user[1],
            "role": user[3]
        }
        return jsonify({"code": "0", "message": "Đăng nhập thành công", "data": user_info})
    else:
        return jsonify({"code": "1", "message": "Tài khoản hoặc mật khẩu không chính xác!"})

progress_status = {
    "is_running": False,
    "phase": "idle",
    "total_files": 0,
    "processed_files": 0,
    "current_file": "",
    "message": "Hệ thống đang rảnh rỗi"
}

def base64ToBGR(base64_string):
    im_bytes = base64.b64decode(str(base64_string))
    im_arr = np.frombuffer(im_bytes, dtype=np.uint8)
    img = cv2.imdecode(im_arr, flags=cv2.IMREAD_COLOR)
    return img

def create_response(data, error_code, error_message):
    return {"errorCode": error_code, "errorMessage": error_message, "data": data}

@app.route("/check_progress", methods=['GET'])
@cross_origin()
def check_progress():
    global progress_status
    return jsonify(create_response(progress_status, "0", "Thành công"))


@app.route("/process_folder_and_build", methods=['POST'])
@cross_origin()
def process_folder_and_build():
    global progress_status

    if 'files' not in request.files:
        return jsonify(create_response("", "1", "Không tìm thấy danh sách file trong request"))

    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify(create_response("", "2", "Folder rỗng hoặc chưa chọn file"))

    processed_jsons = []
    errors = []

    progress_status = {
        "is_running": True,
        "phase": "extracting",
        "total_files": len(files),
        "processed_files": 0,
        "current_file": "",
        "message": f"Bắt đầu trích xuất dữ liệu cho {len(files)} files..."
    }

    for file in files:
        progress_status["current_file"] = file.filename
        progress_status["message"] = f"Đang trích xuất JSON: {file.filename}"

        try:
            doc_uuid = uuid.uuid4().hex
            original_ext = os.path.splitext(file.filename)[1].lower()
            permanent_file_path = os.path.join(FILE_STORAGE_DB, f"folder_{doc_uuid}{original_ext}")
            file.save(permanent_file_path)

            temp_pdf_path = processor_data_model.convert_input2pdf(permanent_file_path)
            if not temp_pdf_path:
                errors.append({"file": file.filename, "error": "Lỗi convert sang PDF"})
                progress_status["processed_files"] += 1
                continue

            # Trích xuất dữ liệu ra JSON bằng Gemini
            result_json = processor_data_model.process_file(temp_pdf_path, doc_uuid)

            # Dọn dẹp file PDF convert tạm
            if temp_pdf_path != permanent_file_path and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)

            if not result_json:
                errors.append({"file": file.filename, "error": "Lỗi trích xuất (Quota Gemini hoặc nội dung rỗng)"})
                progress_status["processed_files"] += 1
                continue

            json_filename = f"data_{doc_uuid}.json"
            json_filepath = os.path.join(FILE_STORAGE_JSON_DB, json_filename)
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result_json, f, ensure_ascii=False, indent=4)

            processed_jsons.append(json_filepath)

        except Exception as e:
            errors.append({"file": file.filename, "error": str(e)})

        progress_status["processed_files"] += 1

    if not processed_jsons:
        progress_status["is_running"] = False
        progress_status["phase"] = "error"
        progress_status["message"] = "Toàn bộ file đều lỗi, hủy tiến trình."
        return jsonify(create_response({"errors": errors}, "3", "Toàn bộ file trong folder đều bị lỗi."))

    try:
        progress_status["phase"] = "uploading"
        progress_status["processed_files"] = 0
        progress_status["total_files"] = len(processed_jsons)

        for idx, file_path in enumerate(processed_jsons):
            file_name_only = os.path.basename(file_path)

            progress_status["current_file"] = file_name_only
            progress_status["message"] = f"Đang nạp dữ liệu lên DB ({idx + 1}/{len(processed_jsons)}): {file_name_only}"

            uploader.upload_data(file_path)

            uploaded_path = file_path + ".uploaded"
            os.rename(file_path, uploaded_path)

            progress_status["processed_files"] += 1

        progress_status["phase"] = "building_graph"
        progress_status["current_file"] = ""
        progress_status["message"] = "Đang chạy Hậu xử lý (Nối dây & Nhúng Vector) trên Neo4j. Vui lòng đợi..."

        post_processor_model.run_all()

        progress_status["is_running"] = False
        progress_status["phase"] = "completed"
        progress_status["message"] = "Hoàn tất 100%!"

        return jsonify(create_response({
            "message": f"Hoàn tất toàn bộ chu trình cho Folder!",
            "total_success": len(processed_jsons),
            "total_errors": len(errors),
            "errors_detail": errors
        }, "0", "Thành công"))

    except Exception as e:
        progress_status["is_running"] = False
        progress_status["phase"] = "error"
        progress_status["message"] = f"Lỗi Graph/Neo4j: {str(e)}"
        return jsonify(create_response({"errors": errors}, "5", f"Lỗi hệ thống: {str(e)}"))

@app.route("/process_document", methods=['POST'])
@cross_origin()
def process_document():
    if 'file' not in request.files:
        return jsonify(create_response("", "1", "Không tìm thấy file trong request"))

    file = request.files['file']
    if file.filename == '':
        return jsonify(create_response("", "2", "Chưa chọn file"))

    try:
        doc_uuid = uuid.uuid4().hex
        original_ext = os.path.splitext(file.filename)[1].lower()
        permanent_file_path = os.path.join(FILE_STORAGE_DB, f"{doc_uuid}{original_ext}")
        file.save(permanent_file_path)


        temp_pdf_path = processor_data_model.convert_input2pdf(permanent_file_path)

        if not temp_pdf_path:
            return jsonify(create_response("", "3", "Lỗi convert file sang PDF"))

        result_json = processor_data_model.process_file(temp_pdf_path, doc_uuid)

        if temp_pdf_path != permanent_file_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

        if result_json is None:
            return jsonify(create_response("", "4", "Lỗi trích xuất dữ liệu (Có thể hết Quota Gemini)"))

        json_filename = f"data_{doc_uuid}.json"
        json_filepath = os.path.join(FILE_STORAGE_JSON_DB, json_filename)

        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, ensure_ascii=False, indent=4)


        return jsonify(create_response({
            "message": "Trích xuất và lưu JSON thành công!",
            "json_file": json_filepath
        }, "0", "Thành công"))

    except Exception as e:
        return jsonify(create_response("", "5", f"Lỗi hệ thống: {str(e)}"))


@app.route("/build_graph", methods=['POST'])
@cross_origin()
def build_graph():
    try:
        print("\n🚀 BẮT ĐẦU LUỒNG UPLOAD DỮ LIỆU & XÂY DỰNG ĐỒ THỊ...")

        json_files = [f for f in os.listdir(FILE_STORAGE_JSON_DB) if f.endswith('.json')]

        if not json_files:
            return jsonify(create_response("", "1", "Không có file JSON nào trong thư mục để upload."))

        print(f"📦 Tìm thấy {len(json_files)} file JSON. Bắt đầu đẩy lên Neo4j...")

        for json_filename in json_files:
            file_path = os.path.join(FILE_STORAGE_JSON_DB, json_filename)
            print(f"⏳ Đang upload file: {json_filename}")

            uploader.upload_data(file_path)

        print("\n🕸️ Đã nạp xong tất cả JSON. Kích hoạt nối dây và nhúng Vector...")
        post_processor_model.run_all()

        return jsonify(create_response(f"Đã upload {len(json_files)} file JSON, xây dựng Đồ thị và nhúng Vector thành công!", "0", "Thành công"))

    except Exception as e:
        print(f"❌ Lỗi khi nạp dữ liệu và xây dựng Đồ thị: {str(e)}")
        return jsonify(create_response("", "5", f"Lỗi hệ thống: {str(e)}"))


@app.route("/chat_stream", methods=['POST'])
@cross_origin()
def chat_stream():
    data = request.json

    if not data:
        return jsonify({"text": "", "code": "1", "message": "Dữ liệu không hợp lệ"})

    current_question = data.get('current_question', data.get('question', ''))
    history = data.get('history', [])
    session_id = data.get('session_id', 'default_session')

    char_remove = " ,.-:;\n)(+[]/\\_*…–"

    current_question = str(current_question).strip(char_remove)

    if len(current_question) < 2:
        return jsonify({"text": "", "code": "2", "message": "Vui lòng đặt câu hỏi chi tiết và rõ ràng hơn."})

    if not current_question.strip():
        return jsonify({"text": "", "code": "2", "message": "Câu hỏi không được để trống"})


    def generate():
        try:
            for chunk in model_chatbot.run_chatbot(current_question, history):
                yield chunk.encode('utf-8')
        except Exception as e:
            print(f"❌ [Lỗi API Stream]: {str(e)}")
            yield f"\n[Lỗi hệ thống]: {str(e)}".encode('utf-8')

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
        # 'Transfer-Encoding': 'chunked'
    }

    return Response(
        stream_with_context(generate()),
        mimetype='text/plain',
        headers=headers
    )

@app.route("/ocr_text", methods=['POST'])
@cross_origin()
def ocr_text():
    if 'image' not in request.files:
        return jsonify({
            "text": "",
            "code": "3",
            "message": "Không tìm thấy dữ liệu hình ảnh"
        }), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({
            "text": "",
            "code": "4",
            "message": "Tên file không hợp lệ"
        }), 400

    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv.imdecode(file_bytes, cv.IMREAD_COLOR)
        list_extracted_texts = model_ocr.predict_ocr(img)
        extracted_text = " ".join(list_extracted_texts)
        if not extracted_text.strip():
            return jsonify({
                "text": "",
                "code": "5",
                "message": "Không tìm thấy chữ trong ảnh"
            })

        return jsonify({
            "text": extracted_text.strip(),
            "code": "0",
            "message": "Thành công"
        })

    except Exception as e:
        return jsonify({
            "text": "",
            "code": "500",
            "message": f"Lỗi xử lý ảnh: {str(e)}"
        }), 500


@app.route("/answer_with_image_input", methods=['POST'])
@cross_origin()
def answer_with_image_input():
    data = request.json
    if not data:
        return jsonify({"text": "", "code": "1", "message": "Không có dữ liệu gửi lên"})

    user_question = data.get('current_question', data.get('question', '')).strip()
    history = data.get('history', [])

    image_bs64 = data.get("image", None)
    if not image_bs64:
        return jsonify({"text": "", "code": "3", "message": "Không tìm thấy dữ liệu ảnh Base64"})

    extracted_text = ""
    try:
        if "," in image_bs64:
            cleaned_bs64 = image_bs64.split(",", 1)[1]
        else:
            cleaned_bs64 = image_bs64

        img = base64ToBGR(cleaned_bs64)
        list_extracted_texts = model_ocr.predict_ocr(img)
        extracted_text = " ".join(list_extracted_texts).strip()

    except Exception as e:
        return jsonify({"text": "", "code": "500", "message": f"Lỗi xử lý ảnh: {str(e)}"})

    if not extracted_text:
        return jsonify({"text": "Không nhận diện được chữ trong ảnh. Vui lòng chụp rõ nét hơn.", "code": "0"})

    try:
        preprocess_prompt = f"""
        Bạn là chuyên gia phân tích tài liệu. Dưới đây là văn bản quét được từ một hình ảnh:
        "{extracted_text}"

        Nhiệm vụ:
        1. Nếu đây là một "Biên bản vi phạm" hoặc "Quyết định xử phạt", HÃY TRÍCH XUẤT CHÍNH XÁC CỤM TỪ mô tả "Hành vi vi phạm" (VD: điều khiển xe không có gương chiếu hậu, chạy quá tốc độ từ 5-10km/h...). Bỏ qua các thông tin rác như tên người, ngày tháng, địa chỉ.
        2. Nếu không phải biên bản, hãy tóm tắt ngắn gọn nội dung chính.
        Tuyệt đối chỉ trả về cụm từ kết quả, không giải thích dài dòng.
        """

        preprocess_response = model_chatbot.llm_model.generate_content(preprocess_prompt)
        refined_context = preprocess_response.text.strip()

    except Exception as e:
        refined_context = extracted_text

    if user_question:
        final_prompt = f"Thông tin/Lỗi vi phạm từ ảnh là: '{refined_context}'.\nKết hợp với câu hỏi của tôi: {user_question}"
    else:
        final_prompt = f"Tôi bị lập biên bản hoặc có thông tin hình ảnh với nội dung lỗi là: '{refined_context}'. Hãy cho tôi biết quy định pháp luật và mức xử phạt cho hành vi này."

    def generate():
        try:
            for chunk in model_chatbot.run_chatbot(final_prompt, history):
                yield chunk.encode('utf-8')
        except Exception as e:
            yield f"\n[Lỗi hệ thống]: {str(e)}".encode('utf-8')

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    }

    return Response(
        stream_with_context(generate()),
        mimetype='text/plain',
        headers=headers
    )

@app.route("/get_system_stats", methods=['GET'])
@cross_origin()
def get_system_stats():
    try:
        driver = uploader.driver

        with driver.session() as session:
            query_docs = """
            MATCH (d:Document) 
            RETURN d.name AS Ten_Van_Ban, d.type AS Loai_Van_Ban
            """
            result_docs = session.run(query_docs)

            list_documents = []
            for record in result_docs:
                list_documents.append({
                    "Ten_Van_Ban": record["Ten_Van_Ban"] if record["Ten_Van_Ban"] else "Không rõ tên",
                    "Loai_Van_Ban": record["Loai_Van_Ban"] if record["Loai_Van_Ban"] else "Không rõ loại"
                })

            query_chunks = """
            MATCH (c:Chunk) 
            RETURN count(c) AS Tong_So_Doan_Van_Ban
            """
            result_chunks = session.run(query_chunks)

            total_chunks = result_chunks.single()["Tong_So_Doan_Van_Ban"]

        final_data = {
            "danh_sach_van_ban": list_documents,
            "tong_so_doan_van_ban": total_chunks
        }

        return jsonify(create_response(final_data, "0", "Thành công"))

    except Exception as e:
        return jsonify(create_response({}, "500", f"Lỗi truy xuất cơ sở dữ liệu: {str(e)}"))


@app.route("/delete_document", methods=['POST'])
@cross_origin()
def delete_document():
    data = request.json
    if not data:
        return jsonify(create_response("", "1", "Không có dữ liệu gửi lên"))

    doc_name = data.get('document_name', '').strip()
    if not doc_name:
        return jsonify(create_response("", "2", "Tên văn bản không được để trống"))


    try:
        driver = uploader.driver
        with driver.session() as session:
            delete_query = """
            MATCH (d:Document {name: $doc_name})
            OPTIONAL MATCH (d)-[]-(c:Chunk)
            DETACH DELETE d, c
            """

            result = session.run(delete_query, doc_name=doc_name)

            summary = result.consume().counters
            nodes_deleted = summary.nodes_deleted
            rels_deleted = summary.relationships_deleted

        return jsonify(create_response({
            "message": f"Đã xóa thành công văn bản: {doc_name}",
            "nodes_deleted": nodes_deleted
        }, "0", "Thành công"))

    except Exception as e:
        return jsonify(create_response("", "500", f"Lỗi khi xóa trong Database: {str(e)}"))

if __name__ == '__main__':
    logging.info("Chương trình bắt đầu chạy...")
    print("🌟 CỖ MÁY GRAPHRAG ĐANG CHẠY TẠI CỔNG 1904...")
    app.run(host="0.0.0.0", port=1904, threaded=True, debug=False)