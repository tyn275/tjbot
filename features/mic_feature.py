# features/mic_feature.py
import os
import time
import wave
import threading
import numpy as np         # 💡 Thêm mới để xử lý ma trận toán học
import noisereduce as nr   # 💡 Thêm mới để lọc nhiễu phổ (Spectral Gating)
from scipy import signal   # Hạ tầng số lấy mẫu

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
    recorded_file = os.path.join(CACHE_DIR, "playback.wav")
    
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    
    # 💡 THAY ĐỔI 1: Ép thu âm ở 44100Hz để vừa vặn với phần cứng của Mic 50k (Tránh lỗi -9997)
    HARDWARE_RATE = 44100 
    TARGET_AI_RATE = 16000 # Tần số đích mà ta muốn chuyển đổi về sau khi lọc
    
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=HARDWARE_RATE, # Chạy đúng tần số gốc của mic
                        input=True,
                        frames_per_buffer=CHUNK)
        
        print(f"-> [MIC] Phần cứng mở thành công ở {HARDWARE_RATE}Hz. Đang thu âm...")
        frames = []
        
        # Tính toán số vòng lặp dựa trên HARDWARE_RATE mới
        for _ in range(0, int(HARDWARE_RATE / CHUNK * timeout_sec)):
            if not is_recording:
                break
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            
        print("-> [MIC] Thu âm hoàn tất. Đang chuyển đổi dữ liệu phù hợp với AI...")
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        if len(frames) > 0:
            # Chuyển đổi dữ liệu nhị phân sang mảng số Numpy
            audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
            
            # 💡 THAY ĐỔI 2: DÙNG SCIPY HẠ TẦN SỐ TỪ 44.1kHz XUỐNG 16kHz TRONG BỘ NHỚ
            # Tính toán số lượng mẫu mới sau khi hạ tần số
            num_samples = int(len(audio_data) * TARGET_AI_RATE / HARDWARE_RATE)
            # Thực hiện thuật toán Resample chất lượng cao của Scipy
            audio_data_16k = signal.resample(audio_data, num_samples).astype(np.int16)
            
            # 🌟 KHUẾCH ĐẠI KỸ THUẬT SỐ (DIGITAL GAIN)
            max_val = np.max(np.abs(audio_data_16k))
            if max_val > 0:
                target_peak = 25000
                gain_factor = min(target_peak / max_val, 8.0)
                print(f"   [GAIN]: Đã tự động nhân biên độ lên x{gain_factor:.2f} lần.")
                audio_data_16k = (audio_data_16k * gain_factor).astype(np.int16)
            
            # 🌟 LỌC NHIỄU PHỔ TRÊN TẦN SỐ 16KHZ MỚI
            print("   [LỌC NHIỄU]: Tiến hành bóc tách dải nhiễu xì nền...")
            cleaned_audio = nr.reduce_noise(y=audio_data_16k, sr=TARGET_AI_RATE, prop_decrease=0.80)
            final_bytes = cleaned_audio.tobytes()
        else:
            final_bytes = b''

        # GHI LẠI FILE WAVE CHUẨN 16KHZ ĐỂ PHÁT HOẶC NHẬN DẠNG
        wf = wave.open(recorded_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pyaudio.PyAudio().get_sample_size(FORMAT))
        wf.setframerate(TARGET_AI_RATE) # Lưu ở 16000Hz cực nhẹ và chuẩn AI
        wf.writeframes(final_bytes)
        wf.close()
        
        print(f"-> [MIC] Xuất file wave thành công: {recorded_file}")
        
        if is_recording:
            print("-> [SPEAKER] Robot đang nói nhại lại...")
            os.system(f"aplay {recorded_file}")
            
    except Exception as e:
        print(f"-> [LỖI TIỀN XỬ LÝ MIC]: {e}")
    finally:
        is_recording = False

