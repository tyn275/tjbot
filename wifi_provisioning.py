# wifi_provisioning.py
import time
import os
import subprocess
import re
import serial

# --- CẤU HÌNH CỔNG BLUETOOTH VIRTUAL SERIAL ---
# Mặc định RFCOMM0 là cổng Serial ảo được ánh xạ từ kết nối Bluetooth SPP
BLUETOOTH_PORT = "/dev/rfcomm0"
BAUDRATE = 115200

def init_bluetooth_serial():
    """Khởi tạo cổng Serial ảo. Nếu chưa có, tự gọi hệ thống lắng nghe kết nối."""
    if not os.path.exists(BLUETOOTH_PORT):
        print(f"⚠️ [BLUETOOTH]: Không tìm thấy {BLUETOOTH_PORT}. Đang phát lệnh lắng nghe kết nối từ thiết bị ngoài...")
        try:
            # Ép hệ thống mở cổng chờ kết nối từ thiết bị. 
            # Khi có thiết bị kết nối vào, lệnh này mới chạy xong và tạo ra file /dev/rfcomm0
            cmd = f"sudo rfcomm listen {BLUETOOTH_PORT} 1"            
            subprocess.run(cmd, shell=True, timeout=30)
        except subprocess.TimeoutExpired:
            # Nếu quá 30 giây không ai thèm kết nối, thoát ra để vòng lặp chính thử lại chu kỳ sau
            return None
        except Exception as e:
            print(f"❌ Lỗi khởi tạo lệnh rfcomm: {e}")
            return None

    try:
        # Khi file /dev/rfcomm0 đã xuất hiện, tiến hành kết nối Serial tốc độ cao
        ser = serial.Serial(BLUETOOTH_PORT, BAUDRATE, timeout=1)
        print("✅ [BLUETOOTH]: Cổng Serial ảo đã thông suốt ở tốc độ {BAUDRATE}!")
        return ser
    except Exception as e:
        print(f"❌ [LỖI SERIAL]: Không thể mở cổng: {e}")
        return None

# --- XỬ LÝ 4 LỆNH HỆ THỐNG GIAO TIẾP VỚI NGƯỜI DÙNG ---

def run_wifi_scan():
    """Lệnh 1: Quét các mạng Wifi xung quanh bằng nmcli"""
    print("🔍 [HỆ THỐNG]: Đang quét Wifi...")
    try:
        # Gọi lệnh hệ thống trả về định dạng rút gọn (SSID, Tín hiệu)
        cmd = "nmcli -t -f SSID,SIGNAL device wifi list"
        output = subprocess.check_output(cmd, shell=True, text=True)
        
        # Lọc bỏ các SSID trống (mạng ẩn) và trùng lặp
        lines = output.strip().split("\n")
        seen_ssids = set()
        result_lines = []
        
        for line in lines:
            if "," in line:
                ssid, signal = line.split(",", 1)
                ssid = ssid.strip()
                if ssid and ssid not in seen_ssids:
                    seen_ssids.add(ssid)
                    result_lines.append(f"- {ssid} ({signal}%)")
        
        if not result_lines:
            return "No WiFi network found.\r\n"
            
        return "--- AVAILABLE WIFI NETWORKS ---\r\n" + "\r\n".join(result_lines) + "\r\n-------------------------------\r\n"
    except Exception as e:
        return f"ERROR_SCAN: Không thể quét Wifi ({e})\r\n"

def run_add_wifi(ssid, password):
    """Lệnh 2: Thêm cấu hình Wifi mới và ép kết nối lập tức"""
    print(f"💾 [HỆ THỐNG]: Đang tiến hành kết nối tới Wifi: {ssid}")
    try:
        # Gọi lệnh nmcli để kết nối
        cmd = f'nmcli device wifi connect "{ssid}" password "{password}"'
        # Thiết lập timeout 15 giây để tránh bị treo nếu sai mật khẩu quá lâu
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=15)
        
        if result.returncode == 0:
            return f"CONNECTED_SUCCESS: Đã kết nối và lưu cấu hình mạng [{ssid}].\r\n"
        else:
            return f"AUTH_FAILED: Thất bại! Vui lòng kiểm tra lại mật khẩu hoặc tín hiệu mạng.\r\nLog: {result.stderr.strip()}\r\n"
    except subprocess.TimeoutExpired:
        return "TIMEOUT: Quá thời gian kết nối (15s). Vui lòng thử lại.\r\n"
    except Exception as e:
        return f"ERROR_ADD: Lỗi xử lý hệ thống ({e})\r\n"

