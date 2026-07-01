import json
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from neo4j import GraphDatabase
from config import *


genai.configure(api_key=API_KEY)

class DocumentEdgesBuilder:
    def __init__(self):
        self.model_llm = genai.GenerativeModel(MODEL_PRO, generation_config={"response_mime_type": "application/json"})
        self.driver = GraphDatabase.driver(URI, auth=(USER_NEO4J, PASSWORD_NEO4J))

    def extract_and_link_relationships(self):
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Chunk)
                WHERE (c.content CONTAINS "bãi bỏ" OR c.content CONTAINS "sửa đổi" OR c.content CONTAINS "thay thế" OR c.content CONTAINS "Bãi bỏ" OR c.content CONTAINS "Sửa đổi")
                  AND c.is_rel_extracted IS NULL
                RETURN elementId(c) AS chunk_id, c.metadata_document AS doc_name, c.content AS content
            """)
            chunks = [record.data() for record in result]

        if not chunks:
            return


        for index, item in enumerate(chunks, 1):
            chunk_id = item['chunk_id']
            doc_name = item['doc_name']
            content = item['content']


            prompt = f"""
            Đọc đoạn văn bản pháp luật sau và trích xuất các mối quan hệ "Bãi bỏ", "Sửa đổi", "Thay thế", "Hướng dẫn".
            Văn bản gốc đang xét (Source): "{doc_name}"
            Nội dung: "{content}"

            Trả về ĐÚNG định dạng JSON array:
            [
              {{"source": "{doc_name}", "target": "Nghị định số 100/2019/NĐ-CP", "relation": "BAI_BO"}}
            ]

            Quy tắc: 
            1. Nếu không có quan hệ nào, trả về mảng rỗng []. 
            2. Chỉ dùng các relation: BAI_BO, SUA_DOI, THAY_THE, HUONG_DAN.
            3. Tên "target" phải đầy đủ (VD: "Luật Giao thông đường bộ 2008" hoặc "Nghị định số 100/2019/NĐ-CP").
            """

            try:
                response = self.model_llm.generate_content(prompt)

                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:-3].strip()
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:-3].strip()

                relations = json.loads(raw_text)

                with self.driver.session() as session:
                    for rel in relations:
                        source_doc = rel.get("source", "").strip()
                        target_doc = rel.get("target", "").strip()

                        if not source_doc or not target_doc:
                            continue

                        rel_type = rel.get("relation", "RELATED_TO").upper().replace(" ", "_")

                        cypher_edge = f"""
                        MATCH (s:Document) WHERE toLower(s.name) = toLower($source)
                        MATCH (t:Document) WHERE toLower(t.name) CONTAINS toLower($target)
                        MERGE (s)-[:`{rel_type}`]->(t)
                        """
                        session.run(cypher_edge, source=source_doc, target=target_doc)

                    session.run("MATCH (c:Chunk) WHERE elementId(c) = $chunk_id SET c.is_rel_extracted = true", chunk_id=chunk_id)

                time.sleep(3)

            except ResourceExhausted as e:
                break

            except json.JSONDecodeError:
                with self.driver.session() as session:
                    session.run("MATCH (c:Chunk) WHERE elementId(c) = $chunk_id SET c.is_rel_extracted = 'json_error'", chunk_id=chunk_id)

            except Exception as e:
                break