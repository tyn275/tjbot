# selftest.py
import sys
import time

# 📦 Import các tính năng cần được kiểm tra
from features import led_feature
from features import arm_feature

def run_selftest():
    """Hàm tổng quản lý, lần lượt kích hoạt selftest của các tính năng"""
    print("=" * 50)
    print("🤖 [TJBOT SYSTEM] KHỞI ĐỘNG CHƯƠNG TRÌNH KIỂM THỬ PHẦN CỨNG")
    print("=" * 50)
    time.sleep(0.5)

    # Danh sách các mô-đun tính năng đăng ký tham gia kiểm tra
    features_to_test = {
        "Hệ thống Đèn LED": led_feature,
        "Cơ cấu Cánh tay & Servo": arm_feature
    }

    results = {}
    
    # Duyệt qua từng mô-đun và kích hoạt hàm selftest mặc định của tụi nó
    for name, module in features_to_test.items():
        try:
            # Kiểm tra xem mô-đun có viết sẵn hàm selftest đúng quy chuẩn không
            if hasattr(module, 'selftest') and callable(getattr(module, 'selftest')):
                # Gọi hàm selftest và lấy kết quả True/False trả về
                success = module.selftest()
                results[name] = "PASSED ✅" if success else "FAILED ❌"
            else:
                print(f"\n🚨 CẢNH BÁO: Mô-đun '{name}' chưa định nghĩa hàm selftest()!")
                results[name] = "SKIPPED ⚠️ (Thiếu hàm test)"
        except Exception as e:
            print(f"\n🚨 LỖI NGHIÊM TRỌNG khi gọi test mô-đun '{name}': {e}")
            results[name] = "CRASHED 🔥"
            
        time.sleep(0.5)

    # -----------------------------------------------------------------
    # IN BẢNG THỐNG KÊ KẾT QUẢ CUỐI CÙNG
    # -----------------------------------------------------------------
    print("\n" + "=" * 50)
    print("📊 BẢNG TỔNG HỢP KẾT QUẢ KIỂM TRA (SELFTEST REPORT)")
    print("=" * 50)
    
    all_passed = True
    for name, status in results.items():
        print(f" ▪️ {name.ljust(25)} : {status}")
        if "FAILED" in status or "CRASHED" in status:
            all_passed = False
            
    print("=" * 50)
    
    if all_passed:
        print("🎉 KẾT LUẬN: Mọi phần cứng đã SẴN SÀNG! Robot hoạt động tốt.")
        sys.exit(0) # Trả về mã 0 (Thành công vẹn toàn)
    else:
        print("🚨 KẾT LUẬN: Phát hiện lỗi phần cứng! Vui lòng kiểm tra lại log phía trên.")
        sys.exit(1) # Trả về mã 1 (Có lỗi xảy ra)

if __name__ == "__main__":
    run_selftest()