# features/led_feature.py
import time
import os

# Tự động tìm đường dẫn chính xác của đèn LED trên Pi 4 hoặc Pi cũ
LED_PATH = "/sys/class/leds/led0/brightness"
if not os.path.exists(LED_PATH):
    LED_PATH = "/sys/class/leds/ACT/brightness"

def _write_led(value):
    """Hàm nội bộ để ghi giá trị 0 hoặc 1 vào file LED hệ thống"""
    try:
        with open(LED_PATH, "w") as f:
            f.write(str(value))
        return True
    except Exception as e:
        print(f"-> [LỖI LED SYSTEM]: Không thể ghi vào {LED_PATH}: {e}")
        return False

# -----------------------------------------------------------------
# CÁC HÀM XỬ LÝ LOGIC LED TRỰC TIẾP
# -----------------------------------------------------------------
def led_control(state, color="white"):
    """Điều khiển bật/tắt đèn LED"""
    print(f"-> [TÍNH NĂNG LED] led_control: State={state}")
    
    if state.lower() in ["on", "1", "true"]:
        if _write_led(1):
            return "SUCCESS: Onboard LED is now ON"
    else:
        if _write_led(0):
            return "SUCCESS: Onboard LED is now OFF"
    return "ERROR: Không thể điều khiển LED hệ thống."

def led_blink_custom(times=3, speed="fast"):
    """Nhấp nháy đèn theo số lần và tốc độ chỉ định"""
    print(f"-> [TÍNH NĂNG LED] led_blink_custom: Times={times}, Speed={speed}")
    
    delay = 0.05 if speed.lower() == "fast" else 0.3
    try:
        times = int(times)
        for _ in range(times):
            _write_led(1)
            time.sleep(delay)
            _write_led(0)
            time.sleep(delay)
        return f"SUCCESS: Onboard LED blinked {times} times"
    except ValueError:
        return "ERROR: Tham số 'times' phải là một số nguyên!"

def selftest():
    """Hàm tự kiểm tra trạng thái hoạt động của hệ thống LED"""
    print("\n--- [SELFTEST] BẮT ĐẦU KIỂM TRA MÔ-ĐUN LED ---")
    
    # Kiểm tra xem file led hệ thống có tồn tại không
    if not os.path.exists(LED_PATH):
        print(f"❌ THẤT BẠI: Không tìm thấy đường dẫn LED hệ thống tại {LED_PATH}!")
        return False
        
    print("💡 Chớp sáng 3 lần...")
    success_on = _write_led(1)
    time.sleep(0.2)
    success_off = _write_led(0)
    time.sleep(0.8)
    success_on = _write_led(1)
    time.sleep(0.2)
    success_off = _write_led(0)
    time.sleep(0.8)
    success_on = _write_led(1)
    time.sleep(0.2)
    success_off = _write_led(0)       
    
    if success_on and success_off:
        print("✅ THÀNH CÔNG: Mô-đun LED hoạt động hoàn hảo.")
        return True
    else:
        print("❌ THẤT BẠI: Lỗi phân quyền ghi File hệ thống (Dù file có tồn tại)!")
        return False

# -----------------------------------------------------------------
# HÀM ĐĂNG KÝ VÀ CUNG CẤP TÀI LIỆU HƯỚNG DẪN (API DOCS)
# -----------------------------------------------------------------
def register(actions_map):
    actions_map["led_control"] = {
        "func": led_control,
        "params": "state, color='white'",
        "example": "led_control(on)"
    }
    actions_map["led_blink"] = {
        "func": led_blink_custom,
        "params": "times=3, speed='fast'",
        "example": "led_blink(5, slow)"
    }
    print("-> [HỆ THỐNG] Đã đăng ký và đồng bộ tài liệu tính năng: LED")