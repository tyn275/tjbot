# button_genture.py
import time
import threading
import RPi.GPIO as GPIO
import subprocess
import socket
import psutil

from features import audio_feature
from features.mqtt import mqtt_response

BUTTON_PIN = 26  
# Biến lưu vị trí chế độ hiện tại trong danh sách
CURRENT_CALLBACK_INDEX = 0

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

def watch_hardware_button(action_callbacks=None): 
    """
    Hàm kiểm soát nút bấm cứng chạy vòng lặp tuần hoàn qua mảng callback.
    :param action_callbacks: Mảng các dictionary chứa thông tin cấu hình dịch vụ.
    """
    global CURRENT_CALLBACK_INDEX
    
    # Cấu hình GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Nếu không truyền mảng callback nào, nút bấm sẽ không làm gì cả
    if not action_callbacks or not isinstance(action_callbacks, list):
        print("⚠️ [NÚT CỨNG]: Không có mảng callback hợp lệ nào được cấu hình!")
        return

    print(f"🏁 [NÚT CỨNG]: Hệ thống nút bấm sẵn sàng với {len(action_callbacks)} chế độ động.")

    def button_worker():
        while True:
            if GPIO.input(BUTTON_PIN) == GPIO.LOW:
                time.sleep(0.05) # Chống rung phím (Debounce)
                if GPIO.input(BUTTON_PIN) == GPIO.LOW:
                    start_press_time = time.time()
                    has_triggered_special = False # Cờ đánh dấu đã kích hoạt chế độ đặc biệt 5s chưa
                    
                    # Vòng lặp quét liên tục khi nút bấm ĐANG ĐƯỢC GIỮ
                    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                        current_duration = time.time() - start_press_time
                        
                        # 🔥 CẢI TIẾN: Đạt đủ 3 giây phát lệnh LUÔN, KHÔNG CẦN đợi nhả tay
                        if current_duration >= 3.0 and not has_triggered_special:
                            print(f"\n🚨 [NÚT CỨNG]: Đã giữ liên tục {current_duration:.1f}s -> Đọc thông tin mạng ngay lập tức!", flush=True)
                            
                            network_text = get_network_speech_text()
                            print(f"🔊 [NÚT CỨNG LOG]: {network_text}")
                            mqtt_response(network_text)
                            audio_feature.text_to_speak(network_text, lang="vi")
                            
                            has_triggered_special = True # Đánh dấu đã chạy xong, không chạy lại lặp đi lặp lại khi vẫn đang giữ nút
                        
                        time.sleep(0.05) # Ngủ ngắn để tiết kiệm CPU và cập nhật thời gian thực
                    
                    # 2. Người dùng ĐÃ NHẢ TAY RA $\rightarrow$ Tính toán xử lý cho cú BẤM NHANH xoay vòng
                    press_total_time = time.time() - start_press_time
                    
                                    
                    # Nếu chu kỳ bấm giữ đã kích hoạt chế độ 3 giây rồi thì nhả ra bỏ qua, không tính là bấm nhanh
                    if has_triggered_special:
                        print("ℹ️ [NÚT CỨNG]: Đã nhả tay sau khi chạy xong chế độ đặc biệt.", flush=True)
                    
                    # Ngược lại, nếu nhả tay sớm (Bấm nhanh > 0.1s chống nhiễu và dưới 1.5s)
                    elif 0.1 < press_total_time < 1.5:                                
                        # 💡 THUẬT TOÁN TOÁN HỌC XOAY VÒNG DỰA TRÊN CHIỀU DÀI MẢNG CALLBACK:
                        # Mỗi lần bấm, tăng index lên 1 và chia lấy dư cho tổng số lượng hàm trong mảng
                        global CURRENT_CALLBACK_INDEX
                        CURRENT_CALLBACK_INDEX = (CURRENT_CALLBACK_INDEX + 1) % len(action_callbacks)
                        
                        # Lấy ra cấu hình của chế độ hiện tại
                        current_mode_config = action_callbacks[CURRENT_CALLBACK_INDEX]
                        
                        mode_name = current_mode_config.get("name", f"Chế độ {CURRENT_CALLBACK_INDEX}")
                        target_function = current_mode_config.get("func")
                        
                        print(f"\n🔄 [NÚT CỨNG]: Đang chuyển sang -> {mode_name}", flush=True)
                        
                        # Đọc ra loa chế độ làm việc
                        audio_feature.text_to_speak("Đã nhận việc " + mode_name, lang="vi")
                        
                        # KÍCH HOẠT HÀM SỰ KIỆN ĐƯỢC ĐÍNH KÈM
                        if target_function and callable(target_function):
                            try:
                                # Thực thi hàm và truyền tên chế độ sang làm tham số nếu cần
                                target_function(mode_name)
                            except Exception as e:
                                print(f"❌ Lỗi khi thực thi hàm callback của {mode_name}: {e}")
                        else:
                            print(f"⚠️ Không tìm thấy hàm xử lý hợp lệ cho: {mode_name}")
                        
                while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                    time.sleep(0.1) # Chờ người dùng nhả tay ra khỏi nút bấm
            time.sleep(0.1)
    t = threading.Thread(target=button_worker, daemon=True)
    t.start()        