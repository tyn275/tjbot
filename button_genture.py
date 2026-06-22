# button_genture.py
import enum
import time
import threading
import subprocess
import socket
import psutil
import RPi.GPIO as GPIO

from features import audio_feature
from features.mqtt import mqtt_response

# 1. ĐỊNH NGHĨA BIẾN ACTIVITY_MODE DẠNG ENUM
class ActivityMode(enum.Enum):
    MODE_GYM = 1
    MODE_ASKANS = 2

# Chuyển đổi Enum thành một danh sách (List) cố định để áp dụng thuật toán chia lấy dư
MODES_LIST = list(ActivityMode)

# Khởi tạo giá trị ban đầu cho Mode hoạt động
CURRENT_ACTIVITY_MODE = ActivityMode.MODE_GYM
BUTTON_PIN = 26  

# --- HÀM TRỢ GIÚP LẤY THÔNG TIN MẠNG (ĐỌC CẢ IP VÀ SSID TÊN WIFI) ---
def get_network_speech_text():
    interfaces = psutil.net_if_addrs()
    AF_INET = socket.AF_INET
    
    # Lấy IP Mạng dây (eth0)
    eth0_ip = "Không có kết nối dây"
    if 'eth0' in interfaces:
        for addr in interfaces['eth0']:
            if addr.family == AF_INET:
                eth0_ip = addr.address
                break
                
    # Lấy IP WiFi (wlan0) và Tên mạng WiFi (SSID)
    wlan0_ip = "Không có kết nối không dây"
    wifi_ssid = "Chưa kết nối mạng"
    
    if 'wlan0' in interfaces:
        for addr in interfaces['wlan0']:
            if addr.family == AF_INET:
                wlan0_ip = addr.address
                
                # Tiến hành gọi lệnh Linux bóc tách lấy chuẩn xác tên SSID mạng WiFi hiện tại
                try:
                    # Lệnh 'iwgetid -r' trả về chính xác chuỗi tên SSID của mạng đang kết nối
                    wifi_ssid = subprocess.check_output(["iwgetid", "-r"]).decode("utf-8").strip()
                    if not wifi_ssid:
                        wifi_ssid = "Ẩn hoặc không rõ tên"
                except:
                    wifi_ssid = "Ngoại tuyến"
                break
                
    # Tạo chuỗi văn bản tiếng Việt tự nhiên để Robot phát âm chuẩn, dễ nghe
    speech_text = (
        f"Thông tin kết nối mạng "
        f"Địa chỉ ai pi mạng dây là: {eth0_ip.replace('.', ' chấm ')}. "
        f"Mạng không dây đang kết nối là: {wifi_ssid}. "
        f"Địa chỉ ai pi mạng không dây là: {wlan0_ip.replace('.', ' chấm ')}."
    )
    return speech_text


def watch_hardware_button():
    global CURRENT_ACTIVITY_MODE
    
    # Thiết lập cấu hình chân GPIO an toàn
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print(f"🔘 [NÚT CỨNG] Đã kích hoạt GPIO{BUTTON_PIN} (PULL-UP) thành công.", flush=True)

    def button_worker():
        global CURRENT_ACTIVITY_MODE
        while True:
            # Khi nút bấm được nhấn xuống (Mức thấp LOW do mạch PULL-UP)
            if GPIO.input(BUTTON_PIN) == GPIO.LOW:
                start_press_time = time.time()
                has_triggered_special = False # Cờ đánh dấu đã kích hoạt chế độ đặc biệt 5s chưa
                
                # Vòng lặp quét liên tục khi nút bấm ĐANG ĐƯỢC GIỮ
                while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                    current_duration = time.time() - start_press_time
                    
                    # 🔥 CẢI TIẾN: Đạt đủ 5 giây phát lệnh LUÔN, KHÔNG CẦN đợi nhả tay
                    if current_duration >= 5.0 and not has_triggered_special:
                        print(f"\n🚨 [NÚT CỨNG]: Đã giữ liên tục {current_duration:.1f}s -> Đọc thông tin mạng ngay lập tức!", flush=True)
                        
                        network_text = get_network_speech_text()
                        print(f"🔊 [NÚT CỨNG LOG]: {network_text}")
                        mqtt_response(network_text)
                        audio_feature.text_to_speak(network_text, lang="vi")
                        
                        has_triggered_special = True # Đánh dấu đã chạy xong, không chạy lại lặp đi lặp lại khi vẫn đang giữ nút
                    
                    time.sleep(0.05) # Ngủ ngắn để tiết kiệm CPU và cập nhật thời gian thực
                
                # 2. Người dùng ĐÃ NHẢ TAY RA $\rightarrow$ Tính toán xử lý cho cú BẤM NHANH xoay vòng
                press_total_time = time.time() - start_press_time
                
                # Nếu chu kỳ bấm giữ đã kích hoạt chế độ 5 giây rồi thì nhả ra bỏ qua, không tính là bấm nhanh
                if has_triggered_special:
                    print("ℹ️ [NÚT CỨNG]: Đã nhả tay sau khi chạy xong chế độ đặc biệt.", flush=True)
                
                # Ngược lại, nếu nhả tay sớm (Bấm nhanh > 0.1s chống nhiễu và dưới 1.5s)
                elif 0.1 < press_total_time < 1.5:
                    # Thuật toán toán học chia lấy dư để tự động xoay vòng trạng thái Enum
                    current_idx = MODES_LIST.index(CURRENT_ACTIVITY_MODE)
                    
                    # 2. Áp dụng công thức chia lấy dư toán học (%) để xoay vòng tuần hoàn index
                    next_idx = (current_idx + 1) % len(MODES_LIST)
                    CURRENT_ACTIVITY_MODE = MODES_LIST[next_idx]
                    
                    # Thân hàm chỉ kiểm tra trạng thái cố định để xử lý logic hành động
                    if CURRENT_ACTIVITY_MODE == ActivityMode.MODE_GYM:
                        res = "Chế độ phòng tập"
                        print(f"\n🔄 [NÚT CỨNG]: Chuyển sang -> 🤖 {res}", flush=True)
                        mqtt_response(res)
                        audio_feature.text_to_speak(res, lang="vi")
                        # TODO: Bạn chèn thêm logic xử lý riêng cho Phòng tập (Gym) tại đây
                        
                    elif CURRENT_ACTIVITY_MODE == ActivityMode.MODE_ASKANS:
                        res = "Chế độ hỏi đáp"
                        print(f"\n🔄 [NÚT CỨNG]: Chuyển sang -> 🧠 {res}", flush=True)
                        mqtt_response(res)
                        audio_feature.text_to_speak(res, lang="vi")
                        # TODO: Bạn chèn thêm logic xử lý riêng cho Hỏi đáp (AskAns) tại đây
                        
            time.sleep(0.1) 

    t = threading.Thread(target=button_worker, daemon=True)
    t.start()