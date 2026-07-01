import glob
import os
import json
# from create_chunk_text import LegalSemanticSplitter
from create_chunk_text import LegalSemanticSplitter


def create_chunk(file_path, folder_save):
    os.makedirs(folder_save, exist_ok=True)
    # 2. Kiểm tra file có tồn tại không
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy file '{file_path}'")
        return

    # 3. Đọc nội dung file Markdown
    with open(file_path, "r", encoding="utf-8") as file:
        markdown_text = file.read()

    # 4. Khởi tạo Splitter và cắt văn bản
    doc_name = os.path.basename(file_path).replace(".md", "")
    splitter = LegalSemanticSplitter()

    legal_chunks = splitter.split_text(markdown_text)

    # 5. In kết quả 
    print(f"Đã cắt thành công {len(legal_chunks)} chunks từ file {file_path}.\n")

    # In thử 3 chunk đầu tiên để kiểm tra
    print(json.dumps(legal_chunks[:3], ensure_ascii=False, indent=2))

    name_json = os.path.basename(file_path).replace(".md", "")
    path_json = os.path.join(folder_save, name_json + ".json")
    # Nếu muốn lưu toàn bộ chunk ra file json:
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(legal_chunks, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    list_files = glob.glob(os.path.join("/home/manh/Code/my_final_project/data_check_call_gemini" + "/*.md"))
    folder_save = "/home/manh/Code/my_final_project/data_bosung_chunks_v3"

    for file_path in list_files:
        create_chunk(file_path, folder_save)
