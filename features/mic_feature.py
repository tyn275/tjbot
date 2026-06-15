# features/mic_feature.py
import os
import time
import wave
import threading
from paho.mqtt import client as mqtt_client

# Thử import các thư viện xử lý Microphone, báo lỗi nếu thiếu
try:
    import pyaudio
    import speech_recognition as sr
except ImportError:
    print("-> [CẢNH BÁO]: Thiếu thư viện âm thanh. Vui lòng chạy: pip install pyaudio speechrecognition")

# -----------------------------------------------------------------
# CẤU HÌNH ĐƯỜNG DẪN THƯ MỤC LƯU FILE THU ÂM
# -----------------------------------------------------------------
# Lưu file ghi âm vào thư mục tạm ../cache/ để phát lại nhại giọng
CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache"))
os.makedirs(CACHE_DIR, exist_ok=True)

# Biến cờ toàn cục dùng để ngắt trạng thái nghe/ghi âm khẩn cấp khi nhận lệnh "off"
is_recording = False
is_listening = False

# -----------------------------------------------------------------
# CẤU HÌNH MQTT PHỤ ĐỂ BẮN KẾT QUẢ S2T VỀ WEB
# -----------------------------------------------------------------
DEVICEID="tjbot1"
# Lấy các thông số môi trường giống như file mẹ để đồng bộ kết nối
BROKER = os.getenv('MQTT_BROKER', 'mqtt.toolhub.app').strip()
PORT = int(os.getenv('MQTT_PORT', 1883))
USER = os.getenv('MQTT_USER').strip() if os.getenv('MQTT_USER') else None
PASSWORD = os.getenv('MQTT_PASSWORD').strip() if os.getenv('MQTT_PASSWORD') else None
TOPIC_RES = DEVICEID+"/res"  # Kênh phản hồi kết quả s2t lên giao diện Web

def publish_s2t_result(text_content):
    """ Hàm kết nối nhanh tới broker để đẩy chuỗi s2t=... lên kênh phản hồi """
    try:
        client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, "tjbot-mic-reporter")
        if USER and PASSWORD:
            client.username_pw_set(USER, PASSWORD)
        client.connect(BROKER, PORT, 60)
        payload = f"s2t={text_content}"
        client.publish(TOPIC_RES, payload)
        print(f"-> [MIC_MQTT]: Đã gửi kết quả nhận diện lên [{TOPIC_RES}]: {payload}")
        client.disconnect()
    except Exception as e:
        print(f"❌ Không thể gửi kết quả MQTT phản hồi: {e}")

