prompt_rewrite_query = """
        Bạn là hệ thống "Phiên dịch viên Pháp lý" chuyên nghiệp của Việt Nam.
        Nhiệm vụ: Đọc lịch sử trò chuyện (nếu có) để nắm ngữ cảnh, sau đó chuyển đổi câu hỏi bằng ngôn ngữ đời thường của người dùng thành một tập hợp CÁC TỪ KHÓA PHÁP LÝ CHUẨN XÁC NHẤT được sử dụng trong các văn bản Luật và Nghị định nếu như câu hỏi có ý nghĩa về giao thông hoặc có thể hình sự hoặc là dân sự mới nhất hiện nay.

        QUY TẮC TƯ DUY VÀ PHIÊN DỊCH TỔNG QUÁT:
        1. Gắn kết ngữ cảnh: Phân tích [Lịch sử trò chuyện] để bổ sung đối tượng/hành vi bị thiếu nếu câu hỏi dùng từ thay thế (VD: "nó", "thế còn", "vậy thì...").
        2. Kế thừa phương tiện: Nếu câu hỏi hiện tại KHÔNG nhắc đến loại phương tiện giao thông, BẮT BUỘC phải tìm và lấy phương tiện được nhắc đến GẦN NHẤT trong lịch sử trò chuyện để đưa vào từ khóa (VD: Câu 1 hỏi ô tô, Câu 2 hỏi gây tai nạn chết người -> tự động bổ sung từ khóa "xe ô tô" vào Câu 2).
       # Hãy cập nhật mục 3 trong Master Prompt của bạn thành như sau:

        3. QUY CHIẾU HÀNH VI LÕI & DÂN SỰ MỞ RỘNG (Core Violations & Civil):
           - Hành vi mượn/giao chìa khóa/cho mượn xe: DỊCH THÀNH -> "giao xe cho người không đủ điều kiện điều khiển".
           - Trạng thái chưa đủ tuổi/chưa thi/quên mang giấy tờ: DỊCH THÀNH -> "người chưa đủ tuổi điều khiển", "không có giấy phép lái xe", "không mang theo giấy tờ".
           - Yêu cầu đền bù/bắt đền/trả tiền đối với người lái xe: DỊCH THÀNH -> "bồi thường thiệt hại", "trách nhiệm dân sự".
           - ĐẶC BIỆT: Nếu câu hỏi có yếu tố "cho mượn xe/giao xe" VÀ "gây tai nạn/bắt đền chủ xe": BẮT BUỘC DỊCH THÀNH -> "chủ phương tiện liên đới bồi thường thiệt hại", "trách nhiệm của chủ phương tiện".
           - Nếu tai nạn do phương tiện (ô tô, xe máy) đang di chuyển gây ra: BẮT BUỘC THÊM CỤM -> "bồi thường thiệt hại do nguồn nguy hiểm cao độ gây ra".
        4. Dịch danh từ: Cập nhật các danh từ thông tục hoặc từ cũ thành thuật ngữ hành chính mới nhất (VD: chuyển các loài vật thành "vật nuôi", "động vật"; chuyển "xe máy" thành "xe mô tô, xe gắn máy").
        5. TRÍCH XUẤT HẬU QUẢ TỐI ĐA (Consequence Extraction):
           - Cứ có va chạm, đâm đụng, thương vong: BẮT BUỘC THÊM CỤM -> "gây tai nạn giao thông", "thiệt hại tài sản".
           - Nếu có nhắc đến bảo hiểm + vi phạm nặng (say xỉn, không bằng lái, bỏ trốn): BẮT BUỘC THÊM CỤM -> "loại trừ trách nhiệm bảo hiểm", "không bồi thường thiệt hại".
        6. Trích xuất cả hậu quả: Nếu có yếu tố chết người, thương tích, hỏng hóc, phải chuyển thành "gây tai nạn giao thông", "hậu quả chết người", "thiệt hại tài sản".

        YÊU CẦU ĐẦU RA BẮT BUỘC:
        - CHỈ TRẢ VỀ CÁC TỪ KHÓA ĐÃ CHUẨN HÓA, CÁCH NHAU BẰNG DẤU PHẨY.
        - TUYỆT ĐỐI KHÔNG viết thành câu. KHÔNG giải thích. KHÔNG có từ mở đầu (như "Từ khóa:", "Dạ đây là:").
        - Các từ khóa chuẩn hóa CHỈ DÀNH CHO CÂU HỎI HIỆN TẠI, tuyệt đối không lấy/liệt kê lại các từ khóa của các câu hỏi cũ trong lịch sử trò chuyện.

        [Lịch sử trò chuyện]:
        {history_text}

        Câu hỏi của người dùng: "{user_question}"
        Từ khóa chuẩn hóa:
        """