def run_list_wifi():
    """Lệnh 3: Liệt kê danh sách các Wifi và mật khẩu (psk) đang lưu trong Pi"""
    print("📋 [HỆ THỐNG]: Đang lấy danh sách Wifi đã lưu...")
    try:
        # Lấy danh sách tất cả các cấu hình Wifi đã từng lưu
        cmd_list = "nmcli -t -f NAME,TYPE connection show"
        output = subprocess.check_output(cmd_list, shell=True, text=True)
        
        saved_wifis = []
        for line in output.strip().split("\n"):
            if ":802-11-wireless" in line: # Chỉ lọc ra các kết nối dạng Wifi
                name = line.split(":")[0]
                saved_wifis.append(name)
                
        if not saved_wifis:
            return "No saved WiFi profiles found.\r\n"
            
        result_lines = ["--- SAVED WIFI PROFILES ---"]
        # Duyệt qua từng Wifi để bóc tách mật khẩu psk trong file hệ thống
        for wifi in saved_wifis:
            password = "Unknown"
            try:
                # Đọc cấu hình bảo mật để lấy mật khẩu dạng clear-text
                cmd_pass = f"sudo nmcli -s -g 802-11-wireless-security.psk connection show '{wifi}'"
                pass_out = subprocess.check_output(cmd_pass, shell=True, text=True).strip()
                if pass_out:
                    password = pass_out
            except Exception:
                pass # Nếu Wifi không có mật khẩu (mạng mở)
                
            result_lines.append(f"SSID: {wifi} | PASS: {password}")
            
        result_lines.append("---------------------------")
        return "\r\n".join(result_lines) + "\r\n"
    except Exception as e:
        return f"ERROR_LIST: Không thể lấy danh sách ({e})\r\n"

def run_del_wifi(ssid):
    """Lệnh 4: Xóa một profile Wifi đã lưu"""
    print(f"🗑️ [HỆ THỐNG]: Đang yêu cầu xóa Wifi: {ssid}")
    try:
        cmd = f'sudo nmcli connection delete "{ssid}"'
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        
        if result.returncode == 0:
            return f"DELETED_SUCCESS: Đã xóa hoàn toàn mạng [{ssid}] khỏi bộ nhớ TJBot.\r\n"
        else:
            return f"NOT_FOUND: Không tìm thấy mạng có tên [{ssid}] để xóa.\r\n"
    except Exception as e:
        return f"ERROR_DEL: Lỗi xóa cấu hình ({e})\r\n"

# --- VÒNG LẶP XỬ LÝ LUỒNG DỮ LIỆU SERIAL (MAIN ENGINE) ---

def process_command(raw_command):
    """Hàm bóc tách cú pháp regex để thực thi lệnh tương ứng"""
    cmd = raw_command.strip()
    if not cmd:
        return ""
        
    # 1. Khớp lệnh wifiscan()
    if cmd == "wifiscan()":
        return run_wifi_scan()
        
    # 2. Khớp lệnh listwifi()
    elif cmd == "listwifi()":
        return run_list_wifi()
        
    # 3. Khớp lệnh addwifi(ssid,matkhauday)
    add_match = re.match(r"^addwifi\((.+?),\s*(.+?)\)$", cmd)
    if add_match:
        ssid = add_match.group(1).strip()
        password = add_match.group(2).strip()
        return run_add_wifi(ssid, password)
        
    # 4. Khớp lệnh delwifi(ssid)
    del_match = re.match(r"^delwifi\((.+?)\)$", cmd)
    if del_match:
        ssid = del_match.group(1).strip()
        return run_del_wifi(ssid)
        
    # Trường hợp nhập sai cú pháp lệnh
    return f"UNKNOWN_COMMAND: Cú pháp '{cmd}' không hợp lệ.\r\nCó sẵn: wifiscan(), addwifi(ssid,pass), listwifi(), delwifi(ssid)\r\n"

def main():
    print("🚀 [PROVISIONING ENGINE] Tiến trình giao tiếp điều khiển qua Bluetooth bắt đầu chạy...")
    
    while True:
        ser = init_bluetooth_serial()
        if ser is None:
            # Nếu cổng Serial ảo chưa được tạo (chưa có kết nối BT), ngủ 5 giây rồi thử lại
            time.sleep(5)
            continue
            
        try:
            buffer = ""
            while True:
                if ser.in_waiting > 0:
                    # Đọc dữ liệu thô gửi đến, giải mã UTF-8
                    raw_data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += raw_data
                    
                    # Kiểm tra xem người dùng đã gõ hết dòng lệnh chưa (ấn nút Enter / gửi ký tự xuống dòng)
                    if "\n" in buffer or "\r" in buffer:
                        # Tách dòng lệnh đầu tiên ra xử lý
                        lines = buffer.splitlines()
                        if lines:
                            command = lines[0]
                            # Thực thi lệnh và lấy chuỗi phản hồi kết quả
                            response = process_command(command)
                            
                            # Gửi trả ngược dữ liệu kết quả về cho trang web hiển thị
                            if response:
                                ser.write(response.encode('utf-8'))
                                
                        # Xóa lệnh vừa xử lý khỏi buffer, giữ lại dữ liệu dang dở nếu có
                        buffer = buffer[buffer.find("\n")+1:] if "\n" in buffer else ""
                time.sleep(0.1)
                
        except (serial.SerialException, OSError):
            print("🔌 [BLUETOOTH]: Thiết bị điều khiển đã ngắt kết nối (Disconnect). Quay lại chế độ chờ...")
        except Exception as e:
            print(f"⚠️ [LỖI HỆ THỐNG TRONG VÒNG LẶP]: {e}")
        finally:
            if ser and ser.is_open:
                ser.close()

if __name__ == "__main__":
    main()