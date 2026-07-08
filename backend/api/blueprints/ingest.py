import os
import json
import hashlib
import logging
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from backend.core.container import ServiceContainer
from backend.core.progress import ProgressTracker

logger = logging.getLogger(__name__)

bp = Blueprint("ingest", __name__)

_progress = ProgressTracker()

FILE_STORAGE = "./cloud_file_storage"
FILE_STORAGE_JSON = "./cloud_file_json_prepare_upload_storage"
os.makedirs(FILE_STORAGE, exist_ok=True)
os.makedirs(FILE_STORAGE_JSON, exist_ok=True)


def _get_processor():
    from backend.ingestion.data_processor import DataProcessorGraphRAG
    return ServiceContainer.get("processor", DataProcessorGraphRAG)


def _get_uploader():
    from backend.ingestion.upload2neo4j import Neo4jUploader
    return ServiceContainer.get("uploader", Neo4jUploader)


def _get_post_processor():
    from backend.ingestion.post_processor import Neo4jPostProcessor
    return ServiceContainer.get("post_processor", Neo4jPostProcessor)


def _resp(data, code="0", msg="Thanh cong"):
    return {"errorCode": code, "errorMessage": msg, "data": data}


@bp.route("/check_progress", methods=["GET"])
@cross_origin()
def check_progress():
    return jsonify(_resp(_progress.snapshot()))


