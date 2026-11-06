"""Tạo ứng dụng Flask, cấu hình và đăng ký các URL của backend."""
import os
import secrets
from pathlib import Path

from flask import Flask

from database import connection as db
from backend import hooks, lms, analytics, m20, study, recovery, ai_questions, question_review


def create_app(config=None):
    # Đường dẫn cố định theo gốc dự án, không phụ thuộc thư mục chạy lệnh.
    root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(root / 'frontend' / 'templates'),
        static_folder=str(root / 'frontend' / 'static'),
        static_url_path='/static',
        instance_path=str(root / 'instance'),
        instance_relative_config=True,
    )
    folder = Path(app.instance_path)
    folder.mkdir(exist_ok=True)

    # Lưu khóa đăng nhập để dùng lại khi khởi động website.
    key_path = folder / 'secret.key'
    try:
        # Chế độ 'x' chỉ tạo file mới, không ghi đè khóa đã tồn tại.
        with key_path.open('x', encoding='utf-8') as file:
            file.write(secrets.token_hex(32))
    except FileExistsError:
        pass  # Đã có khóa thì giữ nguyên.

    # Cấu hình nơi lưu dữ liệu và giới hạn tệp tải lên (16 MB).
    app.config.update(
        # Ưu tiên biến môi trường; khóa dùng để ký cookie phiên, phát hiện việc sửa cookie.
        SECRET_KEY=os.environ.get('SECRET_KEY') or key_path.read_text(encoding='utf-8'),
        DATABASE=str(folder / 'campus.sqlite3'),
        UPLOAD_FOLDER=str(folder / 'uploads'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # Giới hạn tổng dung lượng một request, tính bằng byte.
        # HttpOnly chặn JS đọc cookie; SameSite=Lax hạn chế gửi cookie trong yêu cầu từ site khác.
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY', ''),
        OPENAI_MODEL=os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'),
        AI_MIN_INTERVAL_SECONDS=15,
    )
    if config:
        # Cho phép cấu hình riêng cho từng môi trường triển khai.
        app.config.update(config)

    # Đóng kết nối SQLite sau mỗi yêu cầu.
    app.teardown_appcontext(db.close_db)


    # Áp dụng kiểm tra đăng nhập, CSRF và xử lý lỗi cho các trang.
    # before_request chạy trước route; after_request chỉnh phản hồi trước khi gửi về trình duyệt.
    app.before_request(hooks.authenticate)
    app.after_request(hooks.secure_response)
    app.context_processor(hooks.context)
    # 400: yêu cầu sai; 403: thiếu quyền; 404: không tìm thấy; 413: dữ liệu gửi lên quá lớn.
    for code in (400, 403, 404, 413):
        app.register_error_handler(code, hooks.error_page)

    # Mỗi đường dẫn gọi hàm xử lý trong file phụ trách mục tương ứng.
    # Đăng nhập và tài khoản cá nhân
    # @app.route gắn URL với hàm bên dưới; GET hiển thị form, POST xử lý dữ liệu gửi lên.
    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        return m20.setup()

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        return m20.login()

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        return recovery.forgot_password()

    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        return recovery.reset_password(token)

    @app.route('/accounts/recovery')
    def recovery_requests():
        return recovery.requests_page()

    @app.route('/accounts/recovery/<int:user_id>/issue', methods=['POST'])
    def issue_recovery_link(user_id):
        return recovery.issue_link(user_id)

    @app.route('/logout', methods=['POST'])
    def logout():
        return m20.logout()

    @app.route('/password', methods=['GET', 'POST'])
    def password():
        return m20.password()

    # Trang tổng quan
    @app.route('/')
    def dashboard():
        return lms.dashboard()

    # LMS — Sinh viên
    @app.route('/students')
    def students():
        return lms.students()

    # <int:record_id> nhận số nguyên từ URL, ví dụ /students/12 truyền record_id=12.
    @app.route('/students/<int:record_id>')
    def student_detail(record_id):
        return lms.student_detail(record_id)

    # LMS — Đào tạo và giảng viên
    @app.route('/training')
    def training():
        return lms.training()

    @app.route('/lecturers')
    def lecturers():
        return lms.lecturers()

    # LMS — Học liệu và câu hỏi
    @app.route('/learning')
    def learning():
        return lms.learning()

    @app.route('/courses')
    def courses():
        return study.courses()

    @app.route('/practice')
    def practice():
        return study.practice()

    @app.route('/questions/ai', methods=['GET', 'POST'])
    def ai_generate_questions():
        return ai_questions.generate()

    @app.route('/questions/<int:record_id>/ai-review', methods=['POST'])
    def ai_review_question(record_id):
        return ai_questions.review(record_id)

    @app.route('/questions/<int:record_id>/review', methods=['GET', 'POST'])
    def review_question(record_id):
        return question_review.review(record_id)

    @app.route('/question-reviewers', methods=['GET', 'POST'])
    def question_reviewers():
        return question_review.assignments()

    @app.route('/<table>/<int:record_id>/<action>', methods=['POST'])
    def publication(table, record_id, action):
        return lms.publication(table, record_id, action)

    @app.route('/resources/<int:record_id>/download')
    def download(record_id):
        return lms.download(record_id)

    @app.route('/questions/<int:record_id>/answer', methods=['POST'])
    def answer_question(record_id):
        return lms.answer_question(record_id)

    # Danh sách và biểu mẫu thêm/sửa dùng chung
    @app.route('/records/<table>')
    def listing(table):
        return lms.listing(table)

    # Hai URL dùng chung một hàm: không có record_id là thêm mới, có ID là chỉnh sửa.
    @app.route('/records/<table>/new', methods=['GET', 'POST'])
    @app.route('/records/<table>/<int:record_id>/edit', methods=['GET', 'POST'])
    def edit_record(table, record_id=None):
        return lms.edit_record(table, record_id)

    # Phân tích học tập — Thống kê và xuất báo cáo
    @app.route('/reports')
    def reports():
        return analytics.reports()

    @app.route('/reports/export')
    def export_report():
        return analytics.export_report()

    # M20 — Quản lý tài khoản
    @app.route('/accounts')
    def accounts():
        return m20.accounts()

    @app.route('/accounts/new', methods=['GET', 'POST'])
    @app.route('/accounts/<int:record_id>/edit', methods=['GET', 'POST'])
    def account_edit(record_id=None):
        return m20.account_edit(record_id)

    # Ngoài một request, cần mở ngữ cảnh để get_db() dùng được current_app và g.
    with app.app_context():
        db.init_db()
    return app
