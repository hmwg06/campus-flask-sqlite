"""Chạy app.py để mở website; xem các mục xử lý trong thư mục campus."""
import argparse
import os
import secrets
from pathlib import Path

from flask import Flask

from campus import db, hooks
from campus import auth as auth_views
from campus import dashboard as dashboard_views
from campus import students as students_views
from campus import training as training_views
from campus import learning as learning_views
from campus import records as records_views
from campus import reports as reports_views
from campus import accounts as accounts_views


def create_app(test_config=None):
    # Tạo ứng dụng; __name__ giúp Flask tìm templates/static cạnh file này.
    # instance_relative_config=True cho phép nạp cấu hình tương đối từ thư mục instance.
    app = Flask(__name__, instance_relative_config=True)
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
    )
    if test_config:
        # Cho phép kiểm thử thay database, thư mục upload và khóa phiên bằng giá trị riêng.
        app.config.update(test_config)

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
        return auth_views.setup()

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        return auth_views.login()

    @app.route('/logout', methods=['POST'])
    def logout():
        return auth_views.logout()

    @app.route('/password', methods=['GET', 'POST'])
    def password():
        return auth_views.password()

    # Trang tổng quan
    @app.route('/')
    def dashboard():
        return dashboard_views.dashboard()

    # M03 — Sinh viên
    @app.route('/students')
    def students():
        return students_views.students()

    # <int:record_id> nhận số nguyên từ URL, ví dụ /students/12 truyền record_id=12.
    @app.route('/students/<int:record_id>')
    def student_detail(record_id):
        return students_views.student_detail(record_id)

    # M04 — Đào tạo và giảng viên
    @app.route('/training')
    def training():
        return training_views.training()

    @app.route('/lecturers')
    def lecturers():
        return training_views.lecturers()

    # M10 — Học liệu và câu hỏi
    @app.route('/learning')
    def learning():
        return learning_views.learning()

    @app.route('/<table>/<int:record_id>/<action>', methods=['POST'])
    def publication(table, record_id, action):
        return learning_views.publication(table, record_id, action)

    @app.route('/resources/<int:record_id>/download')
    def download(record_id):
        return learning_views.download(record_id)

    @app.route('/questions/<int:record_id>/answer', methods=['POST'])
    def answer_question(record_id):
        return learning_views.answer_question(record_id)

    # Danh sách và biểu mẫu thêm/sửa dùng chung
    @app.route('/records/<table>')
    def listing(table):
        return records_views.listing(table)

    # Hai URL dùng chung một hàm: không có record_id là thêm mới, có ID là chỉnh sửa.
    @app.route('/records/<table>/new', methods=['GET', 'POST'])
    @app.route('/records/<table>/<int:record_id>/edit', methods=['GET', 'POST'])
    def edit_record(table, record_id=None):
        return records_views.edit_record(table, record_id)

    # M17 — Báo cáo
    @app.route('/reports')
    def reports():
        return reports_views.reports()

    @app.route('/reports/export')
    def export_report():
        return reports_views.export_report()

    # M20 — Quản lý tài khoản
    @app.route('/accounts')
    def accounts():
        return accounts_views.accounts()

    @app.route('/accounts/new', methods=['GET', 'POST'])
    @app.route('/accounts/<int:record_id>/edit', methods=['GET', 'POST'])
    def account_edit(record_id=None):
        return accounts_views.account_edit(record_id)

    # Ngoài một request, cần mở ngữ cảnh để get_db() dùng được current_app và g.
    with app.app_context():
        db.init_db()
    return app


app = create_app()


def main():
    # Tham số command là tùy chọn: python app.py và python app.py run đều mở website.
    # argparse tự xử lý --help và từ chối lệnh không nằm trong choices.
    parser = argparse.ArgumentParser(description='Campus - Flask + SQLite')
    parser.add_argument('command', nargs='?', default='run', choices=['run'],
                        help='run: start website')
    parser.parse_args()
    app.run(debug=False)


if __name__ == '__main__':
    main()
