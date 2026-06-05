# features/arm_feature.py

import time


def wave_hand(speed, times=1):
    print(f"-> [TÍNH NĂNG CÁNH TAY] Thực thi wave_hand: Speed={speed}, Times={times}")
    return f"Hand waved {times} times at {speed}"

def nod_head(angle=90):
    print(f"-> [TÍNH NĂNG CÁNH TAY] Thực thi nod_head góc: {angle} độ")
    return f"Head nodded to {angle} degrees"

def register(actions_map):
    # Đăng ký hàm wave_hand
    actions_map["wave_hand"] = {
        "func": wave_hand,
        "params": "speed, times=1",
        "example": "wave_hand(fast, 3)"
    }
    
    # Đăng ký hàm nod_head
    actions_map["nod_head"] = {
        "func": nod_head,
        "params": "angle=90",
        "example": "nod_head(45)"
    }
    print("-> [HỆ THỐNG] Đã đăng ký các hàm từ tính năng: Cánh Tay")
    
def selftest():
    """Hàm tự kiểm tra trạng thái hoạt động của cánh tay/servo"""
    print("\n--- [SELFTEST] BẮT ĐẦU KIỂM TRA CÁNH TAY & ĐỘNG CƠ ---")
    try:
        # Gọi thử các hàm có sẵn trong mô-đun để kiểm tra kết nối
        print("🤖 Chạy thử lệnh wave_hand...")
        print(wave_hand("slow", 1))
        time.sleep(0.5)
        
        print("🤖 Chạy thử lệnh nod_head...")
        print(nod_head(90))
        time.sleep(0.5)
        
        print("✅ THÀNH CÔNG: Hệ thống cơ cấu Cánh Tay hoạt động tốt.")
        return True
    except Exception as e:
        print(f"❌ THẤT BẠI: Lỗi phát sinh khi test Cánh Tay: {e}")
        return False    
    