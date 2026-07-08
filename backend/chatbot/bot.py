import json
import re
import time
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import google.generativeai as genai
from neo4j import GraphDatabase
from backend.config import *
from backend.chatbot.utils import *
from backend.core.embedding import get_embedding_model

logger = logging.getLogger(__name__)


class GraphRAG_Bot:
    def __init__(self):
        genai.configure(api_key=API_KEY)
        self.generation_config = GENERATION_CONFIG
        self.llm_model = genai.GenerativeModel(
            MODEL_FLASH,
            generation_config=self.generation_config
        )
        self.llm_model_3 = genai.GenerativeModel(
            MODEL_3,
            generation_config=self.generation_config
        )
        self.vector_model = get_embedding_model()
        self.driver = GraphDatabase.driver(URI, auth=(USER_NEO4J, PASSWORD_NEO4J))
        self.prompt_rewrite_query = prompt_rewrite_query
        self.prompt_extract_dynamic_aspects = prompt_extract_dynamic_aspects
        self.cypher_query = cypher_query
        self.cypher_query_criminal = cypher_query_criminal

    def close(self):
        self.driver.close()

    def clean_for_lucene(self, text):
        # Làm sạch ký tự đặc biệt
        cleaned = re.sub(r'[^\w\sÀ-ỹ]', ' ', text).strip()
        # Biến các khoảng trắng thành phép toán OR để Lucene dễ thở hơn
        words = [w for w in cleaned.split() if len(w) > 1]
        return " OR ".join(words) if words else cleaned

    def _safe_get_text(self, response):
        if response and response.candidates and response.candidates[0].content.parts:
            return response.text
        return ""

    def rewrite_query(self, user_question, history=None):
        if history is None:
            history = []

        history_text = "\n".join([f"{'Người dùng' if msg['role'] == 'user' else 'Luật sư AI'}: {msg['text']}" for msg in history])
        if not history_text:
            history_text = "Không có lịch sử trò chuyện."

        prompt = self.prompt_rewrite_query.replace("{history_text}", history_text).replace("{user_question}", user_question)

        try:
            response = self.llm_model.generate_content(prompt)
            raw_text = self._safe_get_text(response)

            if not raw_text.strip():
                print(f"⚠️ [Rewrite Query] AI trả về rỗng, dùng câu hỏi gốc.")
                return user_question

            clean_text = re.sub(r'^[“"]|[”"]$', '', raw_text.strip()).strip()
            return clean_text

        except Exception as e:
            logger.error("Lỗi khi Rewrite Query lần 1: %s", e)

            fallback_prompt = self.prompt_rewrite_query.replace("{history_text}", "Không có lịch sử trò chuyện do lỗi hệ thống.").replace("{user_question}", user_question)

            try:
                fallback_response = self.llm_model.generate_content(fallback_prompt)
                raw_fallback_text = self._safe_get_text(fallback_response)

                if not raw_fallback_text.strip():
                    return user_question

                fallback_clean_text = re.sub(r'^[“"]|[”"]$', '', raw_fallback_text.strip()).strip()
                return fallback_clean_text
            except Exception as e_fallback:
                logger.error("Lỗi tại vòng Fallback của Rewrite Query: %s", e_fallback)
                return user_question

    def extract_dynamic_aspects(self, user_question):
        prompt = self.prompt_extract_dynamic_aspects.replace("{user_question}", user_question)

        try:
            response = self.llm_model.generate_content(prompt)
            text = response.text.strip()
            text = re.sub(r'^```json|```$', '', text, flags=re.MULTILINE).strip()
            data = json.loads(text)

            required_keys = [
                "traffic_rules", "administrative_sanctions", "criminal_liability",
                "accident_handling", "license_points", "vehicle_registration",
                "insurance_compensation", "transport_business"
            ]

            for key in required_keys:
                if key not in data or not isinstance(data[key], list):
                    data[key] = []

            return data

        except Exception as e:
            logger.warning("Không thể trích xuất khía cạnh động tự động, chuyển sang fallback câu hỏi gốc. Chi tiết: %s", e)
            core = self.rewrite_query(user_question)
            return {
                "traffic_rules": [core], "administrative_sanctions": [core],
                "criminal_liability": [], "accident_handling": [], "license_points": [],
                "vehicle_registration": [], "insurance_compensation": [], "transport_business": []
            }

    def is_criminal_case(self, user_question, history=None):
        if history is None:
            history = []

        text = user_question.lower()
        for msg in history:
            text += " " + msg.get('text', '').lower()

        criminal_keywords = ["chết", "tử vong", "thiệt mạng", "hình sự", "đi tù", "truy cứu", "án tù"]
        traffic_keywords = ["gây tai nạn", "đâm", "tông", "lái", "xe", "giao thông", "điều khiển"]

        has_criminal = any(k in text for k in criminal_keywords)
        has_traffic = any(k in text for k in traffic_keywords)

        if has_criminal and has_traffic:
            return True

        return False

    def query_concept_graph(self, question_vector, safe_text):
        cypher = self.cypher_query
        with self.driver.session(database="neo4j") as session:
            result = session.run(cypher, question_vector=question_vector, safe_text=safe_text)
            return [r.data() for r in result]

    def run_chatbot(self, user_question, history=None):
        if history is None:
            history = []

        total_start = time.time()

        clean_q = self.rewrite_query(user_question, history)

        is_criminal = self.is_criminal_case(user_question, history)

        q_vec = self.vector_model.encode(clean_q, normalize_embeddings=True).tolist()
        safe_q = self.clean_for_lucene(clean_q)
        if not safe_q.strip(): safe_q = "vi phạm giao thông"
        graph_data = self.query_concept_graph(q_vec, safe_q)

        if is_criminal:
            crim_data = self.query_criminal_graph()
            graph_data = crim_data + graph_data

        if not graph_data:
            yield "Xin lỗi, tôi không tìm thấy quy định pháp luật nào liên quan đến câu hỏi của bạn."
            return

        top_graph_data = graph_data[:15]
        stage3_start = time.time()

        json_result = json.dumps(top_graph_data, ensure_ascii=False, indent=2)

        safe_json_result = json_result

        prompt_result = return_prompt_result(user_question, safe_json_result)

        gemini_messages = []
        for msg in history:
            role = "model" if msg['role'] == "assistant" else "user"
            safe_text = msg["text"][:1000]
            gemini_messages.append({"role": role, "parts": [safe_text]})

        gemini_messages.append({"role": "user", "parts": [prompt_result]})

        has_yielded = False

        try:
            response = self.llm_model.generate_content(gemini_messages, stream=True)
            for chunk in response:
                try:
                    if chunk.candidates and chunk.candidates[0].content.parts:
                        text_data = chunk.text
                        if text_data:
                            print(text_data, end="", flush=True)
                            yield text_data
                            has_yielded = True
                except ValueError:
                    pass

        except Exception as e:
            if not has_yielded and len(history) >= 1:

                gemini_messages_fallback = [{"role": "user", "parts": [prompt_result]}]

                try:
                    response_fallback = self.llm_model.generate_content(gemini_messages_fallback, stream=True)
                    for chunk in response_fallback:
                        try:
                            if chunk.candidates and chunk.candidates[0].content.parts:
                                text_data = chunk.text
                                if text_data:
                                    print(text_data, end="", flush=True)
                                    yield text_data
                                    has_yielded = True
                        except ValueError:
                            pass
                except Exception as e_fallback:
                    logger.error("Lỗi Stream Fallback: %s", e_fallback)
            else:
                logger.error("Lỗi Stream Khởi tạo: %s", e)

        if not has_yielded:
            yield "Xin lỗi, tôi không thể trả lời câu hỏi này do giới hạn an toàn hoặc quá tải hệ thống. Bạn có thể diễn đạt lại ngắn gọn hơn được không?"

    def query_criminal_graph(self):
        cypher = self.cypher_query_criminal
        with self.driver.session(database="neo4j") as session:
            result = session.run(cypher)
            return [r.data() for r in result]

    def run_chatbot_ndjson(self, user_question, history=None):
        """NDJSON streaming variant: emits sources frame first, then token frames.
        Each frame is a dict to be JSON-serialized + newline by the caller.
        """
        if history is None:
            history = []

        clean_q = self.rewrite_query(user_question, history)
        is_criminal = self.is_criminal_case(user_question, history)

        q_vec = self.vector_model.encode(clean_q, normalize_embeddings=True).tolist()
        safe_q = self.clean_for_lucene(clean_q)
        if not safe_q.strip():
            safe_q = "vi pham giao thong"
        graph_data = self.query_concept_graph(q_vec, safe_q)

        if is_criminal:
            graph_data = self.query_criminal_graph() + graph_data

        if not graph_data:
            yield {"type": "sources", "data": {}}
            yield {"type": "token", "data": "Xin loi, toi khong tim thay quy dinh phap luat nao lien quan den cau hoi cua ban."}
            return

        top_graph_data = graph_data[:15]

        # Build citation registry S1..Sn
        sources = {}
        for i, r in enumerate(top_graph_data[:8], 1):
            key = f"S{i}"
            citations = r.get("citations") or []
            chunk_texts = r.get("chunk_texts") or []
            sources[key] = {
                "label": citations[0] if citations else "",
                "text": chunk_texts[0] if chunk_texts else "",
            }

        yield {"type": "sources", "data": sources}

        json_result = json.dumps(top_graph_data, ensure_ascii=False, indent=2)
        prompt_result = return_prompt_result(user_question, json_result)

        gemini_messages = []
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_messages.append({"role": role, "parts": [msg["text"][:1000]]})
        gemini_messages.append({"role": "user", "parts": [prompt_result]})

        has_yielded = False
        try:
            response = self.llm_model.generate_content(gemini_messages, stream=True)
            for chunk in response:
                try:
                    if chunk.candidates and chunk.candidates[0].content.parts:
                        text_data = chunk.text
                        if text_data:
                            yield {"type": "token", "data": text_data}
                            has_yielded = True
                except ValueError:
                    pass
        except Exception as e:
            if not has_yielded and len(history) >= 1:
                try:
                    fb = self.llm_model.generate_content([{"role": "user", "parts": [prompt_result]}], stream=True)
                    for chunk in fb:
                        try:
                            if chunk.candidates and chunk.candidates[0].content.parts:
                                text_data = chunk.text
                                if text_data:
                                    yield {"type": "token", "data": text_data}
                                    has_yielded = True
                        except ValueError:
                            pass
                except Exception as e_fb:
                    logger.error("Loi Stream Fallback: %s", e_fb)
            else:
                logger.error("Loi Stream Khoi tao: %s", e)

        if not has_yielded:
            yield {"type": "token", "data": "Xin loi, toi khong the tra loi cau hoi nay. Ban co the dien dat lai khong?"}