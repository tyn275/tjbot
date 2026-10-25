# tjbot_client.py
import os
import re
import time
import socket
import subprocess
import urllib.request
from paho.mqtt import client as mqtt_client
import psutil  
from paho.mqtt.subscribeoptions import SubscribeOptions      
from button_genture import watch_hardware_button
import ast   # Phân tích cú pháp trong mqtt payload
import signal  # bắt sự kiện dừng service
import threading    # Xử lý bất đồng bộ với mọi hàm được gọi, trừ những hàm có tên bắt đầu bằng s

# 🔥 ĐÃ ĐỔI: Import cấu hình và hàm phản hồi từ module mqtt dùng chung
from features.mqtt import BROKER, PORT, USER, PASSWORD, TOPIC_PUB, BOT_ID, mqtt_response

# 📦 IMPORT CÁC TÍNH NĂNG PHẦN CỨNG TỪ THƯ MỤC FEATURES
from features import led_feature
from features import arm_feature
from features import audio_feature
from features import mic_feature
from features import cam_feature

# 🔥 ĐÃ ĐỔI: Topic nhận lệnh giờ sẽ tự động ăn theo BOT_ID lấy từ mqtt.py
TOPIC_SUB = BOT_ID + "/" + os.getenv('MQTT_TOPIC_SUB', 'commands').strip()
CLIENT_ID = os.getenv('MQTT_CLIENT_ID', f'raspberry-pi-{BOT_ID}').strip()

# =====================================================================
# KHỞI TẠO BẢNG ÁNH XẠ ACTIONS_MAP RỖNG VÀ ĐĂNG KÝ TÍNH NĂNG ĐỘNG
# =====================================================================
ACTIONS_MAP = {}

# Gọi hàm register của từng tính năng để tự điền thông tin chi tiết vào bảng map chung
led_feature.register(ACTIONS_MAP)
arm_feature.register(ACTIONS_MAP)
audio_feature.register(ACTIONS_MAP)
mic_feature.register(ACTIONS_MAP)
cam_feature.register(ACTIONS_MAP)

# =====================================================================
# CÁC HÀM TRÍCH XUẤT THÔNG TIN HỆ THỐNG & MẠNG
# =====================================================================
def get_all_interfaces_report():
    interfaces = psutil.net_if_addrs()
    card_names_map = {'wlan0': 'WiFi (Không dây)', 'eth0': 'Ethernet (Mạng dây)', 'usb0': 'USB OTG (Cáp Type-C)'}
    report_lines = []
    AF_PACKET_LINUX = getattr(socket, 'AF_PACKET', 17)
    for target_card in ['wlan0', 'eth0', 'usb0']:
        if target_card in interfaces:
            card_friendly_name = card_names_map.get(target_card, target_card)
            mac_addr, ip_addr = "UNKNOWN MAC", "Chưa kết nối (No IP)"
            for addr in interfaces[target_card]:
                if addr.family == AF_PACKET_LINUX: mac_addr = addr.address.upper()
                elif addr.family == socket.AF_INET: ip_addr = addr.address
            report_lines.append(f"   + {card_friendly_name}:\n     * MAC: {mac_addr}\n     * IP: {ip_addr}")
    return "\n".join(report_lines)

def get_wifi_ssid():
    try:
        ssid = subprocess.check_output(["iwgetid", "-r"]).decode("utf-8").strip()
        return ssid if ssid else "Not Connected to WiFi"
    except: return "N/A"

def get_public_ip():
    try: return urllib.request.urlopen('https://api.ipify.org', timeout=3).read().decode('utf8')
    except: return "Không lấy được IP Public"

def send_startup_report(client):
    network_details = get_all_interfaces_report()
    ssid = get_wifi_ssid()
    public_ip = get_public_ip()
    report_msg = (
        f"== [TJBOT STARTUP REPORT] ==\n - Trạng thái: Startup\n"
        f" - Chi tiết danh sách Card mạng:\n{network_details}\n"
        f" - Tên WiFi (SSID): {ssid}\n - Địa chỉ IP Public: {public_ip}\n"
        f" - MQTT Topic sub: {TOPIC_SUB}, pub: {TOPIC_PUB}\n"
        f"=================================---=="
    )
    print(report_msg)
    # Gửi báo cáo khởi động qua hàm mqtt_response tập trung để đồng bộ định danh client
    mqtt_response(report_msg)

