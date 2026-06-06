# features/led_feature.py
import time
import os
import RPi.GPIO as GPIO

# -----------------------------------------------------------------
# CẤU HÌNH PHẦN CỨNG (LED ONBOARD & LED RGB ĐẦU CATHODE CHUNG)
# -----------------------------------------------------------------

# 1. Cấu hình đường dẫn LED Onboard cũ
LED_PATH = "/sys/class/leds/led0/brightness"
if not os.path.exists(LED_PATH):
    LED_PATH = "/sys/class/leds/ACT/brightness"

# 2. Cấu hình chân GPIO cho LED RGB mới
RED_PIN = 16
GREEN_PIN = 20
BLUE_PIN = 21

# Khai báo các đối tượng điều xung PWM toàn cục
pwm_R = None
pwm_G = None
pwm_B = None

# Bảng tên màu cơ bản đã ĐƯỢC CHUẨN HÓA về định dạng HEXCOLOR thống nhất
COLOR_MAP = {
    "white":   "#ffffff",
    "red":     "#ff0000",
    "green":   "#00ff00",
    "blue":    "#0000ff",
    "yellow":  "#ffff00",
    "cyan":    "#00ffff",
    "magenta": "#ff00ff",
    "purple":  "#800080",
    "off":     "#000000"
}

# -----------------------------------------------------------------
# HÀM TRỢ GIÚP NỘI BỘ (INTERNAL HELPERS)
# -----------------------------------------------------------------

def _write_led(value):
    """Hàm nội bộ cũ để ghi giá trị 0 hoặc 1 vào file LED hệ thống"""
    try:
        with open(LED_PATH, "w") as f:
            f.write(str(value))
        return True
    except Exception as e:
        print(f"-> [LỖI LED SYSTEM]: Không thể ghi vào {LED_PATH}: {e}")
        return False

def _init_gpio():
    """Khởi tạo cấu hình các chân GPIO và kích hoạt chế độ băm xung PWM"""
    global pwm_R, pwm_G, pwm_B
    try:
        if GPIO.getmode() is None:
            GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Thiết lập hướng xuất tín hiệu cho các chân
        GPIO.setup([RED_PIN, GREEN_PIN, BLUE_PIN], GPIO.OUT)
        
        # Khởi tạo bộ băm xung với tần số 2000Hz chống nhấp nháy mắt thường
        if pwm_R is None:
            pwm_R = GPIO.PWM(RED_PIN, 2000)
            pwm_G = GPIO.PWM(GREEN_PIN, 2000)
            pwm_B = GPIO.PWM(BLUE_PIN, 2000)
            
            # Bắt đầu phát xung ở mức 0% (Tắt đèn)
            pwm_R.start(0)
            pwm_G.start(0)
            pwm_B.start(0)
        return True
    except Exception as e:
        print(f"-> [LỖI GPIO PWM]: Không thể cấu hình băm xung LED: {e}")
        return False

def _hex_to_pwm_duty(hex_str):
    """Hàm bổ sung: Chuyển đổi một chuỗi hex màu bất kỳ sang bộ ba tỷ lệ phần trăm PWM (dc_r, dc_g, dc_b)"""
    hex_color = hex_str.lower().strip().lstrip("#")
    if len(hex_color) != 6 or not all(c in "0123456789abcdef" for c in hex_color):
        return None
    try:
        # Tách chuỗi hex thành 3 giá trị nguyên từ 0 - 255
        r_255 = int(hex_color[0:2], 16)
        g_255 = int(hex_color[2:4], 16)
        b_255 = int(hex_color[4:6], 16)
        
        # Quy đổi công thức chuẩn từ dải 255 sang phần trăm xung PWM (0 - 100%)
        dc_r = (r_255 / 255.0) * 100.0
        dc_g = (g_255 / 255.0) * 100.0
        dc_b = (b_255 / 255.0) * 100.0
        return dc_r, dc_g, dc_b
    except ValueError:
        return None

def _write_head_rgb_pwm(dc_r, dc_g, dc_b):
    """Hàm nội bộ thay đổi Duty Cycle (0.0 - 100.0) của 3 kênh để đổi màu mịn"""
    if not _init_gpio():
        return False
    try:
        pwm_R.ChangeDutyCycle(dc_r)
        pwm_G.ChangeDutyCycle(dc_g)
        pwm_B.ChangeDutyCycle(dc_b)
        return True
    except Exception as e:
        print(f"-> [LỖI LED PWM]: Không thể thay đổi độ sáng xung: {e}")
        return False

# -----------------------------------------------------------------
# CÁC HÀM XỬ LÝ LOGIC LED TRỰC TIẾP CŨ (ONBOARD CỦA PI)
# -----------------------------------------------------------------

def led_control(state, color="white"):
    """Điều khiển bật/tắt đèn LED Onboard nguyên bản"""
    print(f"-> [TÍNH NĂNG LED] led_control: State={state}")
    
    if state.lower() in ["on", "1", "true"]:
        if _write_led(1):
            return "SUCCESS: Onboard LED is now ON"
    else:
        if _write_led(0):
            return "SUCCESS: Onboard LED is now OFF"
    return "ERROR: Không thể điều khiển LED hệ thống."

