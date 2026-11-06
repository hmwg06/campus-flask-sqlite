"""M20: đăng nhập, tài khoản và phân quyền."""
import json
import secrets
import sqlite3
from .catalog import ROLES
from .common import one, query, require
from database.connection import audit, get_db, invalidate_sessions
from flask import abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


# --- AUTH ---
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
        # Capture the password and generation in one snapshot. A reset during password
        # verification must not grant the old credentials a new session generation.
        user = one('''SELECT u.*,coalesce(v.generation,0) AS auth_generation FROM users u
                      LEFT JOIN session_versions v ON v.user_id=u.id
                      WHERE u.username=? AND u.active=1''', (request.form.get('username', '').strip(),))
        password = request.form.get('password', '')
        # Kiểm tra mật khẩu nhập vào với hash đã lưu; không thể so sánh hai chuỗi trực tiếp.
        if user and len(password) <= 256 and check_password_hash(user['password_hash'], password):
            # Xóa trạng thái phiên cũ và tạo CSRF token mới sau khi đăng nhập thành công.
            session.clear()
            session.update(user_id=user['id'], csrf_token=secrets.token_hex(32))
            session['auth_generation'] = user['auth_generation']
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
            generation = invalidate_sessions(g.user['id'])
            audit('Đổi mật khẩu', 'users', g.user['id'])
            # commit() lưu thay đổi mật khẩu và nhật ký trong cùng giao dịch.
            get_db().commit()
            session['auth_generation'] = generation
            flash('Đã đổi mật khẩu.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('password.html', title='Đổi mật khẩu')


# --- ACCOUNTS ---
def accounts():
    require('admin')
    return render_template('accounts.html', title='Tài khoản & phân quyền', active='accounts',
                           users=query("SELECT u.*,s.code AS student_code FROM users u LEFT JOIN students s ON s.user_id=u.id AND u.role='student' ORDER BY u.id"),
                           logs=query('SELECT a.*,u.full_name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 100'))


def account_edit(record_id=None):
    require('admin')
    user = one("SELECT u.*,s.code AS student_code FROM users u LEFT JOIN students s ON s.user_id=u.id AND u.role='student' WHERE u.id=?", (record_id,)) if record_id else None
    if record_id and not user:
        abort(404)
    values = dict(user) if user else {}
    if request.method == 'POST':
        values = request.form.to_dict()
        name, role = values.get('full_name', '').strip(), values.get('role', '')
        active = values.get('active', '1')
        password = values.get('password', '')
        try:
            if not name or len(name) > 160 or role not in ROLES or active not in ('0', '1'):
                raise ValueError('Thông tin tài khoản không hợp lệ.')
            # Không cho quản trị viên tự khóa/hạ quyền tài khoản đang sử dụng.
            if user and user['id'] == g.user['id'] and (role != 'admin' or active != '1'):
                raise ValueError('Không thể tự khóa hoặc hạ quyền quản trị viên đang đăng nhập.')
            if user and user['role'] != role:
                # Không đổi vai trò khi tài khoản còn liên kết hồ sơ/lớp cần vai trò cũ.
                if one('SELECT 1 FROM students WHERE user_id=?', (record_id,)) and role != 'student':
                    raise ValueError('Tài khoản đang liên kết hồ sơ sinh viên; hãy gỡ liên kết trước khi đổi vai trò.')
                if one('SELECT 1 FROM classes WHERE teacher_id=?', (record_id,)) and role != 'teacher':
                    raise ValueError('Tài khoản đang phụ trách lớp; hãy phân công lại trước khi đổi vai trò.')
            if (not user or password) and not 8 <= len(password) <= 256:
                raise ValueError('Mật khẩu cần từ 8 đến 256 ký tự.')
            db = get_db()
            db.execute('BEGIN IMMEDIATE')
            # Kiểm tra trong giao dịch ghi để luôn còn ít nhất một admin hoạt động.
            if user and user['role'] == 'admin' and (role != 'admin' or active == '0'):
                if one("SELECT count(*) AS n FROM users WHERE role='admin' AND active=1")['n'] <= 1:
                    raise ValueError('Phải giữ lại ít nhất một quản trị viên hoạt động.')
            if user:
                db.execute('UPDATE users SET full_name=?,role=?,active=? WHERE id=?', (name, role, int(active), record_id))
                # Khi sửa tài khoản, để trống mật khẩu nghĩa là giữ nguyên hash hiện tại.
                if password:
                    db.execute('UPDATE users SET password_hash=? WHERE id=?', (generate_password_hash(password), record_id))
                    generation = invalidate_sessions(record_id)
            else:
                username = values.get('username', '').strip()
                if not username or len(username) > 80:
                    raise ValueError('Tên đăng nhập là bắt buộc và tối đa 80 ký tự.')
                record_id = db.execute('INSERT INTO users(username,full_name,role,active,password_hash) VALUES(?,?,?,?,?)',
                                       (username, name, role, int(active), generate_password_hash(password))).lastrowid
            audit('Cập nhật quyền' if user else 'Cấp tài khoản', 'users', record_id, json.dumps({'role': role, 'active': active}, ensure_ascii=False))
            db.commit()
            if user and password and user['id'] == g.user['id']:
                session['auth_generation'] = generation
            flash('Đã lưu tài khoản.', 'success')
            return redirect(url_for('accounts'))
        except (ValueError, sqlite3.IntegrityError) as error:
            get_db().rollback()
            flash(str(error) if isinstance(error, ValueError) else 'Tên đăng nhập đã tồn tại.', 'error')
    return render_template('account_form.html', title='Chỉnh sửa tài khoản' if user else 'Cấp tài khoản mới', active='accounts', values=values, existing=user)
