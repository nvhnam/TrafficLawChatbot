import logging
from neo4j import GraphDatabase
from backend.config import *
from backend.core.embedding import get_embedding_model

logger = logging.getLogger(__name__)


class NodeEmbeddingBuilder:

    def __init__(self):
        self.driver = GraphDatabase.driver(URI, auth=(USER_NEO4J, PASSWORD_NEO4J))
        self.model = get_embedding_model()
        self.dimension = self.model.get_sentence_embedding_dimension()
        self.batch_size = 1
        self. schema = {
            "VIOLATION": "value",
            "SUBJECT": "value",
            "PROHIBITED_EXCLUDED": "value",
            "LEGAL_CONCEPT": "value",

            "Document": "name",
            "Article": "name",
            "Clause": "name",
            "Point": "name",
            "Chunk": "content"
        }

    def close(self):
        self.driver.close()

    def run_query(self, cypher, params=None):
        with self.driver.session() as session:
            return [r.data() for r in session.run(cypher, params or {})]

    def create_vector_index(self, label):
        index_name = f"{label.lower()}_vector_index"
        cypher = f"""
        CREATE VECTOR INDEX `{index_name}` IF NOT EXISTS
        FOR (n:{label}) ON (n.embedding)
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {self.dimension},
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        with self.driver.session() as session:
            session.run(cypher)

    def load_nodes(self, label, field):
        return self.run_query(f"""
            MATCH (n:{label})
            WHERE n.{field} IS NOT NULL AND n.embedding IS NULL
            RETURN elementId(n) AS id, n.{field} AS text
        """)

    def embed_batch(self, texts):
        return self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_tensor=True
        ).tolist()

    def save_embeddings(self, label, batch):
        self.run_query(f"""
            UNWIND $batch AS row
            MATCH (n:{label}) WHERE elementId(n) = row.id
            SET n.embedding = row.embedding
        """, {"batch": batch})

    def process_label(self, label, field="value"):
        nodes = self.load_nodes(label, field)
        if not nodes:
            self.create_vector_index(label)
            return
        total = len(nodes)
        for i in range(0, total, self.batch_size):
            batch_nodes = nodes[i:i + self.batch_size]
            texts = [n["text"] for n in batch_nodes]
            embeddings = self.embed_batch(texts)
            batch_data = [
                {"id": batch_nodes[j]["id"], "embedding": embeddings[j]}
                for j in range(len(batch_nodes))
            ]
            self.save_embeddings(label, batch_data)

        self.create_vector_index(label)

    def run_embedding_node(self):
        for label, field in self.schema.items():
            try:
                self.process_label(label, field)
            except Exception as e:
                logger.warning("Node embedding failed for label '%s': %s", label, e)