def mic_record_control(state, timeout="5"):
    global is_recording
    state = state.strip().lower()
    timeout_sec = int(str(timeout).strip())

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
    
    # Định nghĩa file âm thanh tạm thời sau khi đã được lọc sạch nhiễu
    listen_file = os.path.join(CACHE_DIR, "listen_clean.wav")
    
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    HARDWARE_RATE = 44100   # Tần số gốc ép mic 50k chạy ổn định
    TARGET_AI_RATE = 16000  # Tần số đích tối ưu nhất cho Google Speech AI
    
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=HARDWARE_RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        
        print(f"-> [AI MIC] Phần cứng AI mở thành công ở {HARDWARE_RATE}Hz. Hãy nói... (Giữ im lặng 0.5s đầu)")
        frames = []
        
        # Vòng lặp thu âm dựa theo thời gian lắng nghe cấu hình
        for _ in range(0, int(HARDWARE_RATE / CHUNK * timeout_sec)):
            if not is_listening:
                break
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            
        print("-> [AI MIC] Đang xử lý làm sạch âm thanh thô trước khi chuyển cho AI...")
        
        # Đóng stream phần cứng nhanh để giải phóng tài nguyên
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        if len(frames) > 0:
            # 1. Chuyển mảng bytes sang số để xử lý toán học
            audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
            
            # 2. DÙNG SCIPY HẠ TẦN SỐ TỪ 44.1kHz XUỐNG 16kHz TRONG RAM
            num_samples = int(len(audio_data) * TARGET_AI_RATE / HARDWARE_RATE)
            audio_data_16k = signal.resample(audio_data, num_samples).astype(np.int16)
            
            # 3. KHUẾCH ĐẠI KỸ THUẬT SỐ (DIGITAL GAIN)
            max_val = np.max(np.abs(audio_data_16k))
            if max_val > 0:
                target_peak = 25000
                gain_factor = min(target_peak / max_val, 8.0) # Nhân max 8 lần
                print(f"   [AI GAIN]: Tự động nhân biên độ âm lượng giọng nói lên x{gain_factor:.2f} lần.")
                audio_data_16k = (audio_data_16k * gain_factor).astype(np.int16)
            
            # 4. LỌC SẠCH XÌ NỀN BẰNG NOISEREDUCE TRÊN TẦN SỐ 16KHZ
            print("   [AI LỌC NHIỄU]: Thuật toán phân tích phổ đang quét sạch tiếng rít của mic...")
            cleaned_audio = nr.reduce_noise(y=audio_data_16k, sr=TARGET_AI_RATE, prop_decrease=0.85)
            final_bytes = cleaned_audio.tobytes()
        else:
            final_bytes = b''

        # 5. GHI DỮ LIỆU SẠCH TINH KHIẾT RA FILE WAV TẠM THỜI
        wf = wave.open(listen_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pyaudio.PyAudio().get_sample_size(FORMAT))
        wf.setframerate(TARGET_AI_RATE)
        wf.writeframes(final_bytes)
        wf.close()
        
        # -----------------------------------------------------------------
        # 🚀 CHUYỂN FILE ÂM THANH SẠCH CHO ENGINE NHẬN DẠNG AI
        # -----------------------------------------------------------------
        if is_listening and len(final_bytes) > 0:
            recognizer = sr.Recognizer()
            
            with sr.AudioFile(listen_file) as source:
                print("-> [AI ENGINE] Thư viện nhận dạng đang đọc file âm thanh đã được xử lý...")
                audio_content = recognizer.record(source)
                
            print(f"-> [AI GOOGLE] Đang gửi dữ liệu sạch lên Cloud để nhận dạng [Ngôn ngữ: {lang_code}]...")
            
            text_result = recognizer.recognize_google(audio_content, language=lang_code)
            print(f"-> [AI KẾT QUẢ]: \"{text_result}\"")
            
            # Gọi thẳng hàm bắn chuỗi text thô lên là xong, 1 tham số duy nhất!
            mqtt_response("s2t="+text_result)
            
    except sr.UnknownValueError:
        print("-> [AI CẢNH BÁO]: AI không thể nghe rõ bạn nói gì.")
        mqtt_response("[Không nghe rõ]") # Gửi thông báo chuỗi thô khi lỗi
    except sr.RequestError as e:
        print(f"-> [AI LỖI KẾT NỐI]: Không thể kết nối tới máy chủ Google Speech AI: {e}")
        mqtt_response("[Lỗi kết nối AI]")
    except Exception as e:
        print(f"-> [LỖI HỆ THỐNG TRONG LUỒNG AI NGẦM]: {e}")
        mqtt_response(f"[Lỗi hệ thống: {str(e)}]")
    finally:
        is_listening = False
        print("-> [AI MIC] Trạng thái AI Listen đã được giải phóng.")

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
            "params": "state, timeout='5', lang='vi-VN'",
            "example": "Listen(on, 5, 'vi-VN')"
        }
    
    print("=> Mô-đun MIC_FEATURE đã đăng ký đồng bộ tham số thành công! 🎙️")