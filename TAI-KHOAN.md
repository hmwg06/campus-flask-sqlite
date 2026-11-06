# Tài khoản và dữ liệu trình diễn LMS

Bộ dữ liệu chứa 24 sinh viên, 3 giảng viên, 1 cán bộ và 1 quản trị viên.

| Vai trò | Tên đăng nhập |
|---|---|
| Sinh viên | 11240001 đến 11240024 |
| Giảng viên | giangvien01, giangvien02, giangvien03 |
| Cán bộ | canbo01 |
| Quản trị viên | quantrivien01 |

Mật khẩu do bạn tự đặt khi chạy load_sample_data.py. Repository không chứa mật khẩu hay hash mật khẩu từ máy gốc.

## Dựng bản trình diễn trên bản tải mới

Cài requirements.txt, sau đó chạy trước khi khởi động ứng dụng lần đầu:

    .\.venv\Scripts\python.exe load_sample_data.py
    .\.venv\Scripts\python.exe app.py

Nhập mật khẩu riêng khi được hỏi; nhập liệu được ẩn. Công cụ chỉ tạo database mới và từ chối nếu instance/campus.sqlite3 đã tồn tại. Dữ liệu trên máy đang dùng được giữ nguyên.

## Danh sách sinh viên

| Mã sinh viên / tên đăng nhập | Họ và tên |
|---|---|
| 11240001 | Nguyễn Minh Anh |
| 11240002 | Trần Hoàng Nam |
| 11240003 | Lê Thu Hà |
| 11240004 | Phạm Đức Huy |
| 11240005 | Hoàng Ngọc Linh |
| 11240006 | Vũ Gia Bảo |
| 11240007 | Đặng Phương Thảo |
| 11240008 | Bùi Quang Minh |
| 11240009 | Đỗ Khánh Ly |
| 11240010 | Hồ Tuấn Kiệt |
| 11240011 | Ngô Bảo Ngọc |
| 11240012 | Dương Hải Đăng |
| 11240013 | Lý Minh Châu |
| 11240014 | Mai Quốc Anh |
| 11240015 | Đinh Thanh Tâm |
| 11240016 | Phan Nhật Minh |
| 11240017 | Tạ Ngọc Hân |
| 11240018 | Cao Đức Anh |
| 11240019 | Trịnh Kim Ngân |
| 11240020 | Võ Anh Tú |
| 11240021 | Lâm Phương Nhi |
| 11240022 | Đoàn Trung Kiên |
| 11240023 | Hà Thùy Dương |
| 11240024 | Tô Thành Đạt |

## Trình diễn chức năng

- 11240001: tổng quan, biểu đồ, học phần, tải tài liệu, lọc câu sai/chưa làm.
- giangvien01: quản lý học liệu và câu hỏi trong phạm vi được phân công.
- canbo01: xem hồ sơ, kết quả, báo cáo, xuất CSV và kiểm duyệt.
- quantrivien01: quản trị tài khoản và phân công kiểm duyệt.

Các câu AI mẫu lưu nháp và ghi rõ mô phỏng; muốn gọi OpenAI thật cần cấu hình OPENAI_API_KEY riêng trên máy. Lịch sử mẫu giữ nguyên ngày ghi nhận, nên biểu đồ 7 ngày phụ thuộc ngày mở ứng dụng.