@bp.route("/process_folder_and_build", methods=["POST"])
@cross_origin()
def process_folder_and_build():
    if "files" not in request.files:
        return jsonify(_resp("", "1", "Khong tim thay danh sach file trong request"))

    files = request.files.getlist("files")
    if not files or files[0].filename == "":
        return jsonify(_resp("", "2", "Folder rong hoac chua chon file"))

    _progress.update(
        is_running=True,
        phase="extracting",
        total_files=len(files),
        processed_files=0,
        current_file="",
        message=f"Bat dau trich xuat du lieu cho {len(files)} files...",
    )

    processor = _get_processor()
    uploader = _get_uploader()
    post_processor = _get_post_processor()

    processed_jsons = []
    errors = []

    for file in files:
        _progress.update(current_file=file.filename, message=f"Dang trich xuat JSON: {file.filename}")
        try:
            file_bytes = file.read()
            # Content-derived (not random) so re-uploading the same file after a crash/
            # quota error reuses the same workspace and resumes from its .progress files
            # instead of restarting the whole conversion+extraction pipeline from scratch.
            doc_uuid = hashlib.sha256(file_bytes).hexdigest()[:32]
            ext = os.path.splitext(file.filename)[1].lower()
            perm_path = os.path.join(FILE_STORAGE, f"folder_{doc_uuid}{ext}")
            with open(perm_path, "wb") as f_out:
                f_out.write(file_bytes)

            pdf_path = processor.convert_input2pdf(perm_path)
            if not pdf_path:
                errors.append({"file": file.filename, "error": "Loi convert sang PDF"})
                _progress.increment_processed()
                continue

            result_json = processor.process_file(pdf_path, doc_uuid)

            if pdf_path != perm_path and os.path.exists(pdf_path):
                os.remove(pdf_path)

            if not result_json:
                errors.append({"file": file.filename, "error": "Loi trich xuat (Quota Gemini hoac noi dung rong)"})
                _progress.increment_processed()
                continue

            json_path = os.path.join(FILE_STORAGE_JSON, f"data_{doc_uuid}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result_json, f, ensure_ascii=False, indent=4)
            processed_jsons.append(json_path)

        except Exception as e:
            logger.exception("Unexpected error while processing '%s':", file.filename)
            errors.append({"file": file.filename, "error": str(e)})

        _progress.increment_processed()

    if not processed_jsons:
        _progress.update(is_running=False, phase="error", message="Toan bo file deu loi.")
        return jsonify(_resp({"errors": errors}, "3", "Toan bo file bi loi."))

    try:
        _progress.update(phase="uploading", processed_files=0, total_files=len(processed_jsons))

        for idx, json_path in enumerate(processed_jsons):
            _progress.update(
                current_file=os.path.basename(json_path),
                message=f"Dang nap du lieu len DB ({idx + 1}/{len(processed_jsons)})",
            )
            uploader.upload_data(json_path)
            os.rename(json_path, json_path + ".uploaded")
            _progress.increment_processed()

        _progress.update(
            phase="building_graph",
            current_file="",
            message="Dang chay Hau xu ly (Noi day & Nhung Vector) tren Neo4j...",
        )
        post_processor.run_all()

        _progress.update(is_running=False, phase="completed", message="Hoan tat 100%!")
        return jsonify(_resp({
            "message": "Hoan tat toan bo chu trinh (khong bao gom GraphSAGE - click Train rieng)!",
            "total_success": len(processed_jsons),
            "total_errors": len(errors),
            "errors_detail": errors,
        }))

    except Exception as e:
        _progress.update(is_running=False, phase="error", message=f"Loi Graph/Neo4j: {str(e)}")
        return jsonify(_resp({"errors": errors}, "5", f"Loi he thong: {str(e)}"))


@bp.route("/build_graph", methods=["POST"])
@cross_origin()
def build_graph():
    try:
        uploader = _get_uploader()
        post_processor = _get_post_processor()
        json_files = [f for f in os.listdir(FILE_STORAGE_JSON) if f.endswith(".json")]
        if not json_files:
            return jsonify(_resp("", "1", "Khong co file JSON nao de upload."))

        for fname in json_files:
            uploader.upload_data(os.path.join(FILE_STORAGE_JSON, fname))

        post_processor.run_all()
        return jsonify(_resp(f"Da upload {len(json_files)} file JSON va xay dung Do thi thanh cong!"))
    except Exception as e:
        return jsonify(_resp("", "5", f"Loi he thong: {str(e)}"))


@bp.route("/api/train_graphsage", methods=["POST"])
@cross_origin()
def train_graphsage():
    try:
        driver = _get_uploader().driver
        with driver.session(database="neo4j") as session:
            session.run("CALL gds.graph.drop('traffic_graph', false) YIELD graphName;")
            session.run("""
                CALL gds.graph.project(
                  'traffic_graph',
                  ['Document', 'Article', 'Clause', 'Point', 'Chunk', 'VIOLATION', 'SUBJECT'],
                  {
                    HAS_ARTICLE: {orientation: 'UNDIRECTED'},
                    HAS_CLAUSE: {orientation: 'UNDIRECTED'},
                    HAS_POINT: {orientation: 'UNDIRECTED'},
                    HAS_CHUNK: {orientation: 'UNDIRECTED'},
                    MENTIONED_IN: {orientation: 'UNDIRECTED'}
                  },
                  { nodeProperties: 'embedding' }
                )
            """)
            session.run("""
                CALL gds.beta.graphSage.train(
                  'traffic_graph',
                  {
                    modelName: 'legal_sage_model',
                    featureProperties: ['embedding'],
                    embeddingDimension: 1024,
                    epochs: 10,
                    sampleSizes: [25, 10]
                  }
                )
            """)
            result = session.run("""
                CALL gds.beta.graphSage.write(
                  'traffic_graph',
                  { modelName: 'legal_sage_model', writeProperty: 'structural_embedding' }
                )
            """).single()
            nodes_updated = result.get("nodePropertiesWritten", 0) if result else 0
            session.run("CALL gds.graph.drop('traffic_graph', false) YIELD graphName;")
            session.run("CALL gds.beta.model.drop('legal_sage_model') YIELD modelInfo;")

        return jsonify(_resp({"message": "Huan luyen GraphSAGE hoan tat!", "nodes_updated": nodes_updated}))
    except Exception as e:
        return jsonify(_resp({}, "500", f"Loi qua trinh huan luyen: {str(e)}"))
