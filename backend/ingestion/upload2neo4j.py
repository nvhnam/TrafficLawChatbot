import json
import re
import os
import logging
from neo4j import GraphDatabase
from backend.config import *

logger = logging.getLogger(__name__)

class Neo4jUploader(object):
    def __init__(self):
        self.driver = GraphDatabase.driver(URI, auth=(USER_NEO4J, PASSWORD_NEO4J))
        self.entity_labels = [
            "SUBJECT", "LEGAL_CONCEPT", "DEFINITION", "RIGHT_OBLIGATION",
            "PROHIBITED_EXCLUDED", "VIOLATION", "PENALTY_MEASURE",
            "PROCEDURE_ACTION", "STANDARD_CONDITION", "MONEY_AMOUNT",
            "POINT_DEDUCTION", "OBJECT_EQUIPMENT", "DOCUMENT_RECORD",
            "PHYSICAL_DOCUMENT", "TIME_DURATION", "PERCENTAGE", "TEXT_SEGMENT"
        ]

    def close(self):
        self.driver.close()

    def create_schema_templates(self):
        with self.driver.session() as session:
            hierarchy_labels = ["Document", "Article", "Clause", "Point", "Chunk"]
            for label in hierarchy_labels:
                query = f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE"
                session.run(query)

            for label in self.entity_labels:
                query = f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id_name IS UNIQUE"
                session.run(query)
            try:
                session.run("""
                    CREATE FULLTEXT INDEX chunk_content_index IF NOT EXISTS 
                    FOR (c:Chunk) ON EACH [c.content]
                """)
                logger.info("✅ Đã tạo Full-text Index.")
            except Exception as e:
                logger.error("Lưu ý: Không tạo được Full-text index: %s", e)

            try:
                session.run("""
                    CREATE VECTOR INDEX chunk_vector_index IF NOT EXISTS
                    FOR (c:Chunk) ON (c.embedding)
                    OPTIONS {indexConfig: {
                     `vector.dimensions`: 1024, 
                     `vector.similarity_function`: 'cosine'
                    }}
                """)
            except Exception as e:
                logger.error("Lưu ý: Không tạo được Vector index: %s", e)

    def upload_data(self, input_data):
        self.create_schema_templates()

        chunks = []

        if isinstance(input_data, list):
            chunks = input_data
            logger.info("🚀 ĐANG NHẬN TRỰC TIẾP %d CHUNKS TỪ BỘ NHỚ API...", len(chunks))

        elif isinstance(input_data, str) and os.path.exists(input_data):
            logger.info("🚀 ĐANG ĐỌC DỮ LIỆU TỪ FILE: %s", input_data)
            with open(input_data, 'r', encoding='utf-8') as f:
                try:
                    chunks = json.load(f)
                except json.JSONDecodeError:
                    f.seek(0)
                    for line in f:
                        line = line.strip()
                        if line:
                            chunks.append(json.loads(line))
        else:
            logger.error("❌ LỖI: input_data không hợp lệ! (Không phải List cũng không phải đường dẫn File đúng).")
            return

        logger.info("⏳ ĐANG ĐẨY %d CHUNKS LÊN NEO4J...", len(chunks))
        for line_idx, chunk in enumerate(chunks):
            with self.driver.session() as session:
                session.execute_write(self._process_chunk, chunk, line_idx)

        logger.info("✅ ĐÃ NẠP THÀNH CÔNG LÊN NEO4J!")

    def _process_chunk(self, tx, chunk, chunk_index):
        meta = chunk.get("metadata", {})
        doc_id = meta.get("document", "Văn bản không xác định").strip()
        dieu = str(meta.get("dieu", "")).strip()
        khoan = str(meta.get("khoan", "")).strip()
        diem = str(meta.get("diem", "")).strip()

        chunk_content = chunk.get("original_content", chunk.get("content", "")).strip()

        if not chunk_content: return

        year_match = re.search(r'(19|20)\d{2}', doc_id)
        extracted_year = int(year_match.group()) if year_match else 0
        extracted_type = meta.get("type", "LEGAL_RULE")

        tx.run("""
                    MERGE (d:Document {id: toLower($doc_id)})
                    ON CREATE SET d.name = $doc_id, d.type = $doc_type, d.year = $doc_year
                """,
               doc_id=doc_id, doc_type=extracted_type, doc_year=extracted_year)

        lowest_parent_label = "Document"
        lowest_parent_id = doc_id.lower()
        readable_path = doc_id

        if dieu and dieu.lower() != "none":
            dieu_name = f"Điều {dieu} của {doc_id}"
            readable_path = f"Điều {dieu} - {doc_id}"
            tx.run("""
                MERGE (child:Article {id: toLower($child_name)})
                ON CREATE SET child.name = $child_name
                WITH child MATCH (parent:Document {id: $parent_id})
                MERGE (parent)-[:HAS_ARTICLE]->(child)
            """, child_name=dieu_name, parent_id=lowest_parent_id)
            lowest_parent_label = "Article"
            lowest_parent_id = dieu_name.lower()

            if khoan and khoan.lower() != "none":
                khoan_name = f"Khoản {khoan} {dieu_name}"
                readable_path = f"Khoản {khoan} {readable_path}"
                tx.run("""
                    MERGE (child:Clause {id: toLower($child_name)})
                    ON CREATE SET child.name = $child_name
                    WITH child MATCH (parent:Article {id: $parent_id})
                    MERGE (parent)-[:HAS_CLAUSE]->(child)
                """, child_name=khoan_name, parent_id=lowest_parent_id)
                lowest_parent_label = "Clause"
                lowest_parent_id = khoan_name.lower()

                if diem and diem.lower() != "none":
                    diem_name = f"Điểm {diem} {khoan_name}"
                    readable_path = f"Điểm {diem} {readable_path}"
                    tx.run("""
                        MERGE (child:Point {id: toLower($child_name)})
                        ON CREATE SET child.name = $child_name
                        WITH child MATCH (parent:Clause {id: $parent_id})
                        MERGE (parent)-[:HAS_POINT]->(child)
                    """, child_name=diem_name, parent_id=lowest_parent_id)
                    lowest_parent_label = "Point"
                    lowest_parent_id = diem_name.lower()

        doc_name_clean = doc_id.replace(" ", "_").replace("/", "_").replace("-", "_")

        chunk_node_id = meta.get("chunk_uuid", f"chunk_{doc_name_clean}_{chunk.get('chunk_id', chunk_index)}")

        tx.run(f"""
            MERGE (c:Chunk {{id: $chunk_id}})
            SET c.content = $content, 
                c.metadata_document = $doc_id,
                c.metadata_dieu = $dieu_meta,
                c.metadata_khoan = $khoan_meta,
                c.metadata_diem = $diem_meta,
                c.name = $readable_path
            WITH c MATCH (p:{lowest_parent_label} {{id: $parent_id}})
            MERGE (p)-[:HAS_CHUNK]->(c)
        """,
               chunk_id=chunk_node_id,
               content=chunk_content,
               parent_id=lowest_parent_id,
               doc_id=doc_id,
               dieu_meta=f"Điều {dieu}" if dieu and dieu.lower() != "none" else "",
               khoan_meta=f"Khoản {khoan}" if khoan and khoan.lower() != "none" else "",
               diem_meta=f"Điểm {diem}" if diem and diem.lower() != "none" else "",
               readable_path=f"[{readable_path}]"
               )

        all_entities = (
                chunk.get("Level_3_Foundations", []) +
                chunk.get("Level_2_Rules_Actions", []) +
                chunk.get("Attributes_Measures", [])
        )

        id_mapping = {}

        for ent in all_entities:
            label = ent.get("label", "UNKNOWN").strip()
            if label not in self.entity_labels:
                label = "UNKNOWN"

            name = ent.get("name", "").strip()
            value = ent.get("value", "").strip()
            ent_id = ent.get("id")

            if not name: name = value
            safe_name = name if len(name) <= 1000 else name[:1000]
            global_key = safe_name.lower()
            id_mapping[ent_id] = {"label": label, "global_key": global_key}

            min_val = ent.get("min", 0) if isinstance(ent.get("min"), int) else 0
            max_val = ent.get("max", 0) if isinstance(ent.get("max"), int) else 0

            tx.run(f"""
                MERGE (e:`{label}` {{id_name: $global_key}})
                ON CREATE SET e.name = $name, e.value = $value, e.min = $min_val, e.max = $max_val
                WITH e MATCH (c:Chunk {{id: $chunk_id}})
                MERGE (e)-[:MENTIONED_IN]->(c)
            """,
                   global_key=global_key, name=name, value=value,
                   min_val=min_val, max_val=max_val, chunk_id=chunk_node_id
                   )

        for rel in chunk.get("Relationships", []):
            s_id = rel.get("source")
            t_id = rel.get("target")
            rel_type = rel.get("type", "RELATED_TO").upper().replace(" ", "_")

            if s_id in id_mapping and t_id in id_mapping:
                s_data = id_mapping[s_id]
                t_data = id_mapping[t_id]

                tx.run(f"""
                    MATCH (s:{s_data['label']} {{id_name: $s_val}})
                    MATCH (t:{t_data['label']} {{id_name: $t_val}})
                    MERGE (s)-[:{rel_type}]->(t)
                """, s_val=s_data['global_key'], t_val=t_data['global_key'])