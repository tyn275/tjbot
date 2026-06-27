# features/mic_feature.py
import os
import time
import wave
import threading

# 🔥 ĐÃ ĐỔI: Import hàm gửi tin nhắn tập trung từ module mqtt dùng chung
from features.mqtt import mqtt_response

# Thử import các thư viện xử lý Microphone, báo lỗi nếu thiếu
try:
    import pyaudio
    import speech_recognition as sr
except ImportError:
    print("-> [CẢNH BÁO]: Thiếu thư viện âm thanh. Vui lòng chạy: pip install pyaudio speechrecognition")

# -----------------------------------------------------------------
# CẤU HÌNH ĐƯỜNG DẪN THƯ MỤC LƯU FILE THU ÂM (Giữ nguyên)
# -----------------------------------------------------------------
CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache"))
os.makedirs(CACHE_DIR, exist_ok=True)

is_recording = False
is_listening = False

# ❌ ĐÃ XÓA: Toàn bộ cấu hình MQTT phụ và hàm publish_s2t_result cũ tại đây!

# -----------------------------------------------------------------
# PHẦN 1: HÀM XỬ LÝ "NGHE VÀ NÓI NHẠI" (RECORD) - Giữ nguyên
# -----------------------------------------------------------------
def _record_and_playback_worker(timeout_sec):
    global is_recording
    recorded_file = os.path.join(CACHE_DIR, "playback_copy.wav")
    
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    # 🔥 ĐÃ SỬA: Ép đúng tần số 44100Hz tương thích hoàn toàn với phần cứng Microphone USB của bạn
    RATE = 44100 

    p = None
    stream = None

    try:
        p = pyaudio.PyAudio()
        
        # 🔥 ĐÃ SỬA: Thêm device_index=1 giống như bên hàm Listen để bốc trúng cổng USB
        stream = p.open(
            format=FORMAT, 
            channels=CHANNELS, 
            rate=RATE, 
            input=True, 
            input_device_index=1, 
            frames_per_buffer=CHUNK
        )
        print(f"🎙️ [RECORD USB]: Khởi tạo phần cứng thành công. Đang thu âm trong {timeout_sec}s...")
        
        frames = []
        start_time = time.time()
        
        # Vòng lặp thu âm thông minh có bảo vệ chống tràn bộ đệm và chống kẹt luồng
        while is_recording and (time.time() - start_time < timeout_sec):
            try:
                # Thêm exception_on_overflow=False để tránh treo luồng khi Mic USB bị trễ dữ liệu
                data = stream.read(CHUNK, exception_on_overflow=False)
                if data:
                    frames.append(data)
            except Exception as read_err:
                print(f"⚠️ Cảnh báo đọc dữ liệu Mic: {read_err}")
                break
            
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()
        print("🔒 [RECORD]: Đã giải phóng hoàn toàn thiết bị Microphone USB.")

        if not is_recording or len(frames) == 0:
            print("🛑 [RECORD]: Tiến trình bị hủy bỏ hoặc không có dữ liệu âm thanh.")
            return

        # Ghi file kết quả âm thanh
        wf = wave.open(recorded_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        print("💾 [RECORD]: Đã lưu file âm thanh thu từ USB thành công.")

        # --- PHÁT LẠI GIỌNG NÓI ---
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
        # Bắn thông tin lỗi về hệ thống MQTT dùng chung
        mqtt_response(f"s2t=(Lỗi phần cứng Mic: {str(e)})")
        try:
            if stream: stream.close()
            if p: p.terminate()
        except: pass
    finally:
        is_recording = False

def mic_record_control(state, timeout="5"):
    global is_recording
    state = state.strip().lower()
    timeout_sec = int(timeout.strip())

    if state == "on":
        if is_recording:
            return "Robot đang trong tiến trình thu âm nhại giọng rồi."
        is_recording = True
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
def _listen_and_recognize_worker(timeout_sec, lang_code):
    global is_listening
    r = sr.Recognizer()
    
    r.energy_threshold = 300  
    r.dynamic_energy_threshold = True

    print(f"🧠 [LISTEN AI]: Hệ thống AI đang tập trung lắng nghe để dịch giọng nói ({timeout_sec}s)...")
    
    try:
        # Sử dụng Card mic USB định danh phần cứng index 1 và tần số 44100Hz ổn định
        with sr.Microphone(device_index=1, sample_rate=44100) as source:
            r.adjust_for_ambient_noise(source, duration=0.8)
            if not is_listening: return
            audio_data = r.listen(source, timeout=timeout_sec, phrase_time_limit=timeout_sec)
            
        if not is_listening:
            print("🛑 [LISTEN AI]: Tiến trình nhận diện bị ngắt bởi người dùng.")
            return

        print("🤖 [LISTEN AI]: Đang gửi dữ liệu âm thanh lên Cloud AI để xử lý dịch văn bản...")
        recognized_text = r.recognize_google(audio_data, language=lang_code)
        print(f"🎯 [LISTEN AI] Kết quả dịch thành công: \"{recognized_text}\"")
        
        # 🔥 ĐÃ ĐỔI: Sử dụng hàm dùng chung để bắn thẳng kết quả dạng s2=... lên TOPIC_PUB
        mqtt_response(f"s2t={recognized_text}")

    except sr.WaitTimeoutError:
        print("⏳ [LISTEN AI]: Hết thời gian chờ mà không thấy ai nói gì.")
        mqtt_response("s2t=(Không nghe thấy âm thanh nào từ bạn!)")
    except sr.UnknownValueError:
        print("❓ [LISTEN AI]: Google AI không thể hiểu được từ ngữ bạn vừa nói.")
        mqtt_response("s2t=(Lỗi: Không nhận diện rõ từ ngữ bạn nói!)")
    except Exception as e:
        print(f"❌ Lỗi kết nối dịch vụ Google Speech hoặc lỗi phần cứng: {e}")
        mqtt_response(f"s2t=(Lỗi kết nối AI: {str(e)})")
    finally:
        is_listening = False

def mic_listen_control(state, timeout="5", lang="vi-VN"):
    global is_listening
    
    # Chuẩn hóa dữ liệu đầu vào
    state = str(state).strip().lower()
    timeout_sec = int(str(timeout).strip())
    lang_code = str(lang).strip() # Giữ nguyên hoa thường (ví dụ: vi-VN, en-US)

    if state == "on":
        if is_listening:
            return "Robot đang bận lắng nghe dịch ngôn ngữ rồi."
        
        is_listening = True
        
        # 🔥 ĐÃ NÂNG CẤP: Truyền thêm mã ngôn ngữ (lang_code) vào hàm worker xử lý mic
        t = threading.Thread(
            target=_listen_and_recognize_worker, 
            args=(timeout_sec, lang_code)
        )
        t.daemon = True
        t.start()
        
        return f"Khởi động AI Nghe hiểu [Ngôn ngữ: {lang_code}] ({timeout_sec}s)"
    
    else:
        is_listening = False
        return "Đã dừng tiến trình AI lắng nghe"

# -----------------------------------------------------------------
# ĐĂNG KÝ HÀM VÀO HỆ THỐNG MẸ
# -----------------------------------------------------------------
def register(actions_map):
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