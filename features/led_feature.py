# features/led_feature.py

def led_control(state, color="white"):
    print(f"-> [TÍNH NĂNG LED] Thực thi led_control: State={state}, Color={color}")
    return f"LED changed to {state} ({color})"

def led_rainbow(speed="fast"):
    print(f"-> [TÍNH NĂNG LED] Thực thi led_rainbow với tốc độ: {speed}")
    return f"Rainbow effect started at {speed} speed"

def register(actions_map):
    # Đăng ký hàm led_control
    actions_map["led_control"] = {
        "func": led_control,
        "params": "state, color='white'",
        "example": "led_control(on, red)"
    }
    
    # Đăng ký hàm led_rainbow
    actions_map["led_rainbow"] = {
        "func": led_rainbow,
        "params": "speed='fast'",
        "example": "led_rainbow(slow)"
    }
    print("-> [HỆ THỐNG] Đã đăng ký các hàm từ tính năng: LED")