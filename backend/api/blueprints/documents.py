from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from backend.core.container import ServiceContainer

bp = Blueprint("documents", __name__)


def _get_uploader():
    from backend.ingestion.upload2neo4j import Neo4jUploader
    return ServiceContainer.get("uploader", Neo4jUploader)


def _resp(data, code="0", msg="Thanh cong"):
    return {"errorCode": code, "errorMessage": msg, "data": data}


@bp.route("/get_system_stats", methods=["GET"])
@cross_origin()
def get_system_stats():
    try:
        driver = _get_uploader().driver
        with driver.session() as session:
            rows = list(session.run(
                "MATCH (d:Document) "
                "OPTIONAL MATCH (d)-[*1..4]->(c:Chunk) "
                "RETURN d.name AS name, d.type AS type, count(c) AS chunk_count"
            ))
            total = session.run("MATCH (c:Chunk) RETURN count(c) AS n").single()["n"]

        doc_list = [
            {
                "name": r["name"] or "Khong ro ten",
                "type": r["type"] or "Khong ro loai",
                "chunk_count": r["chunk_count"] or 0,
            }
            for r in rows
        ]
        return jsonify(_resp({"danh_sach_van_ban": doc_list, "tong_so_doan_van_ban": total}))
    except Exception as e:
        return jsonify(_resp({}, "500", f"Loi truy xuat CSDL: {str(e)}"))


@bp.route("/delete_document", methods=["POST"])
@cross_origin()
def delete_document():
    data = request.json or {}
    doc_name = data.get("document_name", "").strip()
    if not doc_name:
        return jsonify(_resp("", "2", "Ten van ban khong duoc de trong"))

    try:
        driver = _get_uploader().driver
        with driver.session() as session:
            result = session.run(
                "MATCH (d:Document {name: $name}) OPTIONAL MATCH (d)-[]-(c:Chunk) DETACH DELETE d, c",
                name=doc_name,
            )
            nodes_deleted = result.consume().counters.nodes_deleted
        return jsonify(_resp({"message": f"Da xoa: {doc_name}", "nodes_deleted": nodes_deleted}))
    except Exception as e:
        return jsonify(_resp("", "500", f"Loi xoa trong DB: {str(e)}"))
