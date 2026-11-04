"""M20: cấp tài khoản, chỉnh sửa thông tin và phân quyền."""
import json
import sqlite3

from flask import abort, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from .catalog import ROLES
from .common import one, query, require
from .db import audit, get_db


def accounts():
    require('admin')
    return render_template('accounts.html', title='Tài khoản & phân quyền', active='accounts', users=query('SELECT * FROM users ORDER BY id'),
                           logs=query('SELECT a.*,u.full_name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 100'))


def account_edit(record_id=None):
    require('admin')
    user = one('SELECT * FROM users WHERE id=?', (record_id,)) if record_id else None
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
            else:
                username = values.get('username', '').strip()
                if not username or len(username) > 80:
                    raise ValueError('Tên đăng nhập là bắt buộc và tối đa 80 ký tự.')
                record_id = db.execute('INSERT INTO users(username,full_name,role,active,password_hash) VALUES(?,?,?,?,?)',
                                       (username, name, role, int(active), generate_password_hash(password))).lastrowid
            audit('Cập nhật quyền' if user else 'Cấp tài khoản', 'users', record_id, json.dumps({'role': role, 'active': active}, ensure_ascii=False))
            db.commit()
            flash('Đã lưu tài khoản.', 'success')
            return redirect(url_for('accounts'))
        except (ValueError, sqlite3.IntegrityError) as error:
            get_db().rollback()
            flash(str(error) if isinstance(error, ValueError) else 'Tên đăng nhập đã tồn tại.', 'error')
    return render_template('account_form.html', title='Chỉnh sửa tài khoản' if user else 'Cấp tài khoản mới', active='accounts', values=values, existing=user)
