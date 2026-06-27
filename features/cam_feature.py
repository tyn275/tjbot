# features/cam_feature.py
import os
import subprocess
import threading
import time

# --- BIẾN TOÀN CỤC LƯU TRẠNG THÁI ---
# Mặc định cấu hình các luồng theo yêu cầu hệ thống
rtsp_push_url = "rtsp://TRAIN.toolhub.app:8554/live/tjbot1/eye"
hls_pull_url = "https://train.toolhub.app/hls/cctv_9fb7ad3e-b8fc-431b-bff9-9a8760a8c845/index.m3u8"
device_id = "tjbot1" # Thêm tham số định danh thiết bị mặc định

# Biến lưu trữ tiến trình con hệ thống (Tiến trình Pipe)
camera_process = None
is_camera_streaming = False

# -----------------------------------------------------------------
# 1. HÀM CẤU HÌNH ĐỊA CHỈ SERVER ĐẨY LUỒNG RTSP (TỪ PI LÊN SERVER)
# -----------------------------------------------------------------
def set_streaming_server(url_text):
    """
    Xử lý lệnh: SetStreamingServer("rtsp://...") từ Website
    """
    global rtsp_push_url
    clean_url = url_text.strip().replace('"', '').replace("'", "")
    if not clean_url:
        return "❌ Lỗi: Địa chỉ RTSP đẩy luồng không được để trống!"
        
    rtsp_push_url = clean_url
    print(f"📡 [CAMERA_CONFIG]: Đã cập nhật RTSP Push URL -> {rtsp_push_url}")
    return f"Đã lưu RTSP Server: {rtsp_push_url}"

# -----------------------------------------------------------------
# 2. HÀM CẤU HÌNH LUỒNG VIDEOSTREAM (TỪ SERVER VỀ WEBSITE PLAYER)
# -----------------------------------------------------------------
def set_video_stream(url_text):
    """
    Xử lý lệnh: SetVideoStream("https://...") từ Website
    """
    global hls_pull_url
    clean_url = url_text.strip().replace('"', '').replace("'", "")
    if not clean_url:
        return "❌ Lỗi: Địa chỉ HLS kéo luồng không được để trống!"
        
    hls_pull_url = clean_url
    print(f"📺 [CAMERA_CONFIG]: Đã cập nhật HLS Pull URL -> {hls_pull_url}")
    return f"Đã đồng bộ VideoStream Player: {hls_pull_url}"

# -----------------------------------------------------------------
# 3. HÀM KIỂM TRA TRẠNG THÁI CAMERA (MỚI BỔ SUNG)
# -----------------------------------------------------------------
def check_camera_status():
    """
    Xử lý lệnh: CheckCamera() từ Website để kiểm tra trạng thái
    """
    global is_camera_streaming, camera_process
    
    # Kiểm tra thực tế bằng cả biến trạng thái và tiến trình Linux ngầm
    if is_camera_streaming and camera_process and camera_process.poll() is None:
        return f"cam=on"   # 🟢 [ONLINE]
    else:
        return f"cam=off"  # 🔴 [OFFLINE]

# -----------------------------------------------------------------
# 4. TIẾN TRÌNH CHẠY NGẦM BẬT PHẦN CỨNG VÀ ĐẨY LUỒNG (RPICAM + FFMPEG WORKER)
# -----------------------------------------------------------------
def _ffmpeg_stream_worker(resolution):
    global camera_process, is_camera_streaming, rtsp_push_url, device_id
    
    try:
        width, height = resolution.split('x')
    except Exception:
        width, height = "640", "480"
    
    fps = "25"
    print(f"🎥 [FFMPEG_LIVE]: Thiết bị '{device_id}' triệu gọi cam_streaming.sh [{width}x{height}] phát tới {rtsp_push_url}...")

    script_path = "./features/cam_streaming.sh" 
    
    # Truyền thêm biến device_id làm tham số thứ 5 cho script .sh
    cmd = [script_path, rtsp_push_url, width, height, fps, device_id]

    try:
        # Hướng stderr vào stdout để gộp chung làm 1 luồng log duy nhất
        camera_process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        is_camera_streaming = True
        print(f"🚀 [FFMPEG_LIVE]: Tiến trình script .sh đã kích hoạt. Đang đọc log...")
        
        # Vòng lặp đọc log thời gian thực (Real-time stdout reader)
        # Vòng lặp này sẽ chặn tại đây và in liên tục cho đến khi script .sh dừng hẳn
        for line in camera_process.stdout:
            if line:
                print(f"📝 [SH_LOG]: {line.strip()}")
            if not is_camera_streaming:
                break
                
        # Khi thoát khỏi vòng lặp trên nghĩa là tiến trình .sh đã kết thúc
        poll_status = camera_process.poll()
        print(f"❌ [FFMPEG_LIVE]: Script .sh đã dừng với mã thoát (Exit Code): {poll_status}")
            
    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng khi chạy file script: {e}")
    finally:
        _stop_ffmpeg_process()
        
