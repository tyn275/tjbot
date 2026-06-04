# features/arm_feature.py

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