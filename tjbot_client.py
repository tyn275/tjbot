import os
import re
import time
import socket
import subprocess
import urllib.request
from dotenv import load_dotenv
from paho.mqtt import client as mqtt_client
import psutil  
from paho.mqtt.subscribeoptions import SubscribeOptions

# --- TẢI CẤU HÌNH TỪ FILE .ENV ---
load_dotenv()

BROKER = os.getenv('MQTT_BROKER', 'mqtt.toolhub.app').strip()
PORT = int(os.getenv('MQTT_PORT', 1883))
USER = os.getenv('MQTT_USER').strip() if os.getenv('MQTT_USER') else None
PASSWORD = os.getenv('MQTT_PASSWORD').strip() if os.getenv('MQTT_PASSWORD') else None

TOPIC_SUB = os.getenv('MQTT_TOPIC_SUB', 'tjbot1/commands').strip()
TOPIC_PUB = os.getenv('MQTT_TOPIC_PUB', 'tjbot1/status').strip()
CLIENT_ID = os.getenv('MQTT_CLIENT_ID', 'raspberry-pi-tjbot1').strip()

# =====================================================================
# 1. CÁC HÀM TRÍCH XUẤT THÔNG TIN HỆ THỐNG & MẠNG
# =====================================================================
def get_all_interfaces_report():
    """ Quét toàn bộ hệ thống để lấy IP và MAC của từng card mạng cụ thể """
    interfaces = psutil.net_if_addrs()
    
    card_names_map = {
        'wlan0': 'WiFi (Không dây)',
        'eth0': 'Ethernet (Mạng dây)',
        'usb0': 'USB OTG (Cáp Type-C)'
    }
    
    report_lines = []
    
    # Định nghĩa hằng số lớp liên kết phần cứng trên Linux (MAC Address)
    # Thường tương đương với socket.AF_PACKET (giá trị 17)
    AF_PACKET_LINUX = getattr(socket, 'AF_PACKET', 17)
    
    for target_card in ['wlan0', 'eth0', 'usb0']:
        if target_card in interfaces:
            card_friendly_name = card_names_map.get(target_card, target_card)
            mac_addr = "UNKNOWN MAC"
            ip_addr = "Chưa kết nối (No IP)"
            
            for addr in interfaces[target_card]:
                # Đọc địa chỉ MAC phần cứng trên Linux
                if addr.family == AF_PACKET_LINUX:
                    mac_addr = addr.address.upper()
                # Đọc địa chỉ IPv4
                elif addr.family == socket.AF_INET:
                    ip_addr = addr.address
            
            report_lines.append(f"   + {card_friendly_name}:\n     * MAC: {mac_addr}\n     * IP: {ip_addr}")
            
    return "\n".join(report_lines)

def get_wifi_ssid():
    """Lấy tên mạng WiFi (SSID) đang kết nối trên Raspberry Pi"""
    try:
        ssid = subprocess.check_output(["iwgetid", "-r"]).decode("utf-8").strip()
        return ssid if ssid else "Not Connected to WiFi"
    except:
        return "N/A (Có thể dùng mạng dây/OTG)"

def get_public_ip():
    """Lấy địa chỉ IP Public công cộng thông qua dịch vụ ipify"""
    try:
        return urllib.request.urlopen('https://api.ipify.org', timeout=3).read().decode('utf8')
    except:
        return "Không lấy được IP Public (Mất internet)"

def send_startup_report(client):
    """Gửi báo cáo tổng quan mọi card mạng khi vừa khởi động"""
    network_details = get_all_interfaces_report()
    ssid = get_wifi_ssid()
    public_ip = get_public_ip()
    
    report_msg = (
        f"== [TJBOT STARTUP REPORT] ==\n"
        f" - Trạng thái: Startup\n"
        f" - Chi tiết danh sách Card mạng:\n"
        f"{network_details}\n"
        f" - Tên WiFi đang kết nối (SSID): {ssid}\n"
        f" - Địa chỉ IP Public (Internet): {public_ip}\n"
        f"============================="
    )
    print(report_msg)
    client.publish(TOPIC_PUB, report_msg, retain=True)

# =====================================================================
# 2. ĐỊNH NGHĨA CÁC HÀM ROBOT VÀ BẢNG ÁNH XẠ ACTIONS_MAP
# =====================================================================
def led_control(state, color="white"):
    print(f"-> [EXEC] led_control: State={state}, Color={color}")
    return f"LED changed to {state} ({color})"

def wave_hand(speed, times=1):
    print(f"-> [EXEC] wave_hand: Speed={speed}, Times={times}")
    return f"Hand waved {times} times at {speed}"

ACTIONS_MAP = {
    "led_control": led_control,
    "wave_hand": wave_hand
}

# =====================================================================
# 3. KẾT NỐI VÀ XỬ LÝ LỆNH MQTT
# =====================================================================
def connect_mqtt():
    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("Connected to MQTT Broker!")
            # 🔥 ĐÃ FIX: Truyền chính xác thuộc tính options vào hàm subscribe để kích hoạt noLocal
            options = SubscribeOptions(noLocal=True)
            client.subscribe(TOPIC_SUB, options=options)
            
            send_startup_report(client)
        else:
            print(f"Failed to connect, return code {rc}\n")

    client = mqtt_client.Client(client_id=CLIENT_ID, callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2)
    if USER and PASSWORD:
        client.username_pw_set(USER, PASSWORD)
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    return client

def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip()
    
    # 🚨 BỘ LỌC CHẶN LẶP PHÒNG THỦ: Tránh xử lý mã phản hồi
    if payload in ["OK", "ERR"] or payload.startswith("SUCCESS:") or payload.startswith("ERROR:"):
        return

    print(f"\n[MQTT] Nhận lệnh từ kênh [{msg.topic}]: {payload}")
    
    # =====================================================================
    # 1. XỬ LÝ CÁC LỆNH ĐẶC BIỆT (HELP / INFO)
    # =====================================================================
    if payload.lower() == "help":
        valid_functions = ", ".join([f"{func}()" for func in ACTIONS_MAP.keys()])
        help_msg = f"== [TJBOT COMMANDS HELP] ==\n Danh sách lệnh hợp lệ: [{valid_functions}]\n==========================="
        print("-> Thực thi lệnh: help")
        client.publish(TOPIC_PUB, help_msg)    
        client.publish(TOPIC_SUB, "OK")         
        return

    if payload.lower() == "info":
        print("-> Thực thi lệnh: info (Gửi lại Startup Report)")
        send_startup_report(client)             
        client.publish(TOPIC_SUB, "OK")         
        return

    # =====================================================================
    # 2. PHÂN TÍCH VÀ XỬ LÝ CÁC HÀM PHẦN CỨNG (RPC)
    # =====================================================================
    match = re.match(r"^(\w+)\((.*)\)$", payload)
    
    if not match or match.group(1) not in ACTIONS_MAP:
        print(f"-> [LỖI]: Sai cú pháp hoặc hàm không tồn tại: {payload}")
        client.publish(TOPIC_SUB, "ERR") 
        return

    func_name = match.group(1)
    raw_params = match.group(2)
    params = [p.strip() for p in raw_params.split(",")] if raw_params else []

    try:
        target_function = ACTIONS_MAP[func_name]
        result = target_function(*params)
        
        client.publish(TOPIC_PUB, f"SUCCESS: {result}")
        client.publish(TOPIC_SUB, "OK")
        
    except TypeError as e:
        print(f"-> [LỖI TẠM THỜI]: Sai số lượng tham số cho hàm '{func_name}': {e}")
        client.publish(TOPIC_SUB, "ERR") 
    except Exception as e:
        print(f"-> [LỖI HỆ THỐNG]: {e}")
        client.publish(TOPIC_SUB, "ERR")

def run():
    client = connect_mqtt()
    client.on_message = on_message
    client.loop_forever() 

if __name__ == '__main__':
    run()