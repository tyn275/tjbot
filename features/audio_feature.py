# features/audio_feature.py
import os
import time
from gtts import gTTS
import subprocess

# Khởi tạo thư viện pygame mixer để quản lý phát âm thanh nền, cho phép ngắt âm lập tức
try:
    import pygame
    pygame.mixer.init()
except ImportError:
    print("-> [CẢNH BÁO]: Chưa cài đặt thư viện 'pygame'. Vui lòng chạy: pip install pygame")

# -----------------------------------------------------------------
# CẤU HÌNH ĐƯỜNG DẪN THƯ MỤC ÂM THANH
# -----------------------------------------------------------------
# Thư mục chứa các file mp3 có sẵn (hello.mp3, bye.mp3,...) theo yêu cầu là ../audio/
AUDIO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "audio"))
# Thư mục tạm thời lưu file sinh ra từ Text-To-Speech
CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache"))

# Tự động tạo các thư mục nếu chưa tồn tại để tránh lỗi hệ thống
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# -----------------------------------------------------------------
# CÁC HÀM XỬ LÝ CHỨC NĂNG CHÍNH (AUDIO ACTIONS)
# -----------------------------------------------------------------

def play_audio_file(filename):
    """
    Xử lý lệnh: Play("filename.mp3") từ phần Bi bô trên Web.
    Phát file âm thanh có sẵn từ thư mục ../audio/
    """
    # Làm sạch tên file đầu vào đề phòng web truyền thừa dấu nháy kép
    filename = filename.strip('"\'')
    file_path = os.path.join(AUDIO_DIR, filename)

    print(f"-> [AUDIO]: Đang xử lý lệnh phát file: {filename}")
    
    if not os.path.exists(file_path):
        err_msg = f"❌ Không tìm thấy file âm thanh tại: {file_path}"
        print(err_msg)
        return err_msg

    try:
        # Nếu đang phát âm thanh khác thì dừng lại trước khi phát file mới
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        return f"Đang phát file: {filename}"
    except Exception as e:
        print(f"❌ Lỗi phát file âm thanh: {e}")
        return f"Lỗi phát file: {str(e)}"


def text_to_speak(text, lang="vi", voice="", service="Google"):
    """
    Xử lý lệnh: TextToSpeak("văn bản", "mã_ngôn_ngữ", "giọng_đọc", "dịch_vụ") từ phần Tập đọc trên Web.
    Chuyển đổi chuỗi văn bản thành âm thanh qua thư viện gTTS và phát ra loa.
    """
    text = text.strip('"\'')
    lang = lang.strip('"\'')
    service = service.strip('"\'')
    
    print(f"-> [TTS]: Nhận lệnh đọc chữ: '{text}' [Ngôn ngữ: {lang}, Dịch vụ: {service}]")
    
    if not text:
        return "Văn bản trống, bỏ qua."

    temp_filename = f"tts_{int(time.time())}.mp3"
    temp_filepath = os.path.join(CACHE_DIR, temp_filename)

    try:
        # Nếu đang bận phát âm thanh khác thì ra lệnh tắt ngay
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

        # Hiện tại gTTS hỗ trợ chuyển đổi Google TTS miễn phí cực kỳ ổn định
        # (Nếu sau này bạn mở rộng kết nối FPT AI hoặc Viettel AI chỉ cần thêm cấu hình API tại đây)
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(temp_filepath)
        
        # Nạp và phát file tạm vừa tạo ra loa
        pygame.mixer.music.load(temp_filepath)
        pygame.mixer.music.play()
        
        # Trả về chuỗi thông báo kết quả ra kênh status MQTT
        return f"Đã đọc xong văn bản qua {service}"
    except Exception as e:
        print(f"❌ Lỗi xử lý Text-To-Speech: {e}")
        return f"Lỗi TTS: {str(e)}"


def silent_audio():
    """
    Xử lý lệnh: Silent() từ nút "Suỵt" trên Web.
    Dừng ngay lập tức toàn bộ âm thanh đang phát ra loa.
    """
    print("-> [AUDIO]: Nhận lệnh dừng âm thanh khẩn cấp (Silent).")
    try:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        return "Đã tắt âm thanh"
    except Exception as e:
        return f"Lỗi khi dừng âm thanh: {str(e)}"

