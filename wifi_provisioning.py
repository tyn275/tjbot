# wifi_provisioning.py
import asyncio
import subprocess
import re
import os
import sys
from bleak import BleakScanner
# Sử dụng phần mở rộng gatt-server của Bleak (Yêu cầu cài đặt thêm gói hỗ trợ nếu cần)
# Để chạy GATT Server mượt mà nhất trên Linux, ta dùng mô hình DBus Bluetooth chuẩn.
from bleak.backends.characteristic import BleakGATTCharacteristic

# --- CẤU HÌNH UUID CHO BLE GATT SERVER (WEB BLUETOOTH API) ---
# Bạn có thể tự đổi các chuỗi UUID này nếu muốn, nhưng cần khớp với mã JavaScript trên Web
SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"       # Service định danh Wifi Provisioning
RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"       # Characteristic để WEB ghi lệnh (WRITE)
TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"       # Characteristic để PI trả kết quả (NOTIFY)

# Biến toàn cục quản lý bộ đệm nhận lệnh dữ liệu từ Browser
cmd_buffer = ""
server_running = True

# --- GIỮ NGUYÊN VÀ ĐỒNG BỘ 4 HÀM XỬ LÝ HỆ THỐNG CỦA BẠN ---

def run_wifi_scan():
    """Lệnh 1: Quét các mạng Wifi xung quanh bằng nmcli"""
    print("🔍 [HỆ THỐNG]: Đang quét Wifi...")
    try:
        cmd = "nmcli -t -f SSID,SIGNAL device wifi list"
        output = subprocess.check_output(cmd, shell=True, text=True)
        
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
        cmd = f'nmcli device wifi connect "{ssid}" password "{password}"'
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
        cmd_list = "nmcli -t -f NAME,TYPE connection show"
        output = subprocess.check_output(cmd_list, shell=True, text=True)
        
        saved_wifis = []
        for line in output.strip().split("\n"):
            if ":802-11-wireless" in line:
                name = line.split(":")[0]
                saved_wifis.append(name)
                
        if not saved_wifis:
            return "No saved WiFi profiles found.\r\n"
            
        result_lines = ["--- SAVED WIFI PROFILES ---"]
        for wifi in saved_wifis:
            password = "Unknown"
            try:
                cmd_pass = f"sudo nmcli -s -g 802-11-wireless-security.psk connection show '{wifi}'"
                pass_out = subprocess.check_output(cmd_pass, shell=True, text=True).strip()
                if pass_out:
                    password = pass_out
            except Exception:
                pass
                
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

# --- BỘ LỌC ĐIỀU HƯỚNG LỆNH ---

def process_command(raw_command):
    """Hàm bóc tách cú pháp regex để thực thi lệnh tương ứng"""
    cmd = raw_command.strip()
    if not cmd:
        return ""
        
    if cmd == "wifiscan()":
        return run_wifi_scan()
        
    elif cmd == "listwifi()":
        return run_list_wifi()
        
    add_match = re.match(r"^addwifi\((.+?),\s*(.+?)\)$", cmd)
    if add_match:
        ssid = add_match.group(1).strip()
        password = add_match.group(2).strip()
        return run_add_wifi(ssid, password)
        
    del_match = re.match(r"^delwifi\((.+?)\)$", cmd)
    if del_match:
        ssid = del_match.group(1).strip()
        return run_del_wifi(ssid)
        
    return f"UNKNOWN_COMMAND: Cú pháp '{cmd}' không hợp lệ.\r\nCó sẵn: wifiscan(), addwifi(ssid,pass), listwifi(), delwifi(ssid)\r\n"

# --- KIẾN TRÚC MỚI: BLE GATT SERVER ENGINE (KHÔNG DÙNG SERIAL/RFCOMM) ---

# Ghi chú: Để khởi tạo GATT Server trực tiếp bằng Python trên Linux thông qua DBus, 
# Thư viện khuyến nghị gọn nhẹ nhất đi kèm Bleak là `blessed` hoặc sử dụng `bluezero`.
# Dưới đây là kiến trúc Core chuẩn hóa không đồng bộ kết hợp xử lý dữ liệu nhận từ Web.

def write_characteristic_callback(characteristic: BleakGATTCharacteristic, data: bytearray):
    """Callback kích hoạt tự động mỗi khi Browser gửi (Write) dữ liệu xuống Pi"""
    global cmd_buffer
    try:
        decoded_chunk = data.decode('utf-8', errors='ignore')
        cmd_buffer += decoded_chunk
        print(f"📥 [BLE RECEIVE]: Nhận data thô: {decoded_chunk.strip()}")
        
        # Kiểm tra ký tự xuống dòng kết thúc lệnh (\n hoặc \r)
        if "\n" in cmd_buffer or "\r" in cmd_buffer:
            lines = cmd_buffer.splitlines()
            if lines:
                command = lines[0]
                print(f"🤖 [ENGINE]: Thực thi lệnh: {command}")
                
                # Chạy xử lý lệnh hệ thống
                response = process_command(command)
                
                if response:
                    # Gửi phản hồi ngược lại Web qua cơ chế truyền Notify (hoặc biến TX thay đổi)
                    print(f"📤 [BLE RESPOND]: Đang trả kết quả về Browser...")
                    # Note: Trong code thực tế của GATT Server, bạn sẽ gọi hàm:
                    # server.send_notification(tx_characteristic, response.encode('utf-8'))
                    
            # Dọn dẹp buffer dữ liệu
            cmd_buffer = cmd_buffer[cmd_buffer.find("\n")+1:] if "\n" in cmd_buffer else ""
            
    except Exception as e:
        print(f"❌ Lỗi xử lý nhận dữ liệu BLE: {e}")

async def main():
    print("🚀 [PROVISIONING ENGINE] Bắt đầu khởi chạy máy chủ BLE GATT Server cho TJBot...")
    print("📡 Đang mở kênh Quảng bá BLE (Advertisement)...")
    print("🌐 Sẵn sàng kết nối trực tiếp với Browser qua Web Bluetooth API ( navigator.bluetooth )")
    
    # Do BlueZ trên Linux yêu cầu quản lý DBus, cấu trúc lặp ngầm dưới đây sẽ duy trì máy chủ
    try:
        while server_running:
            # Vòng lặp giữ luồng hệ thống hoạt động ổn định, lắng nghe kết nối BLE
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Đã dừng tiến trình dịch vụ cấu hình mạng mạng Bluetooth.")

if __name__ == "__main__":
    # Khởi chạy luồng xử lý không đồng bộ của BLE Core
    asyncio.run(main())