"""Admin-verified recovery with expiring single-use reset links."""
import hashlib
import secrets

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from database.connection import audit, get_db, invalidate_sessions
from .common import one, query, require


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        user = one('SELECT id FROM users WHERE username=? AND active=1', (username,)) if 0 < len(username) <= 80 else None
        if user:
            # One outstanding request per account; public requests cannot revoke an issued link.
            get_db().execute('INSERT OR IGNORE INTO password_recovery(user_id) VALUES(?)', (user['id'],))
            get_db().commit()
        flash('Nếu tài khoản hợp lệ, yêu cầu đã được ghi nhận. Vui lòng liên hệ quản trị viên để xác minh và nhận liên kết đặt lại mật khẩu.', 'success')
        return redirect(url_for('forgot_password'))
    return render_template('recovery_form.html', title='Quên mật khẩu', reset=False)


def requests_page(reset_link=None):
    require('admin')
    requests = query('''SELECT r.*,u.username,u.full_name,u.role,u.active FROM password_recovery r
                        JOIN users u ON u.id=r.user_id ORDER BY r.requested_at''')
    return render_template('recovery_requests.html', title='Yêu cầu khôi phục mật khẩu', active='accounts',
                           requests=requests, reset_link=reset_link)


def issue_link(user_id):
    require('admin')
    if request.form.get('verified') != '1':
        abort(400, description='Cần xác minh danh tính người yêu cầu trước khi cấp liên kết.')
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    user = one('''SELECT u.* FROM users u JOIN password_recovery r ON r.user_id=u.id
                  WHERE u.id=? AND u.active=1''', (user_id,))
    if not user:
        abort(404)
    token = secrets.token_urlsafe(32)
    db.execute("""UPDATE password_recovery SET token_hash=?,password_stamp=?,
                  expires_at=datetime('now','+30 minutes') WHERE user_id=?""",
               (digest(token), digest(user['password_hash']), user_id))
    audit('Cấp liên kết khôi phục sau xác minh', 'users', user_id)
    db.commit()
    # Do not persist the plaintext token in sessions, audit logs or the database.
    return requests_page(url_for('reset_password', token=token, _external=True))


def reset_password(token):
    db = get_db()
    if request.method == 'POST':
        db.execute('BEGIN IMMEDIATE')
    row = one('''SELECT r.user_id,r.password_stamp,u.password_hash FROM password_recovery r
                 JOIN users u ON u.id=r.user_id WHERE r.token_hash=?
                 AND r.expires_at>CURRENT_TIMESTAMP AND u.active=1''', (digest(token),))
    if not row or not secrets.compare_digest(row['password_stamp'], digest(row['password_hash'])):
        abort(400, description='Liên kết không hợp lệ, đã hết hạn hoặc đã được sử dụng. Vui lòng yêu cầu liên kết mới.')
    if request.method == 'POST':
        password = request.form.get('password', '')
        if not 8 <= len(password) <= 256 or password != request.form.get('confirm_password'):
            db.rollback()
            flash('Mật khẩu cần 8–256 ký tự và hai lần nhập phải giống nhau.', 'error')
        else:
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (generate_password_hash(password), row['user_id']))
            db.execute('DELETE FROM password_recovery WHERE user_id=?', (row['user_id'],))
            invalidate_sessions(row['user_id'])
            audit('Khôi phục mật khẩu', 'users', row['user_id'])
            db.commit()
            session.clear()
            flash('Đã đặt lại mật khẩu. Vui lòng đăng nhập bằng mật khẩu mới.', 'success')
            return redirect(url_for('login'))
    return render_template('recovery_form.html', title='Đặt lại mật khẩu', reset=True)
