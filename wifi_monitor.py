# wifi_monitor.py
import time
import urllib.request
from features.led_feature import led_sos

def check_wifi_connection():
    """Kiểm tra xem Raspberry Pi có kết nối được Internet thông qua Wifi không"""
    try:
        # Cố gắng gửi một request kết nối đến DNS tin cậy của Google
        # Timeout trong vòng 2 giây để tránh bị treo tiến trình
        urllib.request.urlopen('https://8.8.8.8', timeout=2)
        return True
    except Exception:
        return False

def main():
    print("🚀 [HỆ THỐNG] Tiến trình giám sát kết nối mạng Wifi đã được kích hoạt ngầm...")
    
    # Khoảng thời gian định kỳ kiểm tra (Ví dụ: Cứ 15 giây kiểm tra 1 lần)
    CHECK_INTERVAL = 15 
    # Khoảng cách nghỉ giữa các chu kỳ lặp lại mã SOS liên tục khi mất mạng
    SOS_LOOP_GAP = 2.0 

    while True:
        if check_wifi_connection():
            # Nếu có mạng ổn định, tiến trình sẽ ngủ và kiểm tra lại sau
            time.sleep(CHECK_INTERVAL)
        else:
            print("⚠️ [CẢNH BÁO MẠNG]: Không thể kết nối Wifi hoặc rớt Internet! Đang phát tín hiệu SOS...")
            
            # Khi mất mạng, tiến trình sẽ nháy SOS liên tục trong vòng khoảng 15 giây 
            # trước khi thử thực hiện ping kiểm tra lại trạng thái mạng một lần nữa.
            for _ in range(3):
                led_sos()
                time.sleep(SOS_LOOP_GAP)

if __name__ == "__main__":
    main()