# =====================================================================
# KẾT NỐI VÀ XỬ LÝ LỆNH MQTT
# =====================================================================
def connect_mqtt():
    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("Connected to MQTT Broker!")
            options = SubscribeOptions(noLocal=True)
            client.subscribe(TOPIC_SUB, options=options)
            send_startup_report(client)
        else:
            print(f"Failed to connect, return code {rc}\n")

    client = mqtt_client.Client(client_id=CLIENT_ID, callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2)
    if USER and PASSWORD: client.username_pw_set(USER, PASSWORD)
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    return client

def _parse_params(raw_params: str) -> list:
    """
    Bóc tách tham số từ chuỗi lệnh MQTT một cách robust.
    Xử lý được 3 trường hợp:
      1. Format chuẩn (MQTTX gõ tay):      TextToSpeak("text có, dấu phẩy", "vi")
      2. Format web (double-wrap):  TextToSpeak(""text có, dấu phẩy"", "vi")
      3. Fallback split thô (lưu ý có thể mất dấu phẩy trong text)
    """
    if not raw_params.strip():
        return []

    # --- THử 1: ast.literal_eval chuẩn ---
    # Xử lý tốt nhất: giữ nguyên dấu phẩy bên trong chuỗi, loại bỏ ngoặc kép tự động
    try:
        return list(ast.literal_eval(f"[{raw_params}]"))
    except Exception:
        pass

    # --- THử 2: Phát hiện và xử lý double-double-quote do web sinh ra ---
    # Ví dụ web gửi: ""Xin chào, Tôi là Bot"", "vi", "Google"
    # Người dùng gõ text có dấu phẩy, web tự động bọ thêm 1 lớp ngoặc kép
    if raw_params.startswith('""'):
        try:
            # Regex tìm phần text giữa cặp ngoặc kép kép ""...""
            # và phần còn lại (các tham số tiếp theo)
            match = re.match(r'^""(.*?)""\s*(?:,\s*(.*))?$', raw_params, re.DOTALL)
            if match:
                inner = match.group(1)      # Nội dung trong "": 'Xin chào", "Tôi là Bot'
                rest  = match.group(2) or '' # Các tham số phía sau: '"vi", "Google"'

                # Nội dung bị web tách thành các mảnh bởi '", "', gộp lại bằng ', '
                # Ví dụ: 'Xin chào", "Tôi là Bot' → 'Xin chào, Tôi là Bot'
                text = re.sub(r'",\s*"', ', ', inner)

                # Parse các tham số phía sau bình thường
                try:
                    rest_params = list(ast.literal_eval(f"[{rest}]")) if rest.strip() else []
                except Exception:
                    rest_params = [p.strip().strip('"').strip("'") for p in rest.split(',') if p.strip()]

                print(f"-> [PARSE OK - double-wrap]: text='{text}', rest={rest_params}")
                return [text] + rest_params
        except Exception as e:
            print(f"-> [PARSE double-wrap FAIL]: {e}")

    # --- FALLBACK: split thô (giữ nguyên từ phiên bản cũ, dự phòng cuối cùng) ---
    print("-> [PARSE FALLBACK]: Dùng split thô, có thể mất dấu phẩy trong text")
    return [p.strip().strip('"').strip("'") for p in raw_params.split(",") if p.strip()]


