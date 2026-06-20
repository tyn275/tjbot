# features/arm_feature.py
import time
from gpiozero import AngularServo

SERVO_PIN = 7   # ứng với pin 26   

# Biến toàn cục để ghi nhớ góc quay cuối cùng nhằm tái định vị chính xác khi phục hồi lực (attach)
last_known_angle = 0

try:
    # Nới rộng xung ra góc cực đại: 0.45ms (0.00045) đến 2.45ms (0.00245)
    servo = AngularServo(
        SERVO_PIN, 
        min_angle=-90, 
        max_angle=90, 
        min_pulse_width=0.00045, 
        max_pulse_width=0.00245
    )
    print("-> [HỆ THỐNG] Đã hiệu chuẩn Driver: Mở rộng hành trình Servo lên 180 độ.")
except Exception as e:
    print(f"-> [CẢNH BÁO SERVO]: Không thể khởi tạo Servo ({e})")
    servo = None

# -----------------------------------------------------------------
# CÁC HÀM XỬ LÝ LOGIC ĐIỀU KHIỂN SERVO
# -----------------------------------------------------------------
def muscle_control(state="on"):
    """
    Điều khiển cơ bắp của Robot:
    - state="on" : Cấp điện gồng giữ vị trí (Attach)
    - state="off": Ngắt điện xả lực thả lỏng (Detach)
    """
    global last_known_angle
    if not servo:
        return "ERROR: Servo chưa được khởi tạo!"

    state_clean = state.lower().strip()
    
    if state_clean == "on":
        try:
            # Gán lại góc cũ giúp bật lại bộ phát xung PWM (Attach) mà không bị giật cơ
            servo.angle = last_known_angle
            print(f"-> [TÍNH NĂNG CÁNH TAY] Muscle(on): Đã cấp điện gồng giữ tại góc {last_known_angle} độ.")
            return f"SUCCESS: Đã bật cơ bắp (Gồng giữ tại góc {last_known_angle} độ)."
        except Exception as e:
            return f"ERROR: Không thể bật cơ bắp Servo: {e}"
            
    elif state_clean == "off":
        try:
            servo.detach()
            print("-> [TÍNH NĂNG CÁNH TAY] Muscle(off): Đã ngắt điện giải phóng cơ khí.")
            return "SUCCESS: Đã tắt cơ bắp (Cánh tay thả lỏng)."
        except Exception as e:
            return f"ERROR: Không thể xả lực cơ bắp Servo: {e}"
            
    else:
        return "ERROR: Tham số không hợp lệ! Chỉ chấp nhận 'on' hoặc 'off'."

def wave_hand(speed="fast", times=3):
    """Hàm điều khiển robot vẫy tay qua lại"""
    global last_known_angle
    print(f"-> [TÍNH NĂNG CÁNH TAY] wave_hand: Speed={speed}, Times={times}")
    if not servo:
        return "ERROR: Servo chưa được khởi tạo!"

    delay = 0.2 if speed.lower() == "fast" else 0.5
    try:
        times = int(times)
        for _ in range(times):
            servo.angle = 45   # Quay sang phải
            time.sleep(delay)
            servo.angle = -45  # Quay sang trái
            time.sleep(delay)
        
        servo.angle = 0 # Đưa tay về vị trí chính giữa khi xong
        last_known_angle = 0 # Cập nhật lại góc bộ nhớ
        return f"SUCCESS: Đã vẫy tay {times} lần."
    except ValueError:
        return "ERROR: Tham số 'times' phải là số nguyên!"

def set_arm_angle(angle=0):
    """Hàm quay cánh tay đến một góc cụ thể (Từ -90 đến 90 độ)"""
    global last_known_angle
    print(f"-> [TÍNH NĂNG CÁNH TAY] set_arm_angle: Góc {angle} độ")
    if not servo:
        return "ERROR: Servo chưa được khởi tạo!"

    try:
        angle = float(angle)
        if -90 <= angle <= 90:
            servo.angle = angle
            last_known_angle = angle # Ghi nhớ lại góc này
            return f"SUCCESS: Cánh tay đã quay đến góc {angle} độ."
        else:
            return "ERROR: Góc quay phải nằm trong khoảng từ -90 đến 90!"
    except ValueError:
        return "ERROR: Góc quay phải là một số!"

# -----------------------------------------------------------------
# HÀM SELFTEST TỰ ĐỘNG (GỌI TỪ FILE SELFTEST VẬN HÀNH CHUNG)
# -----------------------------------------------------------------
def selftest():
    """Hàm tự kiểm tra trạng thái hoạt động của Servo theo kịch bản chính xác"""
    global last_known_angle
    print("\n--- [SELFTEST] BẮT ĐẦU KIỂM TRA MÔ-ĐUN SERVO CÁNH TAY ---")
    if not servo:
        print("❌ THẤT BẠI: Thiết bị Servo chưa sẵn sàng.")
        return False

    try:
        print("🤖 Step 1: Cho cánh tay về CHÍNH GIỮA (90 độ)")
        servo.angle = 0
        time.sleep(0.7)

        print("🤖 Step 2: Quay nhanh về góc 0 độ")
        servo.angle = -90
        time.sleep(0.7)

        print("🤖 Step 3: Quay nhanh về góc 180 độ")
        servo.angle = 90
        time.sleep(0.7)

        print("🤖 Step 4: Chuyển động TỪ TỪ từ 180 độ về 0 độ (trong 2 giây)...")
        start_angle = 90
        end_angle = -90
        steps = 30      
        delay_per_step = 0.02 
        angle_per_step = (end_angle - start_angle) / steps
        
        current_angle = start_angle
        for _ in range(steps):
            current_angle += angle_per_step
            servo.angle = current_angle
            time.sleep(delay_per_step)
            
        time.sleep(0.7) 

        print("🤖 Step 5: Quay trở lại vị trí CHÍNH GIỮA (90 độ)")
        servo.angle = 0
        last_known_angle = 0

        print("✅ THÀNH CÔNG: Servo hoàn thành kịch bản quét góc và chuyển động mượt 2s.")
        return True

    except Exception as e:
        print(f"❌ THẤT BẠI: Lỗi phát sinh trong kịch bản quét Servo: {e}")
        return False

# Đăng ký hàm với hệ thống MQTT
def register(actions_map):
    actions_map["Wavehand"] = {"func": wave_hand, "params": "speed=fast|slow, times=3", "example": "Wavehand(slow, 5)"}
    actions_map["Arm"] = {"func": set_arm_angle, "params": "angle=0", "example": "Arm(45)"}
    
    # 🔥 ĐÃ ĐỔI: Đăng ký hàm Muscle duy nhất nhận tham số on/off theo yêu cầu của bạn
    actions_map["Muscle"] = {"func": muscle_control, "params": "state=on|off", "example": "Muscle(off)"}
    
    print("-> [HỆ THỐNG] Đã đăng ký tính năng: Cánh tay Servo")