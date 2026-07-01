from data_processing.build_edges import DocumentEdgesBuilder
from data_processing.build_vector_embeddings import VectorEmbeddingBuilder
from data_processing.build_embedding_node import NodeEmbeddingBuilder


class Neo4jPostProcessor:
    def __init__(self):
        # Khởi tạo cả 3 module
        self.edges_builder = DocumentEdgesBuilder()
        self.chunk_embedder = VectorEmbeddingBuilder()
        self.node_embedder = NodeEmbeddingBuilder()

    def run_all(self):

        try:
            self.edges_builder.extract_and_link_relationships()
            self.chunk_embedder.run_embedding_process()
            self.node_embedder.run_embedding_node()

        except Exception as e:
            print(f"\n❌ LỖI NGHIÊM TRỌNG TRONG QUÁ TRÌNH CHẠY: {e}")

        finally:
            self.close_connections()

    def close_connections(self):
        try:
            if hasattr(self.edges_builder, 'driver'):
                self.edges_builder.driver.close()

            self.chunk_embedder.close()
            self.node_embedder.close()
        except Exception as e:
            print(f"⚠️ Lỗi khi đóng kết nối: {e}")


# ================= CÁCH CHẠY =================
# if __name__ == "__main__":
#     post_processor = Neo4jPostProcessor()
#     post_processor.run_all()