def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip()
    
    if payload in ["OK", "ERR"] or payload.startswith("SUCCESS:") or payload.startswith("ERROR:"):
        return

    print(f"\n[MQTT] Nhận lệnh từ kênh [{msg.topic}]: {payload}")
    
    # -----------------------------------------------------------------
    # XỬ LÝ LỆNH HELP NÂNG CẤP
    # -----------------------------------------------------------------
    if payload.lower() == "help":
        help_lines = ["== [TJBOT COMMANDS DOCUMENTATION] =="]
        for func_name, info in ACTIONS_MAP.items():
            help_lines.append(f" 🔹 Hàm: {func_name}({info['params']})")
            help_lines.append(f"    👉 Ví dụ mẫu: {info['example']}")
            help_lines.append("-" * 35)
        help_lines.append("====================================")
        
        help_msg = "\n".join(help_lines)
        mqtt_response(help_msg)
        client.publish(TOPIC_SUB, "OK")         
        return

    if payload.lower() == "info":
        send_startup_report(client)             
        client.publish(TOPIC_SUB, "OK")         
        return

    # -----------------------------------------------------------------
    # PHÂN TÍCH LỆNH PHẦN CỨNG
    # -----------------------------------------------------------------
    match = re.match(r"^(\w+)\((.*)\)$", payload)
    if not match or match.group(1) not in ACTIONS_MAP:
        print(f"-> [LỖI]: Sai cú pháp hoặc hàm không tồn tại: {payload}")
        client.publish(TOPIC_SUB, "ERR") 
        return

    func_name = match.group(1)
    raw_params = match.group(2)

    params = _parse_params(raw_params)


    # -----------------------------------------------------------------
    # 💡 ÁP DỤNG QUY TẮC PHÂN LUỒNG MỚI (ĐỒNG BỘ vs BẤT ĐỒNG BỘ)
    # -----------------------------------------------------------------
    try:
        target_function = ACTIONS_MAP[func_name]["func"]
        
        # TRƯỜNG HỢP 1: Hàm hệ thống/tắt khẩn cấp bắt đầu bằng chữ "s" -> Chạy ĐỒNG BỘ trực tiếp
        if func_name.startswith("s"):
            print(f"⚡ [EXEC - SYNC]: Chạy đồng bộ lệnh hệ thống ưu tiên: {func_name}")
            result = target_function(*params)
            
            if result is not None and result != "":
                mqtt_response(f"{result}")
            client.publish(TOPIC_SUB, "OK")
            
        # TRƯỜNG HỢP 2: Các hàm tác vụ thông thường (Blink, Move, Speak...) -> Chạy BẤT ĐỒNG BỘ ngầm
        else:
            print(f"🚀 [EXEC - ASYNC]: Đẩy tác vụ {func_name} sang luồng chạy ngầm...")
            
            # Khởi tạo một Thread phụ để chạy hàm con, giải phóng ngay lập tức luồng MQTT mẹ
            t = threading.Thread(
                target=_async_command_worker, 
                args=(client, target_function, params)
            )
            t.daemon = True # Tự giải phóng luồng phụ khi chương trình chính đóng
            t.start()

    except TypeError as e:
        print(f"-> [LỖI THAM SỐ]: {e}")
        client.publish(TOPIC_SUB, "ERR") 
    except Exception as e:
        print(f"-> [LỖI HỆ THỐNG]: {e}")
        client.publish(TOPIC_SUB, "ERR")


def _async_command_worker(client, target_function, params):
    """💡 HÀM WORKER PHỤ: Thực thi tác vụ bất đồng bộ ngầm và trả log lên kênh status sau khi hoàn thành"""
    try:
        result = target_function(*params)
        
        if result is not None and result != "":
            mqtt_response(f"{result}")
        client.publish(TOPIC_SUB, "OK")
    except TypeError as e:
        print(f"-> [LỖI THAM SỐ TRONG LUỒNG NGẦM]: {e}")
        client.publish(TOPIC_SUB, "ERR")
    except Exception as e:
        print(f"-> [LỖI HỆ THỐNG TRONG LUỒNG NGẦM]: {e}")
        client.publish(TOPIC_SUB, "ERR")