# -----------------------------------------------------------------
# PHẦN 1: HÀM XỬ LÝ "NGHE VÀ NÓI NHẠI" (RECORD)
# -----------------------------------------------------------------
def _record_and_playback_worker(timeout_sec):
    global is_recording
    recorded_file = os.path.join(CACHE_DIR, "playback_copy.wav")
    
    # Cấu hình phần cứng Audio Stream
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000 # 16kHz chuẩn giọng nói nhỏ gọn

    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        print(f"🎙️ [RECORD]: Robot đang thu âm giọng nói của bạn trong {timeout_sec} giây...")
        
        frames = []
        start_time = time.time()
        
        # Vòng lặp đọc dữ liệu từ phần cứng Micro
        while is_recording and (time.time() - start_time < timeout_sec):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            
        # Đóng stream thu âm
        stream.stop_stream()
        stream.close()
        p.terminate()

        if not is_recording:
            print("🛑 [RECORD]: Tiến trình bị hủy bỏ bởi người dùng.")
            return

        # Tiến hành ghi mảng dữ liệu âm thanh vừa thu vào file .wav
        wf = wave.open(recorded_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        print("💾 [RECORD]: Đã lưu file âm thanh thu được thành công.")

        # --- PHÁT LẠI Y HỆT GIỌNG VỪA THU (NÓI NHẠI) ---
        # Sử dụng pygame.mixer có sẵn trong mô-đun audio để phát lại ngay lập tức
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            
            print("🔊 [PLAYBACK]: Robot đang phát lại nhại giọng...")
            pygame.mixer.music.load(recorded_file)
            pygame.mixer.music.play()
        except Exception as ex:
            print(f"❌ Lỗi khi gọi module phát lại âm thanh nhại: {ex}")

    except Exception as e:
        print(f"❌ Lỗi phần cứng Micro trong quá trình Record: {e}")
    finally:
        is_recording = False

def mic_record_control(state, timeout="5"):
    """
    Xử lý lệnh: Record(on, 5) hoặc Record(off) từ Web gửi xuống.
    """
    global is_recording
    state = state.strip().lower()
    timeout_sec = int(timeout.strip())

    if state == "on":
        if is_recording:
            return "Robot đang trong tiến trình thu âm nhại giọng rồi."
        is_recording = True
        # Chạy ngầm tiến trình thu âm bằng Thread để không làm treo hệ thống client mẹ
        t = threading.Thread(target=_record_and_playback_worker, args=(timeout_sec,))
        t.daemon = True
        t.start()
        return f"Khởi động thu âm nói nhại ({timeout_sec}s)"
    else:
        is_recording = False
        return "Đã ra lệnh ngắt tiến trình thu âm nhại giọng"


# -----------------------------------------------------------------
# PHẦN 2: HÀM XỬ LÝ "NGHE HIỂU - AI RECOGNITION" (LISTEN)
# -----------------------------------------------------------------
def _listen_and_recognize_worker(timeout_sec):
    global is_listening
    r = sr.Recognizer()
    
    # Điều chỉnh bộ lọc nhiễu môi trường xung quanh cho microphone phòng thí nghiệm
    r.energy_threshold = 3000  
    r.dynamic_energy_threshold = True

    print(f"🧠 [LISTEN AI]: Hệ thống AI đang tập trung lắng nghe để dịch giọng nói ({timeout_sec}s)...")
    
    try:
        with sr.Microphone() as source:
            # Cho phép robot tự điều chỉnh theo tạp âm môi trường trong 0.8 giây đầu
            r.adjust_for_ambient_noise(source, duration=0.8)
            
            if not is_listening: return
            
            # Thực hiện nghe với thời gian giới hạn timeout
            audio_data = r.listen(source, timeout=timeout_sec, phrase_time_limit=timeout_sec)
            
        if not is_listening:
            print("🛑 [LISTEN AI]: Tiến trình nhận diện bị ngắt bởi người dùng.")
            return

        print("🤖 [LISTEN AI]: Đang gửi dữ liệu âm thanh lên Cloud AI để xử lý dịch văn bản...")
        # Sử dụng Google Speech Recognition nhận diện ngôn ngữ Tiếng Việt (vi-VN)
        recognized_text = r.recognize_google(audio_data, language="vi-VN")
        print(f"🎯 [LISTEN AI] Kết quả dịch thành công: \"{recognized_text}\"")
        
        # 🚀 BẮN PHẢN HỒI KẾT QUẢ VỀ CHO TEXTAREA TRÊN TRANG WEB NHẬN ĐƯỢC
        publish_s2t_result(recognized_text)

    except sr.WaitTimeoutError:
        print("⏳ [LISTEN AI]: Hết thời gian chờ mà không thấy ai nói gì.")
        publish_s2t_result("(Không nghe thấy âm thanh nào từ bạn!)")
    except sr.UnknownValueError:
        print("❓ [LISTEN AI]: Google AI không thể hiểu được từ ngữ bạn vừa nói.")
        publish_s2t_result("(Lỗi: Không nhận diện rõ từ ngữ bạn nói!)")
    except Exception as e:
        print(f"❌ Lỗi kết nối dịch vụ Google Speech: {e}")
        publish_s2t_result(f"(Lỗi kết nối AI: {str(e)})")
    finally:
        is_listening = False

def mic_listen_control(state, timeout="5"):
    """
    Xử lý lệnh: Listen(on, 5) hoặc Listen(off) từ Web gửi xuống.
    """
    global is_listening
    state = state.strip().lower()
    timeout_sec = int(timeout.strip())

    if state == "on":
        if is_listening:
            return "Robot đang bận lắng nghe dịch ngôn ngữ rồi."
        is_listening = True
        # Chạy ngầm tiến trình nhận diện AI bằng Thread riêng biệt
        t = threading.Thread(target=_listen_and_recognize_worker, args=(timeout_sec,))
        t.daemon = True
        t.start()
        return f"Khởi động AI Nghe hiểu ({timeout_sec}s)"
    else:
        is_listening = False
        return "Đã dừng tiến trình AI lắng nghe"

# -----------------------------------------------------------------
# ĐĂNG KÝ HÀM VÀO HỆ THỐNG MẸ
# -----------------------------------------------------------------
def register(actions_map):
    """ Đăng ký tự động các lệnh vào bảng điều phối ACTIONS_MAP của tjbot_client.py """
    actions_map["Record"] = {
        "func": mic_record_control,
        "params": "state, timeout='5'",
        "example": 'Record(on, 7)'
    }
       
    actions_map["Listen"] = {
        "func": mic_listen_control,
        "params": "state, timeout='5'",
        "example": 'Listen(on, 10)'
    }
    print("=> Mô-đun MIC_FEATURE đã đăng ký thành công danh sách lệnh! 🎙️")