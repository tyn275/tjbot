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

# 📦 IMPORT CÁC TÍNH NĂNG PHẦN CỨNG TỪ THƯ MỤC FEATURES
from features import led_feature
from features import arm_feature
from features import audio_feature
from features import mic_feature

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
# KHỞI TẠO BẢNG ÁNH XẠ ACTIONS_MAP RỖNG VÀ ĐĂNG KÝ TÍNH NĂNG ĐỘNG
# =====================================================================
ACTIONS_MAP = {}

# Gọi hàm register của từng tính năng để tự điền thông tin chi tiết vào bảng map chung
led_feature.register(ACTIONS_MAP)
arm_feature.register(ACTIONS_MAP)
audio_feature.register(ACTIONS_MAP)
mic_feature.register(ACTIONS_MAP)

# =====================================================================
# CÁC HÀM TRÍCH XUẤT THÔNG TIN HỆ THỐNG & MẠNG (Giữ nguyên)
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
        f" - Tên WiFi (SSID): {ssid}\n - Địa chỉ IP Public: {public_ip}\n============================="
    )
    print(report_msg)
    client.publish(TOPIC_PUB, report_msg, retain=True)

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

def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip()
    
    if payload in ["OK", "ERR"] or payload.startswith("SUCCESS:") or payload.startswith("ERROR:"):
        return

    print(f"\n[MQTT] Nhận lệnh từ kênh [{msg.topic}]: {payload}")
    
    # -----------------------------------------------------------------
    # XỬ LÝ LỆNH HELP NÂNG CẤP (In chi tiết hướng dẫn sử dụng)
    # -----------------------------------------------------------------
    if payload.lower() == "help":
        help_lines = ["== [TJBOT COMMANDS DOCUMENTATION] =="]
        for func_name, info in ACTIONS_MAP.items():
            help_lines.append(f" 🔹 Hàm: {func_name}({info['params']})")
            help_lines.append(f"    👉 Ví dụ mẫu: {info['example']}")
            help_lines.append("-" * 35)
        help_lines.append("====================================")
        
        help_msg = "\n".join(help_lines)
        client.publish(TOPIC_PUB, help_msg)    # Trả tài liệu hướng dẫn về kênh status
        client.publish(TOPIC_SUB, "OK")         # Xác nhận ngắn gọn về kênh command
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
    params = [p.strip() for p in raw_params.split(",")] if raw_params else []

    try:
        # 🔥 ĐÃ FIX: Lấy hàm thực thi nằm trong sub-key 'func'
        target_function = ACTIONS_MAP[func_name]["func"]
        result = target_function(*params)
        
        client.publish(TOPIC_PUB, f"{result}")
        client.publish(TOPIC_SUB, "OK")
    except TypeError as e:
        print(f"-> [LỖI THAM SỐ]: {e}")
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