# =====================================================================
# Khởi tạo ban đầu
# =====================================================================
def welcome():
    """
    Hàm chào mừng hệ thống:
    - Chạy tự động ngay khi Robot vừa khởi động.
    - Kích hoạt tiến trình Selftest để kiểm tra toàn bộ linh kiện.
    - Gọi module âm thanh Audio để phát câu chào bằng giọng nói AI.
    """
    print("\n🚀 [WELCOME]: Bắt đầu tiến trình khởi động Robot đa năng...")
    
    # 1. Chạy luôn kịch bản Selftest (Kiểm tra phần cứng tự động)
    print("🚨 [WELCOME] -> Tự động chạy Selftest kiểm tra linh kiện...")
    try:
        # Gọi script selftest.py độc lập giống kịch bản của nút bấm cứng
        subprocess.run(["/usr/bin/python3", "/home/pi/tjbot_mqtt/selftest.py"], timeout=30)
        print("✅ [WELCOME] -> Hoàn thành bài kiểm tra phần cứng Selftest.")
    except Exception as e:
        print(f"❌ [WELCOME LỖI] -> Không thể tự động chạy Selftest: {e}")

    # 2. Thực hiện lời chào bằng cách gọi hàm text_to_speak từ audio_feature
    print("🔊 [WELCOME] -> Đang phát âm thanh lời chào khởi động...")
    try:
        # Lấy hàm nói từ module audio_feature đã được import ở đầu file
        if hasattr(audio_feature, 'text_to_speak'):
            chao_mung_text = "Xin chào! Robot t j bót đã khởi động và kiểm tra hệ thống thành công. Tôi đã sẵn sàng nhận lệnh."
            audio_feature.text_to_speak(chao_mung_text, lang="vi", blocking=True)
        else:
            print("⚠️ [WELCOME CẢNH BÁO]: Không tìm thấy hàm text_to_speak trong module audio_feature!")
    except Exception as e:
        print(f"❌ [WELCOME LỖI] -> Lỗi phát sinh khi robot tập nói lời chào: {e}")


def callback_trigger_hardware(command_string):
    """Hàm callback số 1: Xử lý kích hoạt phần cứng (mở Mic/Loa)"""
    print(f"⚙️ [CALLBACK 1]: Đang thực thi lệnh phần cứng -> {command_string}")
    # Logic xử lý lệnh phân tích cú pháp ở đây (ví dụ gọi mic_feature)
    # ...
    
def callback_log_system(command_string):
    """Hàm callback số 2: Ghi log lịch sử hoạt động vào file hoặc database"""
    print(f"📝 [CALLBACK 2]: Đang lưu log hệ thống -> Robot nhận lệnh '{command_string}'")
    # Logic ghi file log ở đây
    # ...
        
if __name__ == '__main__':
    client_instance = None

    # Tạo hàm callback xử lý khi nhận lệnh STOP từ systemd (SIGTERM) hoặc Ctrl+C (SIGINT)
    def sigterm_handler(signum, frame):
        print("\n🛑 [SYSTEMD] Nhận tín hiệu dừng hệ thống (SIGTERM/SIGINT)!")
        global client_instance
        if client_instance:
            print("🔄 Đang chủ động ngắt kết nối MQTT...")
            client_instance.disconnect() # Lệnh này sẽ làm gãy vòng lặp loop_forever() một cách an toàn
            print("👋 Đã ngắt kết nối MQTT thành công.")

    # Đăng ký hàm lắng nghe tín hiệu với hệ điều hành
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)

    try:
        # Cập nhật để gán client vào biến toàn cục giúp hàm sigterm_handler có thể gọi được
        try:
            myjobs = [
                {"name": "Luyện tập", "func": callback_trigger_hardware},
                {"name": "Hỏi đáp tư vấn", "func": callback_log_system}
            ]
            watch_hardware_button(action_callbacks=myjobs)
        except Exception as e:
            print(f"⚠️ Không thể bật nút bấm: {e}", flush=True)

        # Bỏ qua nếu không cần chào hỏi phức tạp
        welcome()
        
        # Bóc tách đoạn run() cũ ra đây để lấy biến client_instance
        client_instance = connect_mqtt()
        client_instance.on_message = on_message
        
        print("🤖 [TJBOT] Hệ thống đã sẵn sàng và đang lắng nghe MQTT...")
        client_instance.loop_forever() # Vòng lặp chặn, nhưng giờ có thể bẻ gãy bằng client.disconnect()
        
    except SystemExit:
        print("ℹ️ Tiến trình kết thúc thông qua SystemExit.")
    except Exception as e:
        print(f"❌ Lỗi phát sinh trong luồng chính: {e}")
    finally:
        print("🧹 [CLEANUP] Đang giải phóng chân GPIO và dọn dẹp tài nguyên...")
        try:
            # Lưu ý: File của bạn đang thiếu import GPIO, đảm bảo bạn đã import RPi.GPIO as GPIO ở đầu file nếu dùng lệnh này
            import RPi.GPIO as GPIO
            GPIO.cleanup() 
            print("✅ [CLEANUP SUCCESSFULLY] Hệ thống đã tắt an toàn.")
        except:
            print("⚠️ Không thể dọn dẹp GPIO (Có thể chưa khởi tạo hoặc thiếu thư viện).")