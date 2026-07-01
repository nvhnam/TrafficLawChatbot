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

import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

# Nhớ chỉnh lại thư mục import cho đúng cấu trúc project của bạn
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

# ================= CẤU HÌNH THƯ MỤC =================
# DATABASE 1: Nơi lưu file gốc an toàn (Ổ cứng/Cloud giả lập)
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

    # Kiểm tra và tự động tạo tài khoản ADMIN mặc định nếu chưa có
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin')
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('admin', hashed_pw, 'admin'))
        print("👑 Đã khởi tạo tài khoản Admin mặc định (admin/admin)")

    conn.commit()
    conn.close()


# Chạy khởi tạo DB ngay khi khởi động app
init_user_db()


# ================= CÁC API XÁC THỰC (AUTH) =================
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
        # Đăng nhập thành công, trả về thông tin user (không trả mật khẩu)
        user_info = {
            "id": user[0],
            "username": user[1],
            "role": user[3]
        }
        return jsonify({"code": "0", "message": "Đăng nhập thành công", "data": user_info})
    else:
        return jsonify({"code": "1", "message": "Tài khoản hoặc mật khẩu không chính xác!"})

# ================= TRẠNG THÁI TIẾN TRÌNH (PROGRESS) =================
progress_status = {
    "is_running": False,
    "phase": "idle",       # Các pha: idle, extracting, uploading, building_graph, completed, error
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

# =====================================================================
# API KIỂM TRA TIẾN ĐỘ CHẠY BATCH / FOLDER
# =====================================================================
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

    # --- CẬP NHẬT TRẠNG THÁI: BẮT ĐẦU ---
    progress_status = {
        "is_running": True,
        "phase": "extracting",
        "total_files": len(files),
        "processed_files": 0,
        "current_file": "",
        "message": f"Bắt đầu trích xuất dữ liệu cho {len(files)} files..."
    }

    print("\n" + "=" * 50)
    print(f"🚀 [API TỔNG] BẮT ĐẦU XỬ LÝ FOLDER: {len(files)} FILES")
    print("=" * 50)

    # ---------------------------------------------------------
    # GIAI ĐOẠN 1: XỬ LÝ TỪNG FILE & XUẤT JSON RA Ổ CỨNG
    # ---------------------------------------------------------
    for file in files:
        # --- CẬP NHẬT TRẠNG THÁI: ĐANG XỬ LÝ FILE ---
        progress_status["current_file"] = file.filename
        progress_status["message"] = f"Đang trích xuất JSON: {file.filename}"

        try:
            doc_uuid = uuid.uuid4().hex
            original_ext = os.path.splitext(file.filename)[1].lower()
            permanent_file_path = os.path.join(FILE_STORAGE_DB, f"folder_{doc_uuid}{original_ext}")
            file.save(permanent_file_path)

            print(f"\n📄 Đang xử lý file: {file.filename}")

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

            # LƯU FILE JSON RA Ổ CỨNG
            json_filename = f"data_{doc_uuid}.json"
            json_filepath = os.path.join(FILE_STORAGE_JSON_DB, json_filename)
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result_json, f, ensure_ascii=False, indent=4)

            processed_jsons.append(json_filepath)
            print(f"💾 Đã lưu JSON thành công tại: {json_filepath}")

        except Exception as e:
            print(f"❌ Lỗi ở file {file.filename}: {str(e)}")
            errors.append({"file": file.filename, "error": str(e)})

        # --- CẬP NHẬT TRẠNG THÁI: XONG 1 FILE ---
        progress_status["processed_files"] += 1

    # ---------------------------------------------------------
    # GIAI ĐOẠN 2: ĐẨY LÊN NEO4J & BUILD GRAPH
    # ---------------------------------------------------------
    if not processed_jsons:
        progress_status["is_running"] = False
        progress_status["phase"] = "error"
        progress_status["message"] = "Toàn bộ file đều lỗi, hủy tiến trình."
        return jsonify(create_response({"errors": errors}, "3", "Toàn bộ file trong folder đều bị lỗi."))

    print("\n" + "=" * 50)
    print(f"🕸️ [API TỔNG] CHUYỂN SANG GIAI ĐOẠN ĐẨY {len(processed_jsons)} FILE LÊN NEO4J")
    print("=" * 50)

    try:
        # --- CẬP NHẬT TRẠNG THÁI: UPLOAD NEO4J ---
        progress_status["phase"] = "uploading"
        progress_status["processed_files"] = 0
        progress_status["total_files"] = len(processed_jsons)

        # 2.1. Vòng lặp đẩy các file JSON lên Neo4j
        for idx, file_path in enumerate(processed_jsons):
            file_name_only = os.path.basename(file_path)

            progress_status["current_file"] = file_name_only
            progress_status["message"] = f"Đang nạp dữ liệu lên DB ({idx + 1}/{len(processed_jsons)}): {file_name_only}"
            print(f"⏳ {progress_status['message']}")

            uploader.upload_data(file_path)

            uploaded_path = file_path + ".uploaded"
            os.rename(file_path, uploaded_path)

            progress_status["processed_files"] += 1

        # 2.2. Kích hoạt Hậu xử lý (Edges & Vectors)
        # --- CẬP NHẬT TRẠNG THÁI: BUILD GRAPH ---
        progress_status["phase"] = "building_graph"
        progress_status["current_file"] = ""
        progress_status["message"] = "Đang chạy Hậu xử lý (Nối dây & Nhúng Vector) trên Neo4j. Vui lòng đợi..."
        print("\n🧩 Đang kích hoạt hậu xử lý Graph & Vector...")

        post_processor_model.run_all()

        # --- CẬP NHẬT TRẠNG THÁI: HOÀN THÀNH ---
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
        # --- CẬP NHẬT TRẠNG THÁI: LỖI GIAI ĐOẠN CUỐI ---
        progress_status["is_running"] = False
        progress_status["phase"] = "error"
        progress_status["message"] = f"Lỗi Graph/Neo4j: {str(e)}"
        print(f"❌ Lỗi ở Giai đoạn Build Graph: {str(e)}")
        return jsonify(create_response({"errors": errors}, "5", f"Lỗi ở giai đoạn Neo4j/Build Graph: {str(e)}"))
