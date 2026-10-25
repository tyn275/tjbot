# Changelog

Mọi thay đổi đáng chú ý của dự án TJBot sẽ được ghi chép chi tiết trong tài liệu này.

Định dạng tài liệu tuân theo tiêu chuẩn [Keep a Changelog](https://keepachangelog.com/vi/1.0.0/) và tuân thủ [Semantic Versioning](https://semver.org/).

---

## [1.1.0] - 2026-10-25

### 🐛 Fixed (Sửa lỗi)
- **Sửa lỗi Text-to-Speech (TTS) im lặng khi văn bản chứa dấu phẩy từ Web UI:**
  - **Hiện tượng:** Khi người dùng nhập văn bản có chứa dấu phẩy trên giao diện Web (ví dụ: `"Xin chào mọi người, mình là TJBot"`), lệnh gửi xuống MQTT bị bọc lồng ngoặc kép dạng `TextToSpeak(""Xin chào mọi người", "mình là TJBot"", "vi", "vi-VN-Standard-B", "Google")`.
  - **Nguyên nhân:** Cú pháp trên khiến bộ parse `ast.literal_eval` bị lỗi `SyntaxError` và nhảy vào nhánh fallback `split(",")` thô:
    - Text bị cắt đôi tại dấu phẩy, làm lệch toàn bộ thứ tự tham số truyền vào hàm `text_to_speak()`.
    - Tham số `lang` bị gán nhầm thành vế sau của câu (`"mình là TJBot"`), khiến `gTTS` báo lỗi không hỗ trợ ngôn ngữ.
    - Tham số `blocking` bị gán nhầm thành `"Google"` (chuỗi không rỗng mang giá trị `True` trong Python), khiến hàm phản hồi ngay `Đã đọc xong văn bản qua vi-VN-Standard-B` lên kênh MQTT status dù âm thanh chưa từng phát được.
  - **Giải pháp:** Cải tiến bộ bóc tách tham số trong file `tjbot_client.py` để xử lý thông minh chuỗi đầu vào trước khi truyền vào hàm chức năng.

---

### ✨ Added (Thêm mới)
- **Hàm `_parse_params(raw_params: str) -> list` trong [`tjbot_client.py`](./tjbot_client.py):**
  - Cơ chế bóc tách tham số robust với 3 cấp độ phòng vệ:
    1. **Cấp độ 1 (Chuẩn Python):** Sử dụng `ast.literal_eval` để parse chuẩn xác các lệnh hợp lệ từ MQTTX hoặc REST API, giữ nguyên chuỗi và dấu phẩy bên trong nháy kép.
    2. **Cấp độ 2 (Xử lý chuỗi Web lồng ngoặc kép - Double-wrap):** Dùng biểu thức chính quy (`Regex`) bắt cặp `""...""` sinh ra từ Web UI khi có dấu phẩy, tự động gộp lại thành văn bản hoàn chỉnh và parse các tham số còn lại (`lang`, `voice`, `service`).
    3. **Cấp độ 3 (Fallback dự phòng):** Tách thô bằng `split(",")` và loại bỏ khoảng trắng, dấu nháy thừa đối với các cú pháp không chuẩn khác.

---

### 📝 Documentation (Tài liệu)
- Cập nhật hướng dẫn cấu hình kết nối UART khi flash image.
- Bổ sung tài liệu khắc phục sự cố dịch vụ `pigpiod`, khởi động dịch vụ `tjbot.service` và các lệnh theo dõi log qua `journalctl`.