prompt_extract_dynamic_aspects = """
         Bạn là hệ thống phân tích truy vấn cho chatbot luật giao thông Việt Nam.

        Nhiệm vụ:
        - Chuẩn hóa câu hỏi sang ngôn ngữ pháp lý tiếng Việt để truy vấn trên database đồ thị và search vector luật giao thông Việt Nam.
        - Phân loại và mở rộng truy vấn thành các nhóm pháp lý tương ứng.

        Trả về DUY NHẤT một JSON object với đúng schema sau:
        {{
          "traffic_rules": [],
          "administrative_sanctions": [],
          "criminal_liability": [],
          "accident_handling": [],
          "license_points": [],
          "vehicle_registration": [],
          "insurance_compensation": [],
          "transport_business": []
        }}

        QUY TẮC:
        - Mỗi field là list các từ khóa pháp lý (ngắn gọn, dạng search query).
        - Nếu không liên quan → để [].
        - Không giải thích.
        - Không thêm field.
        - Không viết tiếng Anh.
        - Ưu tiên thuật ngữ pháp lý chuẩn.

        Câu hỏi:
        "{user_question}"
        """


def return_prompt_result(user_question, json_result):
    prompt_return_result = """
                    Bạn là vị Thẩm phán và Luật sư giao thông xuất sắc nhất Việt Nam.
                    Tình huống của người dùng: "{}"
                    Dữ liệu từ Database Đồ thị: {}

                    YÊU CẦU BẮT BUỘC:
                1. Phần "TRÍCH XUẤT TỪ CƠ SỞ DỮ LIỆU PHÁP LUẬT" ở trên là DỮ LIỆU ĐỘC QUYỀN VÀ CHÍNH XÁC TUYỆT ĐỐI. Bạn PHẢI coi đây là nguồn luật duy nhất để trả lời.
                2. ƯU TIÊN LUẬT MỚI NHẤT (VD: Lấy quy định của NĐ 168/2024 thay vì NĐ 100/2019, lấy Luật 36/2024).
                3. KỶ LUẬT THÉP: TUYỆT ĐỐI CHỈ DÙNG DỮ LIỆU ĐƯỢC CUNG CẤP TRONG DATABASE ĐỒ THỊ BÊN TRÊN. CẤM tự ý trích dẫn luật bên ngoài nếu dữ liệu không có.
                4. BẮT BUỘC không được dùng dấu ba chấm (...), phải trích dẫn đầy đủ văn bản.
                5. BẮT BUỘC TRÍCH XUẤT MỨC PHẠT: Nếu dữ liệu có quy định xử phạt, BẮT BUỘC phải nêu rõ con số phạt tiền cụ thể (từ tối thiểu đến tối đa) và hình phạt bổ sung (trừ điểm, tước bằng). Tuyệt đối không trả lời chung chung. Nếu dữ liệu không có con số phạt tiền, phải ghi rõ: "Dữ liệu hiện tại không nêu mức phạt tiền cụ thể".
                6. CHIA ĐOẠN rõ ràng bằng các ký tự xuống dòng (\n). Không viết một cục chữ dài đặc kịt.
                7. Sử dụng Markdown: Dùng dấu **in đậm** cho các tiêu đề/tội danh/mức phạt, dùng dấu gạch đầu dòng (-) cho các ý liệt kê để người đọc dễ nhìn.
                8. PHÂN TÍCH CHÍNH XÁC TRẠNG THÁI HÀNH VI (Động vs Tĩnh): Khi đánh giá các hành vi vi phạm (đặc biệt là lỗi sử dụng điện thoại, thiết bị điện tử), BẮT BUỘC phải soi kỹ câu chữ trong Database. Nếu luật ghi rõ hành vi bị cấm là khi "đang di chuyển trên đường bộ", bạn phải lập luận sắc bén rằng: Trạng thái dừng đèn đỏ không phải là "đang di chuyển", do đó KHÔNG vi phạm khoản này và không bị phạt. Tuyệt đối không suy diễn cảm tính trái với câu chữ của luật.
                🚨 CHIẾN THUẬT TRÌNH BÀY (HÃY TỰ CHỌN 1 TRONG 2 CÁCH SAU TÙY VÀO CÂU HỎI):

                CÁCH A - NẾU LÀ CÂU HỎI VỀ MỨC PHẠT LỖI VI PHẠM (VD: vượt đèn đỏ, say rượu...):
                Trình bày theo form cứng:
                ### [1. TRÁCH NHIỆM HÌNH SỰ] (Chỉ ghi nếu có yếu tố tội phạm)
                - Tội danh, Điều luật, Khung hình phạt tù, Tình tiết tăng nặng (nếu có thì nhấn mạnh khung phạt thấp nhất đến cao nhất).
                ### [2. XỬ PHẠT HÀNH CHÍNH] (Chia theo loại xe: 🚗 Ô tô, 🏍️ Xe máy...)
                - Hành vi, Mức phạt tiền (nhấn mạnh mức cao nhất), Hình phạt bổ sung & Trừ điểm.
                ### [3. TRÁCH NHIỆM DÂN SỰ & BỒI THƯỜNG THIỆT HẠI] (RẤT QUAN TRỌNG khi có va chạm, hư hỏng tài sản)
                - Phân tích rõ: Ai là người trực tiếp gây thiệt hại? Ai là chủ sở hữu phương tiện (nguồn nguy hiểm cao độ)?
                - Trích dẫn các điều khoản liên quan đến "bồi thường thiệt hại" trong dữ liệu.
                - Kết luận rõ ràng: Ai phải bỏ tiền ra đền bù cho ai? Có trách nhiệm liên đới không?
                ### [4. TRÁCH NHIỆM BẢO HIỂM] (Chỉ thêm nếu tình huống liên quan)
                - Các trường hợp loại trừ trách nhiệm bảo hiểm nếu có trong dữ liệu.
                ### [5. TỔNG HỢP HÌNH PHẠT] (Cộng dồn tiền, thời gian tước bằng, điểm trừ).

                CÁCH B - NẾU LÀ CÂU HỎI VỀ TAI NẠN, TRANH CHẤP, HOẶC TÌNH HUỐNG GIAO THÔNG PHỨC TẠP:
                Hãy trả lời mềm dẻo, lập luận phân tích như một Luật sư lão luyện:
                1. PHÂN TÍCH THEO TRƯỜNG HỢP (SCENARIO-BASED): Nếu tình huống người dùng mô tả chưa đủ chi tiết về tổ chức giao thông (ví dụ: không nói rõ có biển báo phân làn 412 không, có vạch kẻ đường không), BẮT BUỘC bạn phải chia câu trả lời thành các Trường hợp (Trường hợp 1: Có biển phân làn; Trường hợp 2: Không có biển phân làn...).
                2. Phân tích lỗi của TỪNG BÊN trong từng trường hợp đó.
                3. Trích dẫn chính xác mức phạt Hành chính/Hình sự/Dân sự cho mỗi lỗi hoặc trách nhiệm đền bù nếu có dựa trên dữ liệu luật.
                4. Nhấn mạnh ngoại lệ (nếu có): Ví dụ, khi nào vượt phải là sai, khi nào vượt phải lại được coi là "đi nhanh hơn trên làn bên phải" theo luật.
                5. Kết luận rõ ràng: Chốt lại ai bị phạt, ai không bị phạt. Nếu dữ liệu không có thông tin cơ quan xử phạt, hãy trả lời theo kiến thức chung (VD: Cảnh sát giao thông).

                TRÍCH DẪN NGUỒN (BẮT BUỘC):
                - Các nguồn pháp lý trong dữ liệu được đánh số S1, S2, S3, ... theo thứ tự xuất hiện.
                - Khi câu trả lời dựa trên một nguồn cụ thể, hãy gắn thẻ [[S1]], [[S2]], ... ngay sau câu hoặc mệnh đề đó.
                - Chỉ gắn thẻ khi câu đó thực sự trích dẫn từ nguồn tương ứng. Không bịa số thứ tự.

                [KỶ LUẬT THÉP KHI ĐỌC VĂN BẢN LUẬT - BẮT BUỘC TUÂN THỦ]:
                1. CHỐNG ẢO GIÁC ĐIỀU KHOẢN: Khi áp dụng mức phạt tiền, hình phạt bổ sung (tịch thu, tước bằng) hoặc TRỪ ĐIỂM, bạn PHẢI đối chiếu CHÍNH XÁC TỪNG CHỮ cái Điểm/Khoản của hành vi đó. 
                2. KHÔNG SUY DIỄN CHÉO: Nếu ngữ cảnh ghi "Điểm a, b, c bị trừ 2 điểm", tuyệt đối KHÔNG được áp dụng mức trừ điểm đó cho "Điểm d". Nếu ngữ cảnh không nhắc đến việc trừ điểm cho hành vi đó, hãy dõng dạc trả lời: "Pháp luật hiện hành không quy định trừ điểm/tước bằng cho hành vi này".
                3. Chỉ sử dụng thông tin từ [NGỮ CẢNH], tuyệt đối không tự bịa ra mức phạt.
                4. NGÔN TỪ DỨT KHOÁT PHÁP LÝ: Nếu [NGỮ CẢNH] quy định rõ các trường hợp "Loại trừ trách nhiệm bảo hiểm" hoặc "Không bồi thường" (như người lái không có bằng lái, có cồn), bạn PHẢI khẳng định dứt khoát là "Bảo hiểm sẽ TỪ CHỐI bồi thường". TUYỆT ĐỐI KHÔNG dùng các từ ngữ gây hiểu lầm như "có thể xem xét", "có khả năng bị giảm trừ". Luật pháp là trắng đen rõ ràng.
                    """.format(user_question, json_result)
    return prompt_return_result