def _stop_ffmpeg_process():
    global camera_process, is_camera_streaming
    is_camera_streaming = False
    
    if camera_process:
        try:
            print("🛑 [FFMPEG_LIVE]: Đang gửi tín hiệu ngắt script .sh và giải phóng Camera...")
            
            # 1. Gửi tín hiệu terminate đến tiến trình cha (file .sh)
            camera_process.terminate() 
            
            # 2. Ép buộc dọn dẹp tận gốc rpicam-vid và ffmpeg do file .sh sinh ra
            # Việc này đảm bảo đèn LED trên camera tắt và giải phóng phần cứng ngay lập tức
            os.system("pkill -f rpicam-vid")
            os.system("pkill -f ffmpeg")
            
            # 3. Chờ tiến trình gốc đóng hẳn
            camera_process.wait(timeout=1)
        except Exception as e:
            print(f"⚠️ Có lỗi nhỏ khi giải phóng tiến trình: {e}")
            # Nếu vẫn cứng đầu, ép diệt hoàn toàn
            try:
                camera_process.kill()
            except Exception:
                pass
        camera_process = None
        
    print("🔒 [FFMPEG_LIVE]: Đã đóng toàn bộ tiến trình liên quan đến Camera.")

# -----------------------------------------------------------------
# 4. HÀM ĐIỀU PHỐI TỔNG CHẠY CAMERA (ON/OFF)
# -----------------------------------------------------------------
def camera_control(state, resolution="640x480"):
    """
    Xử lý lệnh: Camera("on", "640x480") hoặc Camera("off") từ Web hạ xuống
    """
    global is_camera_streaming
    state = state.strip().lower().replace('"', '').replace("'", "")
    res_clean = resolution.strip().replace('"', '').replace("'", "")

    if state == "on":
        if is_camera_streaming:
            return "Thông báo: Hệ thống Camera Mắt thần đang hoạt động sẵn rồi."
        
        # Khởi chạy một Thread ngầm để chạy lệnh, tránh làm đóng băng luồng nhận MQTT mẹ
        t = threading.Thread(target=_ffmpeg_stream_worker, args=(res_clean,))
        t.daemon = True
        t.start()
        return f"Kích hoạt Camera thành công ({res_clean}) -> Đang phát Live!"
    else:
        if not is_camera_streaming:
            return "Thông báo: Hệ thống Camera hiện đang ở trạng thái nghỉ (Offline)."
        
        _stop_ffmpeg_process()
        return "Ngắt luồng phát Livestream Camera thành công."

# -----------------------------------------------------------------
# ĐĂNG KÝ HÀM VÀO LÕI ĐIỀU KHIỂN CHÍNH
# -----------------------------------------------------------------
def register(actions_map):
    """ Đăng ký tự động các cấu trúc hàm vào hệ thống ánh xạ của tjbot_client.py """
    actions_map["SetStreamingServer"] = {
        "func": set_streaming_server,
        "params": "text",
        "example": 'SetStreamingServer("rtsp://TRAIN.toolhub.app:8554/live/tjbot1/eye")'
    }
       
    actions_map["SetVideoStream"] = {
        "func": set_video_stream,
        "params": "text",
        "example": 'SetVideoStream("https://media.toolhub.app/tjbot1/video.m3u8")'
    }

    actions_map["Camera"] = {
        "func": camera_control,
        "params": "state, resolution='640x480'",
        "example": 'Camera("on", "640x480")'
    }
    
    # BỔ SUNG: Đăng ký hàm kiểm tra trạng thái camera lên Web điều khiển
    actions_map["CheckCamera"] = {
        "func": check_camera_status,
        "params": "",
        "example": 'CheckCamera()'
    }
    print("=> Mô-đun CAM_FEATURE đã đăng ký thành công danh sách lệnh! 👁️")