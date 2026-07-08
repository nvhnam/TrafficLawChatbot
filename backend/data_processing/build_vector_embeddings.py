from neo4j import GraphDatabase
from backend.config import *
from backend.core.embedding import get_embedding_model


class VectorEmbeddingBuilder:
    def __init__(self):
        self.driver = GraphDatabase.driver(URI, auth=(USER_NEO4J, PASSWORD_NEO4J))
        self.model = get_embedding_model()
        self.batch_size = 4

    def close(self):
        self.driver.close()

    def query(self, cypher_query, parameters=None):
        with self.driver.session() as session:
            result = session.run(cypher_query, parameters or {})
            return [record.data() for record in result]

    def run_embedding_process(self):
        # Đếm số Chunk chưa có vector
        total_query = "MATCH (c:Chunk) WHERE c.embedding IS NULL RETURN count(c) AS total"
        total_chunks = self.query(total_query)[0]['total']

        if total_chunks == 0:
            return
        processed_count = 0

        while True:
            # Lấy từng mẻ Chunk
            chunks_batch = self.query(f"""
                MATCH (c:Chunk) WHERE c.embedding IS NULL 
                RETURN c.id AS id, c.content AS content
                LIMIT {self.batch_size}
            """)

            if not chunks_batch:
                break

            texts_to_embed = [chunk['content'] for chunk in chunks_batch]
            embeddings = self.model.encode(texts_to_embed, normalize_embeddings=True).tolist()

            batch_for_neo4j = [
                {'id': chunk['id'], 'embedding': embeddings[i]}
                for i, chunk in enumerate(chunks_batch)
            ]

            self.query("""
                UNWIND $batch AS data
                MATCH (c:Chunk {id: data.id})
                SET c.embedding = data.embedding
            """, parameters={'batch': batch_for_neo4j})

            processed_count += len(chunks_batch)

