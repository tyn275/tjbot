# features/cam_feature.py
import os
import subprocess
import threading
import time

# --- BIẾN TOÀN CỤC LƯU TRẠNG THÁI ---
# Mặc định cấu hình các luồng theo yêu cầu hệ thống
rtsp_push_url = "rtsp://media.toolhub.app/tjbot1/eye"
hls_pull_url = "https://media.toolhub.app/tjbot1/video.m3u8"

# Biến lưu trữ tiến trình con hệ thống (FFmpeg)
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
# 3. TIẾN TRÌNH CHẠY NGẦM BẬT PHẦN CỨNG VÀ ĐẨY LUỒNG (FFMPEG WORKER)
# -----------------------------------------------------------------
def _ffmpeg_stream_worker(resolution):
    global camera_process, is_camera_streaming, rtsp_push_url
    
    # Tách chuỗi độ phân giải (Ví dụ: "640x480" -> ["640", "480"])
    try:
        width, height = resolution.split('x')
    except Exception:
        width, height = "640", "480" # Giá trị mặc định an toàn

    print(f"🎥 [FFMPEG_LIVE]: Khởi tạo phần cứng Camera với độ phân giải {width}x{height}...")

    # Cấu hình chuỗi lệnh FFmpeg tối ưu riêng cho Raspberry Pi:
    # - v4l2: Driver camera tiêu chuẩn của Linux trên Pi.
    # - h264_v4l2m2m: Trình biên dịch mã hóa H.264 bằng CHIP PHẦN CỨNG (Hardware Acceleration) của Pi giúp không bị treo CPU.
    # - rtsp_transport tcp: Ép đẩy luồng qua giao thức TCP để bảo toàn khung hình không bị vỡ/giật.
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "v4l2",
        "-video_size", f"{width}x{height}",
        "-framerate", "20",
        "-i", "/dev/video0", # Đường dẫn phần cứng camera mặc định trên Pi
        "-vcodec", "h264_v4l2m2m", # Mã hóa cứng cực nhẹ
        "-pix_fmt", "yuv420p",
        "-b:v", "800k", # Băng thông tối ưu, truyền qua Internet mượt mà
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        rtsp_push_url
    ]

    try:
        # Chạy tiến trình ngầm, ẩn hoàn toàn output rác của ffmpeg ra màn hình nền
        camera_process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            universal_newlines=True
        )
        
        is_camera_streaming = True
        print(f"🚀 [FFMPEG_LIVE]: Luồng video đang được đẩy liên tục lên máy chủ: {rtsp_push_url}")
        
        # Vòng lặp giám sát xem ffmpeg có bị sập hay tắt giữa chừng không
        while is_camera_streaming and camera_process.poll() is None:
            time.sleep(0.5)
            
    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng khi thực thi FFmpeg: {e}")
    finally:
        _stop_ffmpeg_process()

def _stop_ffmpeg_process():
    global camera_process, is_camera_streaming
    is_camera_streaming = False
    if camera_process:
        try:
            print("🛑 [FFMPEG_LIVE]: Đang giải phóng phần cứng và ngắt luồng Camera...")
            camera_process.terminate() # Ra lệnh tắt an toàn
            camera_process.wait(timeout=2) # Chờ tối đa 2 giây để tiến trình đóng hẳn
        except Exception:
            try:
                camera_process.kill() # Ép buộc diệt nếu tiến trình cứng đầu
            except Exception:
                pass
        camera_process = None
    print("🔒 [FFMPEG_LIVE]: Đã tắt Camera phần cứng thành công.")

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
        
        # Khởi chạy một Thread ngầm để chạy lệnh FFmpeg, tránh làm đóng băng luồng nhận MQTT mẹ
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
        "example": 'SetStreamingServer("rtsp://media.toolhub.app/tjbot1/eye")'
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
    print("=> Mô-đun CAM_FEATURE đã đăng ký thành công danh sách lệnh! 👁️")