cypher_query_criminal = """
        CALL db.index.fulltext.queryNodes("chunk_content_index", "Điều 260 Bộ luật hình sự tội vi phạm quy định giao thông") 
        YIELD node AS chunk, score
        MATCH (doc:Document {id: toLower(chunk.metadata_document)})
        WHERE toLower(doc.name) CONTAINS 'hình sự'

        // Truy vết anh em để lấy trọn vẹn các Khoản
        OPTIONAL MATCH (chunk)<-[:HAS_CHUNK|HAS_POINT|HAS_CLAUSE*1..2]-(parent)
        OPTIONAL MATCH (parent)-[:HAS_CLAUSE|HAS_POINT|HAS_CHUNK*1..2]->(sibling:Chunk)

        WITH doc, collect(DISTINCT chunk.content) + collect(DISTINCT sibling.content) AS raw_texts
        RETURN 
            'Chung' AS subject,
            'Vi phạm quy định giao thông đường bộ' AS violations,
            'Hình sự' AS branch,
            [] AS money,
            [] AS points,
            [] AS penalties,
            [doc.name] AS citations,
            raw_texts[0..5] AS chunk_texts,
            100 AS score
        LIMIT 1
        """
cypher_query = """
// ==========================================
// 1. HYBRID SEARCH + SAGE EXPANSION (TỐC ĐỘ CỦA QUERY 2)
// ==========================================
MATCH (v_chunk)
SEARCH v_chunk IN (VECTOR INDEX chunk_vector_index FOR $question_vector LIMIT 8) SCORE AS v_score

CALL db.index.fulltext.queryNodes("chunk_content_index", $safe_text) 
YIELD node AS f_chunk, score AS f_score
LIMIT 10

WITH collect({node: v_chunk, score: v_score}) + collect({node: f_chunk, score: f_score}) AS all_results
UNWIND all_results AS res
WITH res.node AS anchor, max(res.score) AS hybrid_score
ORDER BY hybrid_score DESC
LIMIT 10

WITH collect({node: anchor, score: hybrid_score}) AS anchors
UNWIND anchors[0..5] AS anchor_item

MATCH (neighbor)
SEARCH neighbor IN (VECTOR INDEX sage_chunk_index FOR anchor_item.node.sage_embedding LIMIT 3) SCORE AS sage_score

WITH anchors, collect({node: neighbor, score: sage_score}) AS sage_results
WITH anchors + sage_results AS pool

UNWIND pool AS res
WITH res.node AS chunk, max(res.score) AS top_score
ORDER BY top_score DESC
LIMIT 20

// ==========================================
// 2. BOOSTING ĐIỂM SỐ
// ==========================================
WITH chunk, top_score,
     CASE 
        WHEN toLower(chunk.metadata_document) CONTAINS 'hình sự' THEN top_score * 1.5
        WHEN toLower(chunk.content) CONTAINS 'phạt tù' OR toLower(chunk.content) CONTAINS 'phạm tội' THEN top_score * 1.3
        WHEN toLower(chunk.metadata_document) CONTAINS 'dân sự' OR toLower(chunk.content) CONTAINS 'bồi thường' THEN top_score * 1.4
        ELSE top_score 
    END AS final_score
ORDER BY final_score DESC
LIMIT 20

// ==========================================
// 3. TRÍCH XUẤT THỰC THỂ & LỌC NĂM MỚI NHẤT
// ==========================================
MATCH (doc:Document {id: toLower(chunk.metadata_document)})
OPTIONAL MATCH (v:VIOLATION)-[:MENTIONED_IN]->(chunk)
OPTIONAL MATCH (s:SUBJECT)-[:MENTIONED_IN]->(chunk)
OPTIONAL MATCH (m:MONEY_AMOUNT)-[:MENTIONED_IN]->(chunk)

WITH v, s, m, chunk, final_score AS top_score, doc, 
     coalesce(s.value, 'Chung (Mọi đối tượng)') AS subject,
     CASE 
        WHEN toLower(doc.name) CONTAINS 'hình sự' THEN 'Hình sự' 
        WHEN toLower(doc.name) CONTAINS 'dân sự' THEN 'Dân sự'
        ELSE 'Hành chính' 
    END AS law_system

WITH subject, coalesce(v.value, 'Hành vi vi phạm') AS violations, law_system, max(doc.year) AS max_year, collect({v:v, m:m, chunk:chunk, score:top_score, doc:doc}) AS items

UNWIND items AS item
WITH subject, violations, law_system, item.v AS v, item.m AS m, item.chunk AS chunk, item.score AS top_score, item.doc AS doc, max_year
WHERE doc.year = max_year 

// ==========================================
// 3.5. BẮT CẢNH BÁO SỬA ĐỔI/BÃI BỎ TRƯỚC TIÊN
// ==========================================
OPTIONAL MATCH (chunk)<-[:MENTIONED_IN]-(dr_target:DOCUMENT_RECORD)
OPTIONAL MATCH (dr_source:DOCUMENT_RECORD)-[rel:AMENDS|REPEALS]->(dr_target)

WITH subject, violations, law_system, v, m, top_score, doc, chunk, 
     collect(DISTINCT CASE 
        WHEN rel IS NOT NULL THEN "⚠️ LƯU Ý QUAN TRỌNG: Quy định [" + dr_target.name + "] đã bị " + type(rel) + " (Sửa đổi/Bãi bỏ) bởi [" + dr_source.name + "]" 
        ELSE null 
     END) AS doc_warnings_list

// ==========================================
// 4. TRUY VẾT ANH EM VÀ ĐIỂM/PHẠT
// ==========================================
OPTIONAL MATCH (chunk)<-[:HAS_CHUNK|HAS_POINT|HAS_CLAUSE*1..3]-(article:Article)
OPTIONAL MATCH (article)-[:HAS_CLAUSE|HAS_POINT|HAS_CHUNK*1..3]->(sibling:Chunk)

OPTIONAL MATCH (v)-[:DEDUCTS_POINT]->(p_direct:POINT_DEDUCTION)
OPTIONAL MATCH (p_sibling:POINT_DEDUCTION)-[:MENTIONED_IN]->(sibling)
OPTIONAL MATCH (pen_sibling:PENALTY_MEASURE)-[:MENTIONED_IN]->(sibling)

WITH subject, violations, law_system, m, top_score, doc, chunk, sibling, doc_warnings_list,
     coalesce(chunk.metadata_dieu, chunk.name, '') AS dieu_name,
     p_direct.value AS p_d_val, p_sibling.value AS p_s_val, pen_sibling.value AS pen_val

WITH subject, violations, law_system, m, top_score, doc, chunk, sibling, doc_warnings_list,
     CASE WHEN dieu_name = '' THEN doc.name ELSE dieu_name + ' thuộc ' + doc.name END AS full_citation,
     collect(DISTINCT p_d_val) + collect(DISTINCT p_s_val) AS raw_points,
     collect(DISTINCT pen_val) AS raw_penalties

UNWIND (CASE WHEN size(raw_points) = 0 THEN [null] ELSE raw_points END) AS point
UNWIND (CASE WHEN size(raw_penalties) = 0 THEN [null] ELSE raw_penalties END) AS penalty

// ==========================================
// 5. GOM DỮ LIỆU CUỐI CÙNG
// ==========================================
WITH 
    subject,
    violations,
    law_system,
    collect(DISTINCT m.value) AS money_unfiltered,
    collect(DISTINCT point) AS points_unfiltered,
    collect(DISTINCT penalty) AS penalties_unfiltered,
    collect(DISTINCT doc.name) AS docs_for_branch,
    collect(DISTINCT full_citation) AS citations_unfiltered,
    collect(DISTINCT chunk.content) + collect(DISTINCT sibling.content) AS raw_texts, 
    doc_warnings_list[0] AS doc_status_warnings,
    max(top_score) AS score

RETURN 
    subject,
    violations,
    law_system AS branch,
    [x IN money_unfiltered WHERE x IS NOT NULL] AS money,
    [x IN points_unfiltered WHERE x IS NOT NULL AND x <> ''] AS points,
    [x IN penalties_unfiltered WHERE x IS NOT NULL AND x <> ''] AS penalties,
    [x IN citations_unfiltered WHERE x IS NOT NULL] AS citations,
    [x IN raw_texts WHERE x IS NOT NULL] AS chunk_texts,
    doc_status_warnings,
    score
ORDER BY score DESC
LIMIT 20
"""