/**
 * mock-api.js - Dịch vụ giả lập Streaming API (SSE) với nội dung chuyên sâu (300-500 từ)
 */

const RESPONSES = [
    `# CHI TIẾT QUY ĐỊNH VỀ NỒNG ĐỘ CỒN THEO NGHỊ ĐỊNH 100/2019/NĐ-CP

Việc điều khiển phương tiện giao thông sau khi sử dụng rượu bia là một trong những nguyên nhân hàng đầu gây ra tai nạn giao thông nghiêm trọng tại Việt Nam. Kể từ khi Nghị định 100/2019/NĐ-CP (được sửa đổi, bổ sung bởi Nghị định 123/2021/NĐ-CP) có hiệu lực, mức xử phạt đối với hành vi này đã tăng lên rất cao nhằm tăng tính răn đe.

### 1. Đối với người điều khiển xe máy:
- **Mức 1:** Nồng độ cồn chưa vượt quá 50 miligam/100 mililít máu hoặc chưa vượt quá 0,25 miligam/1 lít khí thở. Phạt tiền từ **2 đến 3 triệu đồng**. Tước giấy phép lái xe (GPLX) từ **10 đến 12 tháng**.
- **Mức 2:** Nồng độ cồn vượt quá 50 miligam đến 80 miligam/100 mililít máu hoặc vượt quá 0,25 miligam đến 0,4 miligam/1 lít khí thở. Phạt tiền từ **4 đến 5 triệu đồng**. Tước GPLX từ **16 đến 18 tháng**.
- **Mức 3:** Nồng độ cồn vượt quá 80 miligam/100 mililít máu hoặc vượt quá 0,4 miligam/1 lít khí thở. Phạt tiền từ **6 đến 8 triệu đồng**. Tước GPLX từ **22 đến 24 tháng**.

### 2. Đối với người điều khiển xe ô tô:
- **Mức 1:** Phạt tiền từ **6 đến 8 triệu đồng**. Tước GPLX từ **10 đến 12 tháng**.
- **Mức 2:** Phạt tiền từ **16 đến 18 triệu đồng**. Tước GPLX từ **16 đến 18 tháng**.
- **Mức 3:** Phạt tiền từ **30 đến 40 triệu đồng**. Tước GPLX từ **22 đến 24 tháng**.

### 3. Các quy định bổ sung quan trọng:
- Việt Nam áp dụng chính sách **"Không nồng độ cồn"**, nghĩa là chỉ cần có hơi men trong người khi lái xe là đã vi phạm, không có ngưỡng tối thiểu an toàn.
- Ngoài phạt tiền và tước bằng, phương tiện vi phạm thường sẽ bị **tạm giữ tối đa đến 07 ngày** trước khi ra quyết định xử phạt.
- Đối với hành vi không chấp hành yêu cầu kiểm tra nồng độ cồn của người thực hiện nhiệm vụ, mức phạt sẽ được áp dụng tương đương với **Mức 3 (mức cao nhất)**.

Việc hiểu rõ các mức phạt này không chỉ giúp bạn tránh thiệt hại về kinh tế mà quan trọng hơn hết là bảo vệ tính mạng của bản thân và những người xung quanh. "Đã uống rượu bia, không lái xe" luôn là khẩu hiệu hàng đầu cho sự an toàn của mọi gia đình.`,

    `# HƯỚNG DẪN TOÀN DIỆN VỀ HỆ THỐNG BIỂN BÁO HIỆU ĐƯỜNG BỘ VIỆT NAM (QCVN 41:2019/BGTVT)

Hệ thống biển báo hiệu đường bộ là "ngôn ngữ" chung giữa người tham gia giao thông và các cơ quan quản lý. Theo Quy chuẩn kỹ thuật quốc gia QCVN 41:2019/BGTVT, hệ thống biển báo tại Việt Nam được chia thành 5 nhóm chính với các đặc điểm nhận dạng riêng biệt.

### 1. Nhóm biển báo cấm (Hình tròn, viền đỏ, nền trắng, hình vẽ đen)
Biển báo cấm biểu thị các điều cấm mà người tham gia giao thông không được vi phạm. 
- **Đặc điểm:** Viền đỏ nổi bật trên nền trắng. 
- **Các biển phổ biến:** Cấm đi ngược chiều (P.102), Cấm đỗ xe (P.131a), Cấm rẽ trái (P.123a). 
- **Lưu ý:** Hiệu lực của biển báo cấm bắt đầu từ vị trí đặt biển đến ngã ba, ngã tư tiếp theo hoặc đến vị trí có biển "Hết tất cả các lệnh cấm".

### 2. Nhóm biển hiệu lệnh (Hình tròn, nền xanh lam, hình vẽ trắng)
Biển hiệu lệnh đưa ra các chỉ dẫn bắt buộc người tham gia giao thông phải thi hành.
- **Đặc điểm:** Hình tròn màu xanh đặc trưng.
- **Các biển phổ biến:** Các xe chỉ được đi thẳng (R.301a), Đường dành cho người đi bộ (R.305).

### 3. Nhóm biển báo nguy hiểm (Hình tam giác đều, viền đỏ, nền vàng, hình vẽ đen)
Nhóm này có tác dụng cảnh báo các tình huống nguy hiểm phía trước để lái xe chủ động giảm tốc độ.
- **Đặc điểm:** Hình tam giác vàng rực rỡ, dễ quan sát từ xa.
- **Các biển phổ biến:** Chỗ ngoặt nguy hiểm (W.201), Đường trơn (W.213), Giao nhau có tín hiệu đèn (W.209).

### 4. Nhóm biển chỉ dẫn (Hình vuông/Chữ nhật, nền xanh lam, hình vẽ trắng)
Nhóm này cung cấp các thông tin hữu ích về đường xá, địa điểm.
- **Ví dụ:** Vị trí quay xe (I.409), Trạm cấp cứu (I.427), Tên đường/Cầu.

### 5. Nhóm biển phụ và Vạch kẻ đường
Biển phụ được đặt dưới các biển chính để bổ sung thông tin như khoảng cách, đối tượng bị cấm (ví dụ: cấm riêng xe tải). Vạch kẻ đường cũng là một dạng báo hiệu quan trọng, giúp phân làn và hướng dẫn hướng đi hợp lý.

### Tầm quan trọng của việc nắm vững biển báo:
Việc nhầm lẫn giữa biển báo nguy hiểm và biển báo cấm có thể dẫn đến những tình huống xử lý sai lầm. Hãy luôn ghi nhớ: **Đỏ là Cấm, Vàng là Nguy hiểm, Xanh là Chỉ dẫn/Hiệu lệnh**. Chúc bạn vạn dặm bình an!`,

    `# QUY TẮC NHƯỜNG ĐƯỜNG VÀ CÁC LỖI VI PHẠM TẠI NÚT GIAO THÔNG PHỨC TẠP

Ngã ba, ngã tư và vòng xuyến là những khu vực có mật độ giao thông dày đặc, nơi dễ xảy ra va chạm và ùn tắc nếu người lái xe không tuân thủ quy tắc nhường đường. Dưới đây là phân tích chi tiết về quy tắc đi đường tại các khu vực này theo Luật Giao thông đường bộ.

### 1. Tại nơi giao nhau không có báo hiệu đi theo vòng xuyến:
Quy tắc vàng là **"Nhường đường cho xe đi đến từ phía bên phải"**.
- Nếu bạn đang ở ngã tư không có đèn xanh đèn đỏ và không có biển ưu tiên, bạn phải quan sát xe từ phía bên phải của mình. Nếu có xe đang tới, bạn phải dừng lại nhường đường.
- Xe đi từ đường không ưu tiên phải nhường đường cho xe đang đi trên đường ưu tiên hoặc đường chính từ bất kỳ hướng nào tới.

### 2. Tại nơi giao nhau có báo hiệu đi theo vòng xuyến (Bùng binh):
Quy tắc lúc này sẽ ngược lại: **"Nhường đường cho xe đi đến từ phía bên trái"**.
- Khi bắt đầu vào vòng xuyến, bạn phải nhường cho những xe đã ở trong vòng xuyến trước đó (phía bên trái của bạn).

### 3. Quy tắc nhường đường cho xe ưu tiên:
Người tham gia giao thông phải giảm tốc độ, tránh hoặc dừng lại sát lề đường bên phải để nhường đường cho các xe sau (theo thứ tự ưu tiên):
1. Xe chữa cháy đi làm nhiệm vụ.
2. Xe quân sự, xe công an đi làm nhiệm vụ khẩn cấp, đoàn xe có xe cảnh sát dẫn đường.
3. Xe cứu thương đang thực hiện nhiệm vụ cấp cứu.
4. Xe hộ đê, xe đi làm nhiệm vụ khắc phục sự cố thiên tai, dịch bệnh hoặc xe đi làm nhiệm vụ trong tình trạng khẩn cấp theo quy định của pháp luật.

### 4. Các lỗi phổ biến thường bị xử phạt nghiêm trọng:
- **Lỗi không nhường đường cho xe ưu tiên:** Phạt tiền từ 3.000.000 - 5.000.000 đồng và tước GPLX từ 02 - 04 tháng đối với ô tô.
- **Lỗi không tuân thủ hiệu lệnh của đèn tín hiệu (Vượt đèn vàng, đèn đỏ):** Đây là hành vi cực kỳ nguy hiểm, có thể gây tai nạn đối đầu. Mức phạt hiện nay rất cao giúp nâng cao ý thức chấp hành.

Việc nhường đường không chỉ là thực hiện đúng luật pháp mà còn thể hiện văn hóa giao thông. Một chút nhường nhịn tại ngã tư có thể giúp dòng xe lưu thông suôn sẻ và tránh được những tranh chấp không đáng có.`,

    `# BẢNG SO SÁNH MỨC PHẠT CÁC LỖI PHỔ BIẾN (2024)

Dưới đây là bảng tổng hợp so sánh mức xử phạt hành chính đối với một số lỗi vi phạm giao thông phổ biến nhất giữa Xe máy và Xe ô tô theo quy định mới nhất.

| Loại vi phạm | Mức phạt Xe máy | Mức phạt Xe ô tô | Hình phạt bổ sung |
| :--- | :--- | :--- | :--- |
| **Vượt đèn đỏ / đèn vàng** | 800.000 - 1.000.000đ | 4.000.000 - 6.000.000đ | Tước GPLX 1-3 tháng |
| **Đi ngược chiều** | 1.000.000 - 2.000.000đ | 4.000.000 - 6.000.000đ | Tước GPLX 2-4 tháng |
| **Nồng độ cồn (Mức 3)** | 6.000.000 - 8.000.000đ | 30.000.000 - 40.000.000đ | Tước GPLX 22-24 tháng |
| **Không đội mũ bảo hiểm** | 400.000 - 600.000đ | Không áp dụng | Không |
| **Chạy quá tốc độ (trên 20km/h)** | 4.000.000 - 5.000.000đ | 6.000.000 - 8.000.000đ | Tước GPLX 2-4 tháng |

### Một số lưu ý về hình phạt bổ sung:
- **Tạm giữ phương tiện:** Hầu hết các lỗi về nồng độ cồn hoặc thiếu giấy tờ xe sẽ bị tạm giữ xe đến 07 ngày.
- **Nộp phạt:** Bạn có thể nộp phạt trực tiếp tại kho bạc hoặc nộp trực tuyến qua Cổng dịch vụ công Quốc gia để tiết kiệm thời gian.
- **Tước GPLX:** Trong thời gian bị tước GPLX, người vi phạm tuyệt đối không được điều khiển phương tiện, nộp phạt xong mới được nhận lại bằng.

Hy vọng bảng so sánh này giúp bạn có cái nhìn tổng quan và chấp hành luật tốt hơn!`
];