# =====================================================================
# API 1: UPLOAD & XỬ LÝ VĂN BẢN (PDF, DOCX, IMG) -> JSON
# =====================================================================
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

        print(f"📥 Đã lưu file gốc vào Storage: {permanent_file_path}")

        temp_pdf_path = processor_data_model.convert_input2pdf(permanent_file_path)

        if not temp_pdf_path:
            return jsonify(create_response("", "3", "Lỗi convert file sang PDF"))

        # Trích xuất dữ liệu ra JSON
        result_json = processor_data_model.process_file(temp_pdf_path, doc_uuid)

        # Dọn file PDF tạm
        if temp_pdf_path != permanent_file_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

        if result_json is None:
            return jsonify(create_response("", "4", "Lỗi trích xuất dữ liệu (Có thể hết Quota Gemini)"))

        json_filename = f"data_{doc_uuid}.json"
        json_filepath = os.path.join(FILE_STORAGE_JSON_DB, json_filename)

        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, ensure_ascii=False, indent=4)

        print(f"💾 Đã lưu file JSON chuẩn bị upload tại: {json_filepath}")

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

    # 1. 🟢 BẮT DỮ LIỆU TỪ PAYLOAD MỚI CỦA FRONTEND
    # Hỗ trợ cả chuẩn mới (current_question) và chuẩn cũ (question) để code không bị gãy
    current_question = data.get('current_question', data.get('question', ''))
    history = data.get('history', [])
    session_id = data.get('session_id', 'default_session')

    char_remove = " ,.-:;\n)(+[]/\\_*…–"

    current_question = str(current_question).strip(char_remove)

    if not current_question.strip():
        return jsonify({"text": "", "code": "2", "message": "Câu hỏi không được để trống"})

    print(f"\n📩 [API /chat_stream] Session: {session_id} | Ngữ cảnh cũ: {len(history)} tin | Hỏi: {current_question}")

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
        'Transfer-Encoding': 'chunked'
    }

    # Bắt buộc dùng stream_with_context
    return Response(
        stream_with_context(generate()),
        mimetype='text/plain',
        headers=headers
    )

@app.route("/ocr_text", methods=['POST'])
@cross_origin()
def ocr_text():
    # 1. Kiểm tra xem có file trong request không
    if 'image' not in request.files:
        return jsonify({
            "text": "",
            "code": "3",
            "message": "Không tìm thấy dữ liệu hình ảnh"
        }), 400

    file = request.files['image']

    # 2. Kiểm tra tên file trống
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
        print(f"❌ [Lỗi OCR]: {str(e)}")
        return jsonify({
            "text": "",
            "code": "500",
            "message": f"Lỗi xử lý ảnh: {str(e)}"
        }), 500

@app.route("/answer_with_image_input", methods=['POST'])
@cross_origin()
def answer_with_image_input():
    data = request.json
    if not data :
        return jsonify({"text" : "", "code": "1", "message": "Không có dữ liệu gửi lên"})
    user_question = data.get('question', "").strip()
    image_bs64 = data.get("image", None)
    if not image_bs64 :
        return jsonify({"text" : "", "code" : "3", "message" : "Không tìm thấy dữ liệu ảnh Base64"})
    extracted_text = ""
    try :
        if "," in image_bs64 :
            cleaned_bs64 = image_bs64.split(",", 1)[1]
        else :
            cleaned_bs64 = image_bs64

        img = base64ToBGR(cleaned_bs64)
        list_extracted_texts = model_ocr.predict_ocr(img)
        extracted_text = " ".join(list_extracted_texts).strip()

    except Exception as e:
        return jsonify({"text": "", "code": "500", "message": f"Lỗi xử lý ảnh: {str(e)}"})

    if user_question:
        final_prompt = f"Tôi có một bức ảnh với nội dung chữ là: '{extracted_text}'.\nCâu hỏi của tôi là: {user_question}"
    else:
        final_prompt = f"Hãy đóng vai chuyên gia luật giao thông và trả lời/giải quyết tình huống trong bức ảnh có nội dung sau: '{extracted_text}'"

    def generate():
        try:
            for chunk in model_chatbot.run_chatbot(final_prompt):
                yield chunk.encode('utf-8')
        except Exception as e:
            print(f"❌ [Lỗi API Stream Ảnh]: {str(e)}")
            yield f"\n[Lỗi hệ thống]: {str(e)}".encode('utf-8')

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
        'Transfer-Encoding': 'chunked'
    }

    return Response(
        stream_with_context(generate()),
        mimetype='text/plain',
        headers=headers
    )


@app.route("/get_system_stats", methods=['GET'])
@cross_origin()
def get_system_stats():
    """API lấy danh sách Văn bản và Tổng số Đoạn văn (Chunks) từ Neo4j"""
    try:
        driver = uploader.driver

        with driver.session() as session:
            # ==========================================
            # QUERY 1: Lấy danh sách Document
            # ==========================================
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

            # ==========================================
            # QUERY 2: Đếm tổng số Chunk
            # ==========================================
            query_chunks = """
            MATCH (c:Chunk) 
            RETURN count(c) AS Tong_So_Doan_Van_Ban
            """
            result_chunks = session.run(query_chunks)

            total_chunks = result_chunks.single()["Tong_So_Doan_Van_Ban"]

        # ==========================================
        # ĐÓNG GÓI KẾT QUẢ ĐẦU RA THEO YÊU CẦU
        # ==========================================
        final_data = {
            "danh_sach_van_ban": list_documents,
            "tong_so_doan_van_ban": total_chunks
        }

        print(f"📊 Đã truy xuất thống kê: {len(list_documents)} văn bản, {total_chunks} đoạn văn.")

        # Tận dụng luôn hàm create_response có sẵn trong code của bạn
        return jsonify(create_response(final_data, "0", "Thành công"))

    except Exception as e:
        print(f"❌ [Lỗi API Thống kê Neo4j]: {str(e)}")
        return jsonify(create_response({}, "500", f"Lỗi truy xuất cơ sở dữ liệu: {str(e)}"))

    
    @app.route("/delete_document", methods=['POST'])
    @cross_origin()
    def delete_document():
        """API Xóa Văn bản và toàn bộ Chunk liên quan khỏi Neo4j"""
        data = request.json
        if not data:
            return jsonify(create_response("", "1", "Không có dữ liệu gửi lên"))

        doc_name = data.get('document_name', '').strip()
        if not doc_name:
            return jsonify(create_response("", "2", "Tên văn bản không được để trống"))

        print(f"\n🗑️ [API XÓA] Đang yêu cầu xóa văn bản: '{doc_name}'")

        try:
            driver = uploader.driver
            with driver.session() as session:
                delete_query = """
                MATCH (d:Document {name: $doc_name})
                OPTIONAL MATCH (d)-[]-(c:Chunk)
                DETACH DELETE d, c
                """

                # Thực thi query
                result = session.run(delete_query, doc_name=doc_name)

                # Lấy thông tin thống kê số lượng Node/Edge đã bị xóa để log ra cho an tâm
                summary = result.consume().counters
                nodes_deleted = summary.nodes_deleted
                rels_deleted = summary.relationships_deleted

            print(f"✅ Đã xóa thành công! (Xóa {nodes_deleted} nodes và {rels_deleted} relationships)")

            return jsonify(create_response({
                "message": f"Đã xóa thành công văn bản: {doc_name}",
                "nodes_deleted": nodes_deleted
            }, "0", "Thành công"))

        except Exception as e:
            print(f"❌ [Lỗi API Xóa Neo4j]: {str(e)}")
            return jsonify(create_response("", "500", f"Lỗi khi xóa trong Database: {str(e)}"))

if __name__ == '__main__':
    print("🌟 CỖ MÁY GRAPHRAG ĐANG CHẠY TẠI CỔNG 1904...")
    app.run(host="0.0.0.0", port=1904, threaded=True, debug=False)