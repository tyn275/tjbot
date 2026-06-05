# features/arm_feature.py
import time
from gpiozero import AngularServo

try:
    # Nới rộng xung ra góc cực đại: 0.45ms (0.00045) đến 2.45ms (0.00245)
    servo = AngularServo(
        7, 
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
def wave_hand(speed="fast", times=3):
    """Hàm điều khiển robot vẫy tay qua lại"""
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
        return f"SUCCESS: Đã vẫy tay {times} lần."
    except ValueError:
        return "ERROR: Tham số 'times' phải là số nguyên!"

def set_arm_angle(angle=0):
    """Hàm quay cánh tay đến một góc cụ thể (Từ -90 đến 90 độ)"""
    print(f"-> [TÍNH NĂNG CÁNH TAY] set_arm_angle: Góc {angle} độ")
    if not servo:
        return "ERROR: Servo chưa được khởi tạo!"

    try:
        angle = float(angle)
        if -90 <= angle <= 90:
            servo.angle = angle
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
    print("\n--- [SELFTEST] BẮT ĐẦU KIỂM TRA MÔ-ĐUN SERVO CÁNH TAY ---")
    if not servo:
        print("❌ THẤT BẠI: Thiết bị Servo chưa sẵn sàng.")
        return False

    try:
        # 1. Cho về giữa (Góc thực tế 90 -> Code: 0)
        print("🤖 Step 1: Cho cánh tay về CHÍNH GIỮA (90 độ)")
        servo.angle = 0
        time.sleep(0.7) # Nghỉ giữa thao tác

        # 2. Cho về góc 0 (Góc thực tế 0 -> Code: -90)
        print("🤖 Step 2: Quay nhanh về góc 0 độ")
        servo.angle = -90
        time.sleep(0.7) # Nghỉ giữa thao tác

        # 3. Cho về góc 180 (Góc thực tế 180 -> Code: 90)
        print("🤖 Step 3: Quay nhanh về góc 180 độ")
        servo.angle = 90
        time.sleep(0.7) # Nghỉ giữa thao tác

        # 4. Chuyển động từ từ từ 180 về 0 trong khoảng 2 giây
        # (Từ Code: 90 về Code: -90, tổng quãng đường là 180 độ)
        print("🤖 Step 4: Chuyển động TỪ TỪ từ 180 độ về 0 độ (trong 2 giây)...")
        
        start_angle = 90
        end_angle = -90
        steps = 50      # Chia nhỏ hành trình thành nhiều bước để chuyển động mượt
        delay_per_step = 0.02 # Khoảng 0.05 giây mỗi bước nhỏ
        angle_per_step = (end_angle - start_angle) / steps
        
        current_angle = start_angle
        for _ in range(steps):
            current_angle += angle_per_step
            servo.angle = current_angle
            time.sleep(delay_per_step)
            
        time.sleep(0.7) # Nghỉ giữa thao tác

        # 5. Chuyển về 90 (Góc thực tế 90 -> Code: 0)
        print("🤖 Step 5: Quay trở lại vị trí CHÍNH GIỮA (90 độ)")
        servo.angle = 0

        print("✅ THÀNH CÔNG: Servo hoàn thành kịch bản quét góc và chuyển động mượt 2s.")
        return True

    except Exception as e:
        print(f"❌ THẤT BẠI: Lỗi phát sinh trong kịch bản quét Servo: {e}")
        return False

# Đăng ký hàm với hệ thống MQTT
def register(actions_map):
    actions_map["wave_hand"] = {"func": wave_hand, "params": "speed='fast', times=3", "example": "wave_hand(slow, 5)"}
    actions_map["set_arm"] = {"func": set_arm_angle, "params": "angle=0", "example": "set_arm(45)"}
    print("-> [HỆ THỐNG] Đã đăng ký tính năng: Cánh tay Servo")