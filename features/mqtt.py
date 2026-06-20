# features/mqtt.py
import os
from dotenv import load_dotenv
from paho.mqtt import client as mqtt_client

# Tải cấu hình môi trường từ file .env
load_dotenv()

BOT_ID = os.getenv('BOT_ID', 'tjbot0').strip()
BROKER = os.getenv('MQTT_BROKER', 'mqtt.toolhub.app').strip()
PORT = int(os.getenv('MQTT_PORT', 1883))
USER = os.getenv('MQTT_USER').strip() if os.getenv('MQTT_USER') else None
PASSWORD = os.getenv('MQTT_PASSWORD').strip() if os.getenv('MQTT_PASSWORD') else None

# Topic phản hồi trạng thái chuẩn của hệ thống
TOPIC_PUB = BOT_ID + "/" + os.getenv('MQTT_TOPIC_PUB', 'status').strip()

def mqtt_response(text):
    """
    Hàm tập trung đóng gói việc gửi dữ liệu phản hồi ngược lại Broker qua TOPIC_PUB.
    Có thể gọi từ bất kỳ mô-đun tính năng nào (Mic, Arm, Led...).
    """
    try:
        # Tạo client định danh động dựa trên BOT_ID để tránh xung đột kết nối
        client = mqtt_client.Client(
            client_id=f"{BOT_ID}-shared-reporter", 
            callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2
        )
        
        if USER and PASSWORD:
            client.username_pw_set(USER, PASSWORD)
            
        client.connect(BROKER, PORT, 60)
        
        # Bắn tin nhắn trực tiếp vào kênh TOPIC_PUB chung của hệ thống
        client.publish(TOPIC_PUB, text)
        print(f"-> [MQTT_SHARED]: Đã đẩy phản hồi lên [{TOPIC_PUB}]: {text}")
        
        client.disconnect()
    except Exception as e:
        print(f"❌ [MQTT_SHARED LỖI]: Không thể gửi dữ liệu phản hồi: {e}")