# -----------------------------------------------------------------
# HÀM SELFTEST TỰ ĐỘNG (GỌI TỪ FILE SELFTEST VẬN HÀNH CHUNG)
# -----------------------------------------------------------------
def selftest():
    """
    Hàm tự kiểm tra hệ thống âm thanh:
    - Mặc định: Gọi lệnh Shell phát file âm thanh mẫu tiêu chuẩn của Linux.
    - Dự phòng: Tự động sinh tiếng Beep tần số nếu hệ thống thiếu file wav.
    """
    print("\n--- [SELFTEST] BẮT ĐẦU KIỂM TRA MÔ-ĐUN ÂM THANH (COMBINED) ---")
    
    # Đường dẫn file âm thanh mặc định của hệ thống ALSA Linux (Giọng nói "Front Center")
    system_wav = "/usr/share/sounds/alsa/Front_Center.wav"
    
    try:
        # TRƯỜNG HỢP 1: Hệ thống có sẵn file âm thanh mẫu -> Dùng aplay mặc định
        if os.path.exists(system_wav):
            print(f"🤖 Step 1: Phát hiện file mẫu hệ thống tại '{system_wav}'")
            print("🤖 Step 2: ĐANG PHÁT GIỌNG NÓI MẪU QUA LỆNH APLAY... 🔊")
            run_cmd = f"aplay -q {system_wav}"
            
        # TRƯỜNG HỢP 2: File mẫu bị thiếu -> Gọi lệnh Shell sinh tiếng Beep tần số 440Hz trong 1.5 giây
        else:
            print("⚠️ Cảnh báo: Không tìm thấy file Front_Center.wav của Linux.")
            print("🤖 Step 1: Kích hoạt phương án dự phòng: Tự sinh tần số âm thanh (Tone Generator)...")
            print("🤖 Step 2: ĐANG PHÁT TIẾNG BEEP DỰ PHÒNG (440Hz - 1.5 giây)... 🔊")
            # Lệnh speaker-test dùng sine wave (-t sine), tần số 440Hz (-f 440), lặp 1 lần và tự ngắt bằng timeout
            run_cmd = "speaker-test -t sine -f 440 -l 1 > /dev/null 2>&1"

        # 3. Thực thi lệnh Shell với cơ chế kiểm soát thời gian (Timeout)
        # Thiết lập timeout 5 giây đề phòng trường hợp card âm thanh bị kẹt phần cứng gây treo tiến trình
        result = subprocess.run(
            run_cmd, 
            shell=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.PIPE, 
            timeout=5
        )
        
        # 4. Đánh giá kết quả dựa trên mã phản hồi (Exit Code) của hệ thống
        if result.returncode == 0:
            time.sleep(0.5) # Nghỉ ngắn dọn dẹp luồng
            print("✅ THÀNH CÔNG: Mạch âm thanh phản hồi tốt, loa đã phát tín hiệu thành công.")
            return True
        else:
            # Lấy thông tin lỗi chi tiết từ tầng driver Linux trả về nếu có
            error_msg = result.stderr.decode().strip()
            print(f"❌ THẤT BẠI: Lệnh Shell trả về lỗi phần cứng/driver: {error_msg}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ THẤT BẠI: Quá thời gian phản hồi (Timeout)! Tiến trình âm thanh hệ thống bị treo.")
        return False
    except Exception as e:
        print(f"❌ THẤT BẠI: Lỗi phát sinh ngoài dự kiến trong kịch bản: {e}")
        return False

# -----------------------------------------------------------------
# ĐĂNG KÝ VÀ CUNG CẤP TÀI LIỆU HƯỚNG DẪN ĐỘNG (API DOCS)
# -----------------------------------------------------------------
def register(actions_map):
    """
    Đăng ký tự động các hàm xử lý âm thanh vào bảng điều phối ACTIONS_MAP của tjbot_client.py
    """
    actions_map["Play"] = {
        "func": play_audio_file,
        "params": "filename",
        "example": 'Play("hello.mp3")'
    }
       
    actions_map["TextToSpeak"] = {
        "func": text_to_speak,
        "params": "text, lang='vi', voice='', service='Google'",
        "example": 'TextToSpeak("Xin chào chủ nhân", "vi", "vi-VN-Standard-A", "Google")'
    }
    
    actions_map["Silent"] = {
        "func": silent_audio,
        "params": "",
        "example": "Silent()"
    }
    print("=> Mô-đun AUDIO_FEATURE đã đăng ký thành công danh sách lệnh! 🔊")