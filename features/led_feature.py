# features/led_feature.py
import time
import os
import pigpio  # 💡 Thay thế RPi.GPIO bằng pigpio để băm xung phần cứng (DMA PWM)

# -----------------------------------------------------------------
# CẤU HÌNH PHẦN CỨNG (LED ONBOARD & LED RGB ĐẦU CATHODE CHUNG)
# -----------------------------------------------------------------

# 1. Cấu hình đường dẫn LED Onboard hệ thống
LED_PATH = "/sys/class/leds/led0/brightness"
if not os.path.exists(LED_PATH):
    LED_PATH = "/sys/class/leds/ACT/brightness"

# 2. Cấu hình chân GPIO cho LED RGB mới (sử dụng số chân BCM)
RED_PIN = 12   # GPIO 12 (Pin 32)
GREEN_PIN = 16 # GPIO 16 (Pin 36)
BLUE_PIN = 21  # GPIO 21 (Pin 40)

# Khởi tạo kết nối với tiến trình pigpio daemon
pi = pigpio.pi()
if not pi.connected:
    print("❌ LỖI KHỞI ĐỘNG PIGPIO: Hãy chắc chắn bạn đã chạy lệnh 'sudo systemctl start pigpiod'!")

# 💡 BIẾN CỜ TOÀN CỤC: Luồng ngầm (Async) sẽ liên tục đọc cờ này để tự dừng vòng lặp.
stop_blink_flag = False

# Bảng tên màu cơ bản định dạng HEXCOLOR
COLOR_MAP = {
    "white":   "#ffffff",
    "red":     "#ff0000",
    "green":   "#00ff00",
    "blue":    "#0000ff",
    "yellow":  "#ffff00",
    "cyan":    "#00ffff",
    "magenta": "#ff00ff",
    "purple":  "#800080",
    "black":   "#000000"
}

# -----------------------------------------------------------------
# HÀM TRỢ GIÚP NỘI BỘ (INTERNAL HELPERS)
# -----------------------------------------------------------------

def _write_led(value):
    """Hàm nội bộ điều khiển LED Onboard hệ thống"""
    try:
        with open(LED_PATH, "w") as f:
            f.write(str(value))
        return True
    except Exception as e:
        print(f"-> [LỖI LED SYSTEM]: Không thể ghi vào {LED_PATH}: {e}")
        return False

def _init_gpio():
    """Khởi tạo cấu hình băm xung phần cứng thông qua pigpio"""
    if not pi.connected:
        return False
    # pigpio quản lý tần số PWM cực kỳ ổn định (Đặt tần số 2000Hz cho cả 3 chân)
    pi.set_PWM_frequency(RED_PIN, 2000)
    pi.set_PWM_frequency(GREEN_PIN, 2000)
    pi.set_PWM_frequency(BLUE_PIN, 2000)
    return True

def _hex_to_pwm_duty(hex_str):
    """Chuyển đổi chuỗi HEX màu sang dải độ sáng phần cứng pigpio (0 - 255)"""
    hex_color = hex_str.lower().strip().lstrip("#")
    if len(hex_color) != 6 or not all(c in "0123456789abcdef" for c in hex_color):
        return None
    try:
        # pigpio nhận giá trị Duty Cycle chuẩn từ 0 đến 255
        r_255 = int(hex_color[0:2], 16)
        g_255 = int(hex_color[2:4], 16)
        b_255 = int(hex_color[4:6], 16)
        return r_255, g_255, b_255
    except ValueError:
        return None

def _write_head_rgb_pwm(dc_r, dc_g, dc_b):
    """Ghi trực tiếp giá trị độ sáng (0-255) xuống chân phần cứng"""
    if not _init_gpio():
        return False
    try:
        # Sử dụng hàm set_PWM_dutycycle của pigpio để phát xung mượt mà
        pi.set_PWM_dutycycle(RED_PIN, int(dc_r))
        pi.set_PWM_dutycycle(GREEN_PIN, int(dc_g))
        pi.set_PWM_dutycycle(BLUE_PIN, int(dc_b))
        return True
    except Exception as e:
        print(f"-> [LỖI LED PWM PIGPIO]: Không thể thay đổi xung: {e}")
        return False

def _interruptible_sleep(duration):
    """💡 Hàm ngủ chia nhỏ: Phát hiện cờ dừng lập tức để thoát luồng ngầm"""
    global stop_blink_flag
    step = 0.01
    elapsed = 0
    while elapsed < duration:
        if stop_blink_flag:
            return True
        time.sleep(step)
        elapsed += step
    return False

# -----------------------------------------------------------------
# CÁC HÀM XỬ LÝ LOGIC LED ONBOARD
# -----------------------------------------------------------------

def sAct(state, color="white"):
    """(ĐỒNG BỘ): Điều khiển bật/tắt đèn LED Onboard tĩnh"""
    global stop_blink_flag
    print(f"-> [TÍNH NĂNG LED SYS] sAct: State={state}")
    stop_blink_flag = True
    
    if str(state).lower() in ["on", "1", "true"]:
        if _write_led(1): return "SUCCESS: Onboard LED is now ON"
    else:
        if _write_led(0): return "SUCCESS: Onboard LED is now OFF"
    return "ERROR: Không thể điều khiển LED hệ thống."

def ActBlink(times=3, speed="fast"):
    """(BẤT ĐỒNG BỘ): Nhấp nháy đèn Onboard"""
    global stop_blink_flag
    print(f"-> [TÍNH NĂNG LED] ActBlink: Times={times}, Speed={speed}")
    
    stop_blink_flag = False
    delay = 0.05 if speed.lower() == "fast" else 0.3
    try:
        times = int(times)
        for _ in range(times):
            if stop_blink_flag: break
            _write_led(1)
            if _interruptible_sleep(delay): break
            _write_led(0)
            if _interruptible_sleep(delay): break
        return f"SUCCESS: Onboard LED blinked {times} times"
    except ValueError:
        return "ERROR: Tham số 'times' phải là một số nguyên!"

def led_sos():
    """(BẤT ĐỒNG BỘ): Phát tín hiệu SOS qua đèn ACT"""
    global stop_blink_flag
    print("-> [TÍNH NĂNG LED] led_sos: Đang phát tín hiệu cứu hộ SOS...")
    
    stop_blink_flag = False
    SHORT_GAP, LONG_GAP = 0.15, 0.45
    ELEMENT_GAP, LETTER_GAP = 0.15, 0.4

    try:
        for _ in range(3):
            if stop_blink_flag: return "SUCCESS: SOS loop interrupted."
            _write_led(1); time.sleep(SHORT_GAP)
            _write_led(0); time.sleep(ELEMENT_GAP)
        time.sleep(LETTER_GAP)
        for _ in range(3):
            if stop_blink_flag: return "SUCCESS: SOS loop interrupted."
            _write_led(1); time.sleep(LONG_GAP)
            _write_led(0); time.sleep(ELEMENT_GAP)
        time.sleep(LETTER_GAP)
        for _ in range(3):
            if stop_blink_flag: return "SUCCESS: SOS loop interrupted."
            _write_led(1); time.sleep(SHORT_GAP)
            _write_led(0); time.sleep(ELEMENT_GAP)
        return "SUCCESS: Đã hoàn thành 1 chu kỳ SOS trên đèn ACT."
    except Exception as e:
        return f"ERROR: Không thể phát tín hiệu SOS: {e}"
    
# -----------------------------------------------------------------
# CÁC HÀM XỬ LÝ LOGIC LED ĐẦU (HỖ TRỢ PWM HOÀN HẢO)
# -----------------------------------------------------------------

def sHead(state, color="white"):
    """(ĐỒNG BỘ): Bật màu tĩnh hoặc TẮT KHẨN CẤP LED đầu."""
    global stop_blink_flag
    color_key = color.lower().strip().strip("'\"")
    state_str = str(state).lower().strip().strip("'\"")
    
    print(f"-> [SYS LED HEAD PIGPIO] sHead: State={state_str}, Color={color_key}")
    
    if state_str in ["off", "0", "false", "black"]:
        stop_blink_flag = True  
        _write_head_rgb_pwm(0, 0, 0)
        return "SUCCESS: Head LED is now OFF and Blink loop was terminated"
            
    elif state_str in ["on", "1", "true"]:
        stop_blink_flag = True  
        time.sleep(0.02) 
        stop_blink_flag = False 
        
        target_hex = COLOR_MAP.get(color_key, color_key)
        pwm_values = _hex_to_pwm_duty(target_hex)
        
        if pwm_values is not None:
            r, g, b = pwm_values
            if _write_head_rgb_pwm(r, g, b):
                return f"SUCCESS: Head LED Mixed via Hardware PWM with HEX [{target_hex}]"
                
        _write_head_rgb_pwm(255, 255, 255)
        return f"WARNING: Màu '{color}' lỗi HEX. Mặc định bật WHITE."
            
    return "ERROR: Không thể xác định trạng thái điều khiển LED đầu."

def HeadBlink(times=3, speed="fast", color="white"):
    """(BẤT ĐỒNG BỘ): Nhấp nháy đèn ở đầu."""
    global stop_blink_flag
    color_key = color.lower().strip()
    print(f"-> [TÍNH NĂNG LED HEAD] HeadBlink: Times={times}, Speed={speed}, Color={color_key}")
    
    stop_blink_flag = False
    delay = 0.08 if speed.lower() == "fast" else 0.4
    target_hex = COLOR_MAP.get(color_key, color_key)
    pwm_values = _hex_to_pwm_duty(target_hex)
    r, g, b = pwm_values if pwm_values is not None else (255, 255, 255)

    try:
        times = int(times)
        for _ in range(times):
            if stop_blink_flag: break
            _write_head_rgb_pwm(r, g, b)
            if _interruptible_sleep(delay): break
            _write_head_rgb_pwm(0, 0, 0)
            if _interruptible_sleep(delay): break
            
        _write_head_rgb_pwm(0, 0, 0) 
        return f"SUCCESS: Head LED blink process finished safely."
    except ValueError:
        return "ERROR: Tham số 'times' phải là số nguyên!"

# -----------------------------------------------------------------
# 💡 KHỐI HIỆU ỨNG RAINBOW VÔ HẠN & NHỊP THỜ SIÊU MỊN MÀNG (PIGPIO)
# -----------------------------------------------------------------

def Rainbow(effect_type="7color"):
    """(BẤT ĐỒNG BỘ): Tạo hiệu ứng Rainbow vô hạn và mượt mà hoàn toàn nhờ băm xung phần cứng DMA."""
    global stop_blink_flag
    eff = str(effect_type).lower().strip().strip("'\"")
    print(f"-> [TÍNH NĂNG RAINBOW PIGPIO] Rainbow: Khởi chạy kiểu hiệu ứng VÔ HẠN = {eff}")
    
    stop_blink_flag = False
    step_delay = 0.02 

    try:
        # Vòng lặp VÔ HẠN, chỉ thoát khi nhận lệnh sHead("off")
        while not stop_blink_flag:

            # KIỂU 1: ĐỎ - XANH LÁ (Tone R-G)
            if eff == "rg":
                for r in range(255, -1, -5):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(r, 255 - r, 0)
                    if _interruptible_sleep(step_delay): break
                for g in range(255, -1, -5):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(255 - g, g, 0)
                    if _interruptible_sleep(step_delay): break

            # KIỂU 2: ĐỎ - TRẮNG (Tone R-W)
            elif eff == "rw":
                for i in range(0, 256, 5):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(255, i, i)
                    if _interruptible_sleep(step_delay): break
                for i in range(255, -1, -5):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(255, i, i)
                    if _interruptible_sleep(step_delay): break

            # KIỂU 3: XANH LÁ - TRẮNG (Tone G-W)
            elif eff == "gw":
                for i in range(0, 256, 5):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(i, 255, i)
                    if _interruptible_sleep(step_delay): break
                for i in range(255, -1, -5):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(i, 255, i)
                    if _interruptible_sleep(step_delay): break

            # 🌈 KIỂU 4: 7 SẮC CẦU VỒNG (CHẬM, MƯỢT TUYỆT ĐỐI & VÔ HẠN)
            elif eff == "7color":
                slow_delay = 0.06  # Tốc độ làm chậm lý tưởng để hòa sắc lung linh
                # 1. Đỏ -> Vàng (Tăng G)
                for g in range(0, 256, 3): # Bước nhảy nhỏ 3 giúp dải sắc chuyển đổi vô cùng nhuyễn
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(255, g, 0)
                    if _interruptible_sleep(slow_delay): break
                # 2. Vàng -> Xanh lá (Giảm R)
                for r in range(255, -1, -3):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(r, 255, 0)
                    if _interruptible_sleep(slow_delay): break
                # 3. Xanh lá -> Cyan (Tăng B)
                for b in range(0, 256, 3):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(0, 255, b)
                    if _interruptible_sleep(slow_delay): break
                # 4. Cyan -> Xanh dương (Giảm G)
                for g in range(255, -1, -3):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(0, g, 255)
                    if _interruptible_sleep(slow_delay): break
                # 5. Xanh dương -> Magenta (Tăng R)
                for r in range(0, 256, 3):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(r, 0, 255)
                    if _interruptible_sleep(slow_delay): break
                # 6. Magenta -> Đỏ (Giảm B)
                for b in range(255, -1, -3):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(255, 0, b)
                    if _interruptible_sleep(slow_delay): break

            # 🌬️ KIỂU 5: NHỊP THỜ - BREATHING (ĐÃ KHẮC PHỤC LỖI NHÁY - MỜ TỎ SIÊU MỊN)
            elif eff == "breath":
                # Chạy từ bước nhảy 1 đơn vị, kết hợp Hardware PWM sẽ loại bỏ hoàn toàn lỗi ON/OFF
                for i in range(0, 256, 2):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(i, i, i)
                    if _interruptible_sleep(0.012): break
                for i in range(255, -1, -2):
                    if stop_blink_flag: break
                    _write_head_rgb_pwm(i, i, i)
                    if _interruptible_sleep(0.012): break
            
            else:
                _write_head_rgb_pwm(0, 0, 0)
                return f"ERROR: Không tồn tại kiểu màu [{effect_type}]"

        _write_head_rgb_pwm(0, 0, 0) 
        return f"SUCCESS: Hiệu ứng vô hạn [{effect_type}] đã được giải phóng an toàn."
    except Exception as e:
        _write_head_rgb_pwm(0, 0, 0)
        return f"ERROR tại luồng màu pigpio: {e}"

# -----------------------------------------------------------------
# HÀM TỰ KIỂM TRA TOÀN DIỆN VÀ ĐĂNG KÝ API
# -----------------------------------------------------------------

def selftest():
    print("\n--- [SELFTEST] KIỂM TRA MÔ-ĐUN LED VỚI PIGPIO ---")
    if not pi.connected:
        print("❌ THẤT BẠI: pigpio daemon chưa chạy!")
        return False
    _write_head_rgb_pwm(255, 0, 0); time.sleep(0.3)
    _write_head_rgb_pwm(0, 255, 0); time.sleep(0.3)
    _write_head_rgb_pwm(0, 0, 255); time.sleep(0.3)
    _write_head_rgb_pwm(0, 0, 0)
    print("✅ OK: Phần cứng băm xung phần cứng hoạt động hoàn hảo.")
    return True

def register(actions_map):
    actions_map["sAct"] = {"func": sAct, "params": "state, color='white'", "example": "sAct(on)"}
    actions_map["ActBlink"] = {"func": ActBlink, "params": "times=3, speed='fast'", "example": "ActBlink(5, slow)"}
    actions_map["Head"] = {"func": sHead, "params": "state, color", "example": "sHead(on, #ff00ff)"}
    actions_map["HeadBlink"] = {"func": HeadBlink, "params": "times, speed, color", "example": "HeadBlink(5, slow, blue)"}
    actions_map["led_sos"] = {"func": led_sos, "params": "", "example": "led_sos()"}
    actions_map["Rainbow"] = {"func": Rainbow, "params": "effect_type", "example": "Rainbow(7Color)"}
    print("-> [HỆ THỐNG] Đã đồng bộ pigpio API: sAct, ActBlink, sHead, HeadBlink, Rainbow")