# Campus — Flask + SQLite

Website tiếng Việt gồm M03 (sinh viên), M04 (đào tạo), M10 (LMS/LCMS), M17 (báo cáo), M20 (tài khoản).

## Chạy trong PyCharm / Windows

Chọn môi trường `.venv` của dự án. Cài `requirements.txt` nếu chưa có Flask, sau đó chạy `app.py` và truy cập **http://127.0.0.1:5000**.

Nếu vừa tải mã nguồn từ GitHub, tạo môi trường Python trước (Python 3.10 trở lên):

```powershell
py -m venv .venv
```

Repository chứa mã nguồn ứng dụng. Database, tài khoản hiện có, tệp tải lên và khóa phiên không được đưa lên GitHub; ứng dụng tự tạo database mới khi chạy lần đầu.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Lần đầu mở website sẽ có màn hình tạo tài khoản quản trị. Không có mật khẩu mặc định.

## Cấu trúc code

**`app.py`** cấu hình Flask và khai báo các URL bằng `@app.route`. Mỗi route gọi một hàm xử lý trong thư mục `campus`; không dùng Blueprint.

Muốn đổi URL, sửa `app.py`. Muốn đổi nghiệp vụ, mở file phụ trách mục tương ứng. Chú thích giải thích câu lệnh được giữ cùng phần code đã chuyển.

| Thành phần | Nội dung |
|---|---|
| `app.py` | Cấu hình ứng dụng, đăng ký route và chạy website |
| `campus/auth.py` | Khởi tạo quản trị viên, đăng nhập, đăng xuất, đổi mật khẩu |
| `campus/dashboard.py` | Trang tổng quan |
| `campus/students.py` | Hồ sơ sinh viên và kết quả học tập |
| `campus/training.py` | Đào tạo và danh sách giảng viên |
| `campus/learning.py` | Học liệu, kiểm duyệt, tải tài liệu và luyện câu hỏi |
| `campus/reports.py` | Báo cáo và xuất CSV |
| `campus/accounts.py` | Quản lý tài khoản và vai trò |
| `campus/records.py` | Trang danh sách, biểu mẫu thêm/sửa và kiểm tra dữ liệu dùng chung |
| `campus/common.py` | Truy vấn và giới hạn dữ liệu theo quyền |
| `campus/hooks.py` | Kiểm tra đăng nhập, CSRF, phản hồi và trang lỗi |
| `campus/catalog.py` | Cấu hình trường biểu mẫu, vai trò và trạng thái |
| `campus/db.py` | Kết nối SQLite, khởi tạo bảng và ghi nhật ký |
| `schema.sql` | Cấu trúc bảng SQLite |
| `templates/`, `static/` | HTML, CSS và JavaScript |

Ví dụ: mở `/students` → route `students()` trong `app.py` → `campus/students.py` → hiển thị danh sách. Các file tính năng không import ngược lại `app.py`. `create_app()` vẫn được giữ để kiểm thử với database tạm riêng.


## Các luồng sử dụng

1. Admin tạo tài khoản cán bộ, giảng viên, sinh viên tại **Tài khoản & quyền**.
2. Cán bộ tạo chương trình và phiên bản, học phần, khung chương trình, lớp học; phân công giảng viên.
3. Cán bộ tạo hồ sơ sinh viên với mã duy nhất, liên kết tài khoản, thêm một hoặc nhiều chương trình theo học, đăng ký lớp học phần. Đổi trạng thái cần căn cứ thay đổi và có nhật ký.
4. Cán bộ nhập điểm 0–10 và công bố kết quả. Sinh viên chỉ xem điểm chính thức của mình; giảng viên xem học viên và kết quả trong lớp mình phụ trách.
5. Giảng viên tạo học liệu/câu hỏi thuộc học phần được phân công. Học liệu hỗ trợ tệp hoặc liên kết, tác giả/nguồn/phiên bản/quyền sử dụng, một tài liệu gắn nhiều học phần. Cán bộ/Admin duyệt và công bố hoặc lưu trữ. Sửa nội dung sẽ đưa về nháp. Sinh viên chỉ truy cập nội dung đã công bố của lớp đã đăng ký; có luyện câu hỏi và phản hồi đúng/sai.
6. Cán bộ/Admin xem báo cáo lớp, điểm trung bình từ kết quả công bố, lượt tải/mở học liệu, thời gian từ tạo đến lần kiểm duyệt gần nhất; xuất CSV. Nhật ký chi tiết toàn hệ thống chỉ dành cho Admin.

## Phân quyền


| Vai trò | Phạm vi |
|---|---|
| Admin | Toàn hệ thống, cấp/khóa tài khoản, đổi vai trò, đặt lại mật khẩu và xem nhật ký |
| Cán bộ | Hồ sơ, chương trình, lớp, đăng ký, điểm, kiểm duyệt và báo cáo |
| Giảng viên | Sinh viên trong lớp được phân công; quản lý học liệu/câu hỏi do mình tạo và thuộc học phần phụ trách |
| Sinh viên | Hồ sơ/kết quả của mình; lớp đã đăng ký và nội dung đã công bố của các học phần đó |

Hồ sơ cá nhân dùng mã duy nhất, các lần theo học tách riêng theo chương trình/phiên bản. Đây là chính sách mặc định cho phiên bản này. Cán bộ cấp mã thủ công, hệ thống kiểm tra trùng. Không sao chép dữ liệu tài chính/luận văn vào hồ sơ.

## Lưu trữ và bảo mật

- `instance/campus.sqlite3`: cơ sở dữ liệu; tự tạo, không reset khi khởi động lại.
- `instance/uploads/`: tệp học liệu, tên lưu ngẫu nhiên; tải qua route kiểm tra quyền, không phục vụ công khai từ `static`.
- `instance/secret.key`: khóa phiên bền vững; có thể thay bằng biến môi trường `SECRET_KEY`.
- Mật khẩu được hash; CSRF trên tất cả POST; truy vấn tham số hóa; kiểm tra quyền phía server; CSV vô hiệu hóa công thức từ ô văn bản.
- Khóa/đổi vai trò có hiệu lực ở yêu cầu tiếp theo, không cho tự khóa/hạ quyền admin hoặc loại bỏ admin cuối cùng.
- Sao lưu cả ba mục trong `instance` khi ứng dụng đã dừng. Không đưa `instance` vào Git.
- Chạy mặc định ở localhost, không bật debug. Khi triển khai mạng thật, cần HTTPS, cookie Secure, WSGI server, giới hạn thử đăng nhập, kiểm tra an toàn tệp tải lên và quy trình sao lưu phù hợp.

## Phạm vi phiên bản hiện tại

Đây là bản ứng dụng nền tảng có các luồng chính hoạt động và dữ liệu lưu thật, chưa phải toàn bộ hệ thống quản trị đại học ở quy mô sản xuất. Chưa tích hợp nhà cung cấp SSO, API AI, tài chính, luận văn, tài khoản dịch vụ/chuyên gia riêng, quyền theo đơn vị/thời hạn, KPI/HEDI chính thức, quy đổi giờ giảng, phòng học/xếp lịch tự động, thi trực tuyến hay đồng bộ LMS ngoài. Hỗ trợ người học chỉ được nhắc trong phần tổng quan ảnh M10, chưa có đặc tả module riêng nên chưa triển khai ticket/chatbot.

Lưu lịch sử chỉnh sửa trong nhật ký; chưa có giao diện khôi phục phiên bản. Giới hạn tải lên 16 MB cho toàn bộ request; các tệp được tải xuống dưới dạng đính kèm. Lượt truy cập học liệu ghi nhận việc mở/tải, không đại diện thời lượng học hay hoàn thành khóa học. Không xóa dữ liệu lịch sử qua giao diện; dùng trạng thái bảo lưu/thôi học/lưu trữ/khóa.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kiểm thử dùng SQLite tạm riêng, không thay đổi dữ liệu đang sử dụng.
