#!/bin/bash

# Hứng các tham số truyền vào theo thứ tự (Nếu không có, tự động lấy giá trị mặc định)
RTSP_URL="${1:-rtsp://TRAIN.toolhub.app:8554/live/tjbot1/eye}"
WIDTH="${2:-640}"
HEIGHT="${3:-480}"
FPS="${4:-25}"
DEVICE_ID="${5:-tjbot1}"

echo "🔄 [SCRIPT SH]: Thiết bị $DEVICE_ID đang chạy Stream với: URL=$RTSP_URL, RES=${WIDTH}x${HEIGHT}, FPS=$FPS"

if [ 0 == 1 ]
then
    # Thực hiện lệnh pipe với log nhiều
    rpicam-vid -t 0 --inline --width $WIDTH --height $HEIGHT --framerate $FPS --intra $FPS -o - | \
    ffmpeg -y -probesize 15M -analyzeduration 2000000 -f h264 -i - \
    -c:v copy -an -flush_packets 1 -f rtsp -rtsp_transport tcp "$RTSP_URL"
else
    # Thực hiện lệnh pipe không log
    rpicam-vid -t 0 --inline --width $WIDTH --height $HEIGHT --framerate $FPS --intra $FPS -o - 2>/dev/null | \
    ffmpeg -y -loglevel warning -probesize 15M -analyzeduration 2000000 -f h264 -i - \
    -c:v copy -an -flush_packets 1 -f rtsp -rtsp_transport tcp "$RTSP_URL"
fi    