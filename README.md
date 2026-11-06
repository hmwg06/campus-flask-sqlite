# LMS — Flask + SQLite

Website tiếng Việt gồm **3 module chính**:

| Module | Phạm vi | File nghiệp vụ |
|---|---|---|
| LMS | Ôn tập, phân tích cá nhân, học liệu; quản lý sinh viên, chương trình, lớp học và điểm | `backend/lms.py`, `backend/study.py` |
| Phân tích học tập | Kết quả theo lớp, điểm trung bình đã công bố, lượt sử dụng học liệu và xuất CSV | `backend/analytics.py` |
| Tài khoản & quyền | Đăng nhập, đổi/khôi phục mật khẩu, tài khoản và vai trò | `backend/m20.py`, `backend/recovery.py` |

Sinh viên có giao diện ôn tập và phân tích cá nhân. Cán bộ/admin xem báo cáo tổng hợp theo lớp; quản trị tài khoản dành cho admin, các vai trò khác vào **Tài khoản & quyền** để đổi mật khẩu. Quyền truy cập được kiểm tra phía server.

## Chạy trong PyCharm / Windows

Chọn môi trường `.venv` của dự án. Cài các thư viện trong `requirements.txt`, sau đó chạy `app.py` và truy cập **http://127.0.0.1:5000**.

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

## Bản trình diễn có sẵn dữ liệu

Repository có bộ dữ liệu trong `sample_data/data.json` và 24 tệp học liệu trong `sample_data/uploads/`. Bộ dữ liệu gồm 24 sinh viên, 6 lớp/học phần, 25 học liệu, 42 câu hỏi và lịch sử luyện tập. Xem danh sách tài khoản và cách trình diễn trong [TAI-KHOAN.md](TAI-KHOAN.md).

Trên bản tải mới, sau khi cài thư viện và **trước khi chạy ứng dụng lần đầu**, chạy:

```powershell
.\.venv\Scripts\python.exe load_sample_data.py
.\.venv\Scripts\python.exe app.py
```

Bạn tự đặt mật khẩu chung cho các tài khoản trình diễn khi được hỏi; công cụ tạo hash mới trên máy. Không có mật khẩu/hash đăng nhập, API key hay khóa phiên từ máy gốc trong bộ dữ liệu. Công cụ từ chối nếu database đã tồn tại; không ghi đè dữ liệu đang dùng. Khi chạy tự động có thể đặt biến môi trường `LMS_SAMPLE_PASSWORD` thay cho nhập tương tác. Bộ dữ liệu giả lập chỉ phục vụ trình diễn, nhận xét AI mẫu được ghi rõ là mô phỏng.

## Cấu trúc code

Dự án chia thành **frontend**, **backend** và **database**. Chạy bằng `app.py` như trước.

```text
FlaskProject7/
├── app.py                 # Điểm chạy website; export app, create_app và main
├── frontend/
│   ├── templates/         # Giao diện HTML/Jinja
│   └── static/            # CSS và JavaScript
├── backend/
│   ├── app.py             # Cấu hình Flask và đăng ký URL
│   ├── lms.py             # Quản lý học tập và các biểu mẫu LMS
│   ├── study.py           # Ôn tập và phân tích cá nhân cho sinh viên
│   ├── ai_client.py       # OpenAI Responses API và kiểm tra đầu ra
│   ├── ai_questions.py    # Soạn nháp và rà soát câu hỏi bằng AI
│   ├── question_review.py # Phân công và kiểm duyệt chuyên môn
│   ├── analytics.py       # Phân tích học tập và xuất CSV
│   ├── m20.py             # Đăng nhập, tài khoản và vai trò
│   ├── recovery.py        # Khôi phục mật khẩu sau xác minh
│   ├── common.py          # Truy vấn và giới hạn dữ liệu theo quyền
│   ├── hooks.py           # Xác thực, CSRF và xử lý lỗi
│   └── catalog.py         # Cấu hình trường biểu mẫu, vai trò, trạng thái
├── database/
│   ├── connection.py      # Kết nối SQLite, khởi tạo bảng và ghi nhật ký
│   └── schema.sql         # Định nghĩa các bảng và chỉ mục
└── instance/              # Dữ liệu chạy thực tế (không đưa lên Git)
```