/**
 * Giả lập phản hồi streaming qua Fetch ReadableStream
 */
function getMockChatResponse(question) {
    console.log("🤖 [MOCK API] Nhận câu hỏi:", question);
    
    // Chọn ngẫu nhiên một bài viết chuyên sâu
    const text = RESPONSES[Math.floor(Math.random() * RESPONSES.length)];
    
    // Tạo ReadableStream để mô phỏng SSE
    const stream = new ReadableStream({
        async start(controller) {
            const encoder = new TextEncoder();
            
            // Chia văn bản thành các từ để stream
            const words = text.split(' ');
            let buffer = [];
            
            for (let i = 0; i < words.length; i++) {
                buffer.push(words[i]);
                
                // Gửi cụm 3 từ hoặc từ cuối cùng
                if (buffer.length >= 3 || i === words.length - 1) {
                    const content = buffer.join(' ') + ' ';
                    const chunk = encoder.encode(`data: ${content} \n\n`);
                    controller.enqueue(chunk);
                    buffer = [];
                    
                    // Delay giữa các đợt stream
                    await new Promise(resolve => setTimeout(resolve, 80));
                }
            }
            
            controller.close();
            console.log("✅ [MOCK API] Đã hoàn thành gửi stream.");
        }
    });

    return new Response(stream, {
        headers: { 'Content-Type': 'text/event-stream' }
    });
}

// Xuất ra global
window.getMockChatResponse = getMockChatResponse;
window.USE_MOCK = false;
