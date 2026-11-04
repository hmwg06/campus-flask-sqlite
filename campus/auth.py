"""Khởi tạo tài khoản quản trị, đăng nhập, đăng xuất và đổi mật khẩu."""
import secrets

from flask import flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .common import one
from .db import audit, get_db


def setup():
    if one('SELECT 1 FROM users'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        name = request.form.get('full_name', '').strip()
        if not username or not name or len(username) > 80 or len(name) > 160 or not 8 <= len(password) <= 256:
            flash('Điền đầy đủ thông tin. Mật khẩu cần từ 8 đến 256 ký tự.', 'error')
        else:
            db = get_db()
            db.execute('BEGIN IMMEDIATE')
            # Kiểm tra lại sau khi giữ quyền ghi để hai yêu cầu không cùng tạo admin đầu tiên.
            if db.execute('SELECT 1 FROM users').fetchone():
                db.rollback()
                return redirect(url_for('login'))
            # Chỉ lưu hash mật khẩu; không lưu mật khẩu gốc vào database.
            db.execute("INSERT INTO users(username,full_name,password_hash,role) VALUES(?,?,?,'admin')", (username, name, generate_password_hash(password)))
            db.commit()
            flash('Đã tạo quản trị viên. Bạn có thể đăng nhập.', 'success')
            return redirect(url_for('login'))
    return render_template('login.html', setup=True, title='Khởi tạo hệ thống')


def login():
    if not one('SELECT 1 FROM users'):
        return redirect(url_for('setup'))
    if request.method == 'POST':
        user = one('SELECT * FROM users WHERE username=? AND active=1', (request.form.get('username', '').strip(),))
        password = request.form.get('password', '')
        # Kiểm tra mật khẩu nhập vào với hash đã lưu; không thể so sánh hai chuỗi trực tiếp.
        if user and len(password) <= 256 and check_password_hash(user['password_hash'], password):
            # Xóa trạng thái phiên cũ và tạo CSRF token mới sau khi đăng nhập thành công.
            session.clear()
            session.update(user_id=user['id'], csrf_token=secrets.token_hex(32))
            # url_for nhận tên hàm route; redirect yêu cầu trình duyệt chuyển sang URL đó.
            return redirect(url_for('dashboard'))
        flash('Tên đăng nhập hoặc mật khẩu không đúng, hoặc tài khoản đã bị khóa.', 'error')
    # Ghép file HTML trong templates với các biến truyền vào để tạo trang trả về.
    return render_template('login.html', title='Đăng nhập')


def logout():
    # Xóa user_id và CSRF token khỏi phiên; đăng xuất cũng phải là POST có CSRF hợp lệ.
    session.clear()
    return redirect(url_for('login'))


def password():
    if request.method == 'POST':
        old, new = request.form.get('old_password', ''), request.form.get('password', '')
        if len(old) > 256 or not check_password_hash(g.user['password_hash'], old):
            flash('Mật khẩu hiện tại không đúng.', 'error')
        elif not 8 <= len(new) <= 256 or new != request.form.get('confirm_password'):
            flash('Mật khẩu mới cần 8–256 ký tự và hai lần nhập phải giống nhau.', 'error')
        else:
            get_db().execute('UPDATE users SET password_hash=? WHERE id=?', (generate_password_hash(new), g.user['id']))
            audit('Đổi mật khẩu', 'users', g.user['id'])
            # commit() lưu thay đổi mật khẩu và nhật ký trong cùng giao dịch.
            get_db().commit()
            flash('Đã đổi mật khẩu.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('password.html', title='Đổi mật khẩu')