def led_blink_custom(times=3, speed="fast"):
    """Nhấp nháy đèn Onboard theo số lần và tốc độ chỉ định"""
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

def led_sos():
    """BỔ SUNG MỚI: Phát tín hiệu SOS qua đèn ACT (Onboard LED) theo mã Morse"""
    print("-> [TÍNH NĂNG LED] led_sos: Đang phát tín hiệu cứu hộ SOS...")
    
    # Chuẩn thời gian Morse cơ bản: 
    SHORT_GAP = 0.15  # Thời gian chớp ngắn (dấu chấm)
    LONG_GAP = 0.45   # Thời gian chớp dài (dấu gạch)
    ELEMENT_GAP = 0.15 # Khoảng cách nghỉ giữa các lần chớp trong 1 ký tự
    LETTER_GAP = 0.4  # Khoảng cách nghỉ giữa các chữ cái (S - O - S)

    try:
        # 1. Chữ 'S' (3 chớp ngắn)
        for _ in range(3):
            _write_led(1); time.sleep(SHORT_GAP)
            _write_led(0); time.sleep(ELEMENT_GAP)
        time.sleep(LETTER_GAP)

        # 2. Chữ 'O' (3 chớp dài)
        for _ in range(3):
            _write_led(1); time.sleep(LONG_GAP)
            _write_led(0); time.sleep(ELEMENT_GAP)
        time.sleep(LETTER_GAP)

        # 3. Chữ 'S' (3 chớp ngắn)
        for _ in range(3):
            _write_led(1); time.sleep(SHORT_GAP)
            _write_led(0); time.sleep(ELEMENT_GAP)
            
        return "SUCCESS: Đã hoàn thành 1 chu kỳ phát tín hiệu SOS trên đèn ACT."
    except Exception as e:
        return f"ERROR: Không thể phát tín hiệu SOS: {e}"
    
# -----------------------------------------------------------------
# CÁC HÀM XỬ LÝ LOGIC LED BỔ SUNG MỚI (ĐẦU TJBOT - HỖ TRỢ PWM & HEX)
# -----------------------------------------------------------------

def head_led_control(state, color="white"):
    """Điều khiển bật/tắt và pha trộn màu LED bằng PWM theo tên màu hoặc mã #rrggbb trực tiếp"""
    color_key = color.lower().strip()
    print(f"-> [TÍNH NĂNG LED HEAD PWM] head_led_control: State={state}, Color={color_key}")
    
    # 1. XỬ LÝ LỆNH TẮT ĐÈN HEAD
    if state.lower() in ["off", "0", "false"]:
        if _write_head_rgb_pwm(0, 0, 0):
            return "SUCCESS: Head LED is now OFF via PWM"
            
    # 2. XỬ LÝ LỆNH BẬT ĐÈN HEAD
    elif state.lower() in ["on", "1", "true"]:
        # Bước 1: Nếu color truyền vào nằm trong bảng tra cứu COLOR_MAP, lấy mã HEX tương ứng ra
        target_hex = COLOR_MAP.get(color_key, color_key)
        
        # Bước 2: Biên dịch mã HEX đó ra thông số phần trăm Duty Cycle cho PWM
        pwm_values = _hex_to_pwm_duty(target_hex)
        
        if pwm_values is not None:
            dc_r, dc_g, dc_b = pwm_values
            if _write_head_rgb_pwm(dc_r, dc_g, dc_b):
                return f"SUCCESS: Head LED Mixed via PWM with HEX [{target_hex}] -> Duty(R:{dc_r:.1f}%, G:{dc_g:.1f}%, B:{dc_b:.1f}%)"
                
        # Bước 3: Nếu mã màu nhập vào hoàn toàn sai cú pháp hoặc lỗi hệ thống -> Mặc định kích hoạt màu TRẮNG 100%
        _write_head_rgb_pwm(100, 100, 100)
        return f"WARNING: Màu '{color}' không thể định dạng thành HEXCOLOR. Mặc định bật màu WHITE."
            
    return "ERROR: Không thể xác định trạng thái điều khiển LED đầu."

def head_led_blink(times=3, speed="fast", color="white"):
    """Nhấp nháy đèn ở đầu bằng cách bật/tắt chu kỳ xung PWM theo màu tùy chọn (Tên hoặc HEX)"""
    color_key = color.lower().strip()
    print(f"-> [TÍNH NĂNG LED HEAD] head_led_blink: Times={times}, Speed={speed}, Color={color_key}")
    
    delay = 0.08 if speed.lower() == "fast" else 0.4
    
    # Tìm kiếm mã HEX tương ứng thông qua bảng tra cứu hoặc tự xử lý nếu nhập mã trực tiếp
    target_hex = COLOR_MAP.get(color_key, color_key)
    pwm_values = _hex_to_pwm_duty(target_hex)
    
    # Nếu lấy dữ liệu màu thành công, nạp thông số; Nếu thất bại, mặc định chọn Trắng (100, 100, 100)
    dc_r, dc_g, dc_b = pwm_values if pwm_values is not None else (100, 100, 100)

    try:
        times = int(times)
        for _ in range(times):
            _write_head_rgb_pwm(dc_r, dc_g, dc_b)
            time.sleep(delay)
            _write_head_rgb_pwm(0, 0, 0)
            time.sleep(delay)
        return f"SUCCESS: Head LED blinked {times} times with color [{target_hex}]"
    except ValueError:
        return "ERROR: Tham số 'times' phải là một số nguyên!"

