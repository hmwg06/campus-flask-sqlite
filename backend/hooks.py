"""Kiểm tra đăng nhập, CSRF, bảo mật phản hồi và trang lỗi."""
import secrets
from datetime import date

from flask import abort, g, redirect, render_template, request, session, url_for

from .catalog import CATALOG, ROLES, STATUS
from .common import MANAGERS, one


def authenticate():
    # Token CSRF gắn với phiên; form POST phải gửi lại token này để được chấp nhận.
    session.setdefault('csrf_token', secrets.token_hex(32))
    # Đọc lại tài khoản mỗi yêu cầu để việc khóa tài khoản/đổi quyền có hiệu lực ngay.
    g.user = one('''SELECT u.*,coalesce(v.generation,0) AS auth_generation FROM users u
                    LEFT JOIN session_versions v ON v.user_id=u.id WHERE u.id=? AND u.active=1''', (session.get('user_id'),))
    if g.user and session.get('auth_generation', 0) != g.user['auth_generation']:
        session.clear()
        session['csrf_token'] = secrets.token_hex(32)
        g.user = None
    if request.method == 'POST':
        # compare_digest() so sánh token theo cách hạn chế lộ thông tin qua thời gian xử lý.
        if not secrets.compare_digest(session['csrf_token'], request.form.get('csrf_token', '')):
            abort(400, description='Phiên biểu mẫu đã hết hạn. Vui lòng tải lại trang rồi thử lại.')
    # endpoint là tên hàm route; các trang đăng nhập, khởi tạo và tệp tĩnh được miễn đăng nhập.
    if request.endpoint and request.endpoint not in ('login', 'setup', 'static', 'forgot_password', 'reset_password') and not g.user:
        return redirect(url_for('login'))


def secure_response(response):
    # Yêu cầu trình duyệt tôn trọng kiểu nội dung, hạn chế nhúng trang và thông tin referrer.
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.endpoint in ('reset_password', 'issue_recovery_link'):
        response.headers['Referrer-Policy'] = 'no-referrer'
    # CSP giới hạn nguồn tải script/CSS và nơi gửi form về cùng nguồn với website.
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'self'; base-uri 'self'"
    if request.endpoint != 'static':
        # Yêu cầu không lưu cache các trang động có dữ liệu người dùng.
        response.headers['Cache-Control'] = 'no-store'
    return response


def context():
    # Các biến này được đưa vào mọi template, không cần truyền lại ở từng render_template().
    return dict(roles=ROLES, statuses=STATUS, catalog=CATALOG, manager=g.user and g.user['role'] in MANAGERS,
                csrf_token=session.get('csrf_token'), today=date.today().strftime('%d/%m/%Y'))


def error_page(error):
    return render_template('error.html', error=error, title='Không thể thực hiện yêu cầu'), error.code