- Sửa giao diện: mở `frontend/templates/`, `frontend/static/`.
- Sửa URL hoặc cấu hình: mở `backend/app.py`; sửa nghiệp vụ trong module backend tương ứng.
- Sửa cấu trúc bảng/kết nối: mở `database/schema.sql`, `database/connection.py`. Các truy vấn nghiệp vụ vẫn nằm trong backend.
- Database thực tế vẫn ở `instance/campus.sqlite3`; tệp tải lên và khóa phiên giữ nguyên trong `instance/`.

Frontend dùng HTML/Jinja do Flask render; ba thư mục cùng chạy trong một ứng dụng. Flask phục vụ CSS/JS tại `/static/...` như trước. Không cần chạy frontend riêng.

Ví dụ: `/students` → route trong `backend/app.py` → `backend/lms.py` → đọc SQLite qua `database/connection.py` → render `frontend/templates/listing.html`.

`create_app(config=None)` có thể import từ `backend.app` hoặc `app` để cấu hình ứng dụng theo môi trường triển khai. Các đường dẫn giao diện, schema và `instance` được xác định theo vị trí mã nguồn, không phụ thuộc thư mục chạy lệnh.

## Các luồng sử dụng

1. Admin tạo tài khoản cán bộ, giảng viên, sinh viên tại **Tài khoản & quyền**.
2. Cán bộ tạo chương trình và phiên bản, học phần, khung chương trình, lớp học; phân công giảng viên.
3. Cán bộ tạo hồ sơ sinh viên với mã duy nhất, liên kết tài khoản, thêm một hoặc nhiều chương trình theo học, đăng ký lớp học phần. Đổi trạng thái cần căn cứ thay đổi và có nhật ký.
4. Cán bộ nhập điểm 0–10 và công bố kết quả. Sinh viên chỉ xem điểm chính thức của mình; giảng viên xem học viên và kết quả trong lớp mình phụ trách.
5. Giảng viên tạo học liệu/câu hỏi thuộc học phần được phân công. Học liệu hỗ trợ tệp hoặc liên kết, tác giả/nguồn/phiên bản/quyền sử dụng, một tài liệu gắn nhiều học phần. Cán bộ/Admin công bố học liệu hoặc lưu trữ nội dung. Câu hỏi cần người được phân công kiểm duyệt học phần, khác người tạo, xác nhận trước khi công bố. Sửa nội dung sẽ đưa về nháp. Sinh viên chỉ truy cập nội dung đã công bố của lớp đã đăng ký; có luyện câu hỏi và phản hồi đúng/sai.
6. Cán bộ/Admin xem báo cáo lớp, điểm trung bình từ kết quả công bố, lượt tải/mở học liệu, thời gian từ tạo đến lần kiểm duyệt gần nhất; xuất CSV. Nhật ký chi tiết toàn hệ thống chỉ dành cho Admin.

## Ôn tập và phân tích cá nhân cho sinh viên

- Đăng nhập bằng tài khoản sinh viên đã liên kết hồ sơ và đăng ký lớp. Trang chủ hiển thị **Ôn tập hôm nay**, gợi ý ôn lại câu sai, tỷ lệ đúng theo môn, hoạt động 7 ngày và 8 lần trả lời gần nhất.
- **Học phần của tôi** (`/courses`) nhóm học liệu đã công bố theo môn. **Luyện tập** (`/practice`) lọc theo môn, câu chưa làm hoặc câu cần ôn lại; mỗi trang có tối đa 10 câu.
- Mỗi câu trả lời hợp lệ được lưu cùng phiên bản câu hỏi. Tỷ lệ đúng tính trên mọi lần trả lời của phiên bản hiện tại; danh sách cần ôn lại dùng kết quả gần nhất của từng câu. Trả lời đúng lần tiếp theo sẽ đưa câu đó ra khỏi danh sách cần ôn lại.
- Chỉ thống kê câu hỏi hiện được công bố thuộc học phần sinh viên có quyền truy cập. Khi câu hỏi đổi phiên bản, lịch sử cũ vẫn được lưu nhưng không đưa vào thống kê hiện tại. Chưa làm bài sẽ hiện **Chưa có dữ liệu**, không coi là kết quả 0%.
- Thời gian lịch sử và hoạt động 7 ngày dùng UTC. Tỷ lệ đúng là kết quả luyện tập, không phải điểm học phần hay chứng nhận hoàn thành.

## OpenAI và kiểm duyệt câu hỏi

Ứng dụng dùng [Responses API với Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). Khóa chỉ đọc từ biến môi trường trên máy chủ, không đưa vào HTML hoặc Git. Model mặc định là `gpt-4.1-mini`; có thể đổi bằng `OPENAI_MODEL` sang model hỗ trợ Responses API và Structured Outputs.

Trong PyCharm, mở **Run → Edit Configurations → cấu hình chạy app.py → Environment variables** và thêm:

```text
OPENAI_API_KEY=<khóa API của bạn>
OPENAI_MODEL=gpt-4.1-mini
```

Lưu cấu hình riêng trên máy, không chia sẻ cấu hình chứa khóa. Dừng và chạy lại `app.py` sau khi thêm biến môi trường. Không cần sửa mã nguồn. Ứng dụng không tự đọc file `.env`. Cần khóa OpenAI API có quyền gọi model và hạn mức sử dụng; khi chưa cấu hình khóa, chức năng AI bị vô hiệu hóa, các chức năng LMS khác vẫn dùng được.

1. Admin vào **Không gian học tập → Phân công kiểm duyệt**, chọn người có chuyên môn theo từng học phần. Admin cũng cần được phân công nếu trực tiếp duyệt; không ai tự duyệt câu mình tạo.
2. Giảng viên/cán bộ/admin chọn **Soạn với OpenAI**, nhập học phần, chủ đề, độ khó, nguồn và nội dung tham khảo. Mỗi yêu cầu tối đa 10 câu; nội dung tham khảo từ 20 đến 20.000 ký tự.
3. Đầu ra hợp lệ được lưu toàn bộ ở trạng thái **Nháp**, kèm model, tài liệu nguồn và giải thích. Phản hồi thiếu, sai cấu trúc hoặc lỗi API không tạo câu hỏi. Giá trị trạng thái/kiểm duyệt không lấy từ AI hay form người dùng.
4. Mở **Rà soát & kiểm duyệt** để yêu cầu AI nêu vấn đề về kiến thức, đáp án, diễn đạt và căn cứ nguồn. Nhận xét AI là gợi ý cần xác minh; không tự sửa hoặc công bố câu hỏi.
5. Người được phân công đọc nội dung, nguồn và nhận xét, ghi nhận xét chuyên môn, xác nhận đã kiểm tra rồi **Duyệt chuyên môn & công bố** hoặc **Yêu cầu chỉnh sửa**. Quyết định lưu người duyệt, thời gian và phiên bản.
6. Mỗi lần sửa câu hỏi tăng phiên bản, đưa về nháp và yêu cầu duyệt lại. Quyết định cho phiên bản cũ bị từ chối; kết quả AI trả về khi nội dung đã thay đổi không được lưu. Nhận xét AI đã lưu cho bản cũ được ghi rõ trên giao diện.

Chỉ nội dung câu hỏi, chủ đề/học phần và tài liệu tham khảo được gửi tới OpenAI; không gửi hồ sơ, điểm hoặc tài khoản sinh viên. Lời gọi đặt `store=False`; điều này không thay thế chính sách xử lý dữ liệu của nhà cung cấp. Chỉ gửi tài liệu được phép sử dụng. Giới hạn mặc định 15 giây giữa các yêu cầu AI của một tài khoản, thời gian chờ API 45 giây và không tự thử lại.

Các bảng AI và kiểm duyệt được thêm tự động khi khởi động; câu hỏi đã công bố trước khi nâng cấp giữ trạng thái hiện có. Câu hỏi mới và câu đã chỉnh sửa phải qua quy trình duyệt ở trên. Phân công chuyên môn do admin xác minh, ứng dụng không tự đánh giá bằng cấp của người duyệt.

## Quên mật khẩu

1. Người dùng chọn **Quên mật khẩu?** trên trang đăng nhập và gửi tên đăng nhập.
2. Admin mở **Tài khoản & quyền → Yêu cầu quên mật khẩu**, xác minh danh tính qua kênh liên hệ đã biết, rồi chọn **Cấp liên kết**.
3. Admin gửi riêng liên kết cho đúng người đã được xác minh. Liên kết chỉ dùng một lần, hết hạn sau 30 phút; cấp lại sẽ hủy liên kết cũ. Bản hiện tại không gửi email tự động.
4. Người dùng nhập và xác nhận mật khẩu mới (8–256 ký tự). Đặt lại thành công sẽ vô hiệu hóa các phiên đăng nhập cũ.

Các bảng lịch sử luyện tập và khôi phục mật khẩu được thêm tự động khi khởi động lại ứng dụng; dữ liệu hiện có được giữ nguyên.

## Phạm vi theo vai trò


| Vai trò | Phạm vi |
|---|---|
| Admin | Toàn hệ thống, cấp/khóa tài khoản, đổi vai trò, đặt lại mật khẩu và xem nhật ký |
| Cán bộ | Hồ sơ, chương trình, lớp, đăng ký, điểm, kiểm duyệt và báo cáo |
| Giảng viên | Sinh viên trong lớp được phân công; quản lý học liệu/câu hỏi do mình tạo và thuộc học phần phụ trách; xem và kiểm duyệt câu hỏi của học phần được admin phân công |
| Sinh viên | Hồ sơ/kết quả của mình; lớp đã đăng ký và nội dung đã công bố của các học phần đó |

Hồ sơ cá nhân dùng mã duy nhất, các lần theo học tách riêng theo chương trình/phiên bản. Đây là chính sách mặc định cho phiên bản này. Cán bộ cấp mã thủ công, hệ thống kiểm tra trùng. Không sao chép dữ liệu tài chính/luận văn vào hồ sơ.

## Lưu trữ và bảo mật

- `instance/campus.sqlite3`: cơ sở dữ liệu; tự tạo, không reset khi khởi động lại.
- `instance/uploads/`: tệp học liệu, tên lưu ngẫu nhiên; tải qua route kiểm tra quyền, không phục vụ công khai từ `static`.
- `instance/secret.key`: khóa phiên bền vững; có thể thay bằng biến môi trường `SECRET_KEY`.
- Mật khẩu được hash; CSRF trên tất cả POST; truy vấn tham số hóa; kiểm tra quyền phía server; CSV vô hiệu hóa công thức từ ô văn bản.
- Khóa/đổi vai trò có hiệu lực ở yêu cầu tiếp theo, không cho tự khóa/hạ quyền admin hoặc loại bỏ admin cuối cùng.
- Đổi hoặc đặt lại mật khẩu vô hiệu hóa các phiên đăng nhập cũ; khi người dùng tự đổi mật khẩu, phiên đang thao tác được giữ lại.
- Sao lưu cả ba mục trong `instance` khi ứng dụng đã dừng. Không đưa `instance` vào Git.
- Chạy mặc định ở localhost, không bật debug. Khi triển khai mạng thật, cần HTTPS, cookie Secure, WSGI server, giới hạn thử đăng nhập, kiểm tra an toàn tệp tải lên và quy trình sao lưu phù hợp.

## Phạm vi phiên bản hiện tại

Ứng dụng lưu dữ liệu thật bằng SQLite và hỗ trợ OpenAI khi được cấu hình API key. Chưa tích hợp SSO, gửi email tự động, thi trực tuyến hoặc đồng bộ với LMS bên ngoài.

Lưu lịch sử chỉnh sửa trong nhật ký; chưa có giao diện khôi phục phiên bản. Giới hạn tải lên 16 MB cho toàn bộ request; các tệp được tải xuống dưới dạng đính kèm. Lượt truy cập học liệu ghi nhận việc mở/tải, không đại diện thời lượng học hay hoàn thành khóa học. Không xóa dữ liệu lịch sử qua giao diện; dùng trạng thái bảo lưu/thôi học/lưu trữ/khóa.

## Cập nhật lên GitHub

Bộ mã nguồn gồm `app.py`, `backend/`, `database/`, `frontend/`, `requirements.txt`, `README.md` và `.gitignore`; kèm `sample_data/`, `load_sample_data.py` và `TAI-KHOAN.md` để dựng bản trình diễn. Môi trường `.venv/`, cấu hình IDE, bộ nhớ đệm, dữ liệu riêng trong `instance/` và gói bàn giao `.release/` được loại khỏi Git.

Để cập nhật repository hiện có và ghi nhận cả những file cũ đã xóa:

```powershell
git add -A
git status
git commit -m "Finalize LMS student learning interface and personal analytics"
git push
```

Nếu dùng gói `LMS-source.zip`, giải nén và đưa nội dung bên trong vào repository, bao gồm `.gitignore`. Nếu repository vẫn có cấu trúc cũ, xóa `campus/`, `templates/`, `static/`, `schema.sql`, `tests/` và các tài liệu kế hoạch cũ trước khi cập nhật; giao diện hiện nằm trong `frontend/`, schema nằm trong `database/`.