# -----------------------------------------------------------------
# HÀM TỰ KIỂM TRA TOÀN DIỆN (GỘP CẢ KIỂM TRA CŨ VÀ MỚI)
# -----------------------------------------------------------------

def selftest():
    """Hàm tự kiểm tra trạng thái hoạt động của cả LED Onboard và LED PWM ở đầu"""
    print("\n--- [SELFTEST] BẮT ĐẦU KIỂM TRA TOÀN BỘ MÔ-ĐUN LED (CÓ PWM) ---")
    
    # 1. Thực hiện kiểm tra cụm LED Onboard nguyên bản
    print("[1/2] Đang kiểm tra LED Onboard hệ thống...")
    if not os.path.exists(LED_PATH):
        print(f"❌ THẤT BẠI: Không tìm thấy đường dẫn LED hệ thống tại {LED_PATH}!")
        onboard_ok = False
    else:
        print("💡 Chớp sáng LED onboard hệ thống 3 lần...")
        success_on = _write_led(1)
        time.sleep(0.2)
        success_off = _write_led(0)
        time.sleep(0.6)
        _write_led(1); time.sleep(0.2); _write_led(0); time.sleep(0.6)
        _write_led(1); time.sleep(0.2); _write_led(0)       
        
        if success_on and success_off:
            print("✅ OK: Cụm LED Onboard phản hồi tốt.")
            onboard_ok = True
        else:
            print("❌ THẤT BẠI: Lỗi phân quyền ghi File hệ thống!")
            onboard_ok = False

    print("-----------------------------------------------------------------")

    # 2. Thực hiện kiểm tra cụm LED RGB PWM ở đầu mới bằng hiệu ứng tăng sáng mịn
    print("[2/2] Đang kiểm tra hệ thống điều xung PWM của LED RGB Đầu...")
    if not _init_gpio():
        print("❌ THẤT BẠI: Lỗi khởi tạo cấu hình thư viện GPIO!")
        rgb_ok = False
    else:
        print("💡 Khởi chạy hiệu ứng tăng mờ dần (Fade In) màu ĐỎ để kiểm tra phần cứng bộ băm xung...")
        try:
            # Tăng chu kỳ nhiệm vụ từ 0% lên đến 100% công suất
            for brightness in range(0, 101, 4):
                _write_head_rgb_pwm(brightness, 0, 0)
                time.sleep(0.02)
            time.sleep(0.3)
            # Tắt hẳn đèn sau khi test xong
            _write_head_rgb_pwm(0, 0, 0)
            print("✅ OK: Bộ điều xung PWM của LED Đầu hoạt động cực kỳ mượt mà.")
            rgb_ok = True
        except Exception as e:
            print(f"❌ THẤT BẠI: Xảy ra xung đột trong quá trình phát xung: {e}")
            rgb_ok = False
            
    print("\n--- [KẾT QUẢ TỔNG HỢP SELFTEST MÔ-ĐUN ĐÈN ĐIỀU KHIỂN] ---")
    if onboard_ok and rgb_ok:
        print("=> TOÀN BỘ MÔ-ĐUN LED TRÊN ROBOT HOẠT ĐỘNG HOÀN HẢO! ✅")
        return True
    else:
        print("=> HỆ THỐNG PHÁT HIỆN CÓ LỖI Ở MỘT TRONG HAI CỤM ĐÈN ĐIỀU KHIỂN! ❌")
        return False

# -----------------------------------------------------------------
# HÀM ĐĂNG KÝ VÀ CUNG CẤP TÀI LIỆU HƯỚNG DẪN (API DOCS)
# -----------------------------------------------------------------

def register(actions_map):
    # Đăng ký các hàm cũ
    actions_map["Act"] = {
        "func": led_control,
        "params": "state, color='white'",
        "example": "led_control(on)"
    }
       
    actions_map["ActBlink"] = {
        "func": led_blink_custom,
        "params": "times=3, speed='fast'",
        "example": "led_blink(5, slow)"
    }
    
    # Đăng ký các hàm bổ sung mới
    actions_map["Head"] = {
        "func": head_led_control,
        "params": "state, color='white | #FFFFFF'",
        "example": "head_led_control('on', '#ff00ff')"
    }
    actions_map["HeadBlink"] = {
        "func": head_led_blink,
        "params": "times=3, speed='fast', color='white | #FFFFFF'",
        "example": "head_led_blink(5, 'slow', 'blue')"
    }
    print("-> [HỆ THỐNG] Đã đồng bộ tài liệu: Gồm LED ACT & LED RGB trên đầu")