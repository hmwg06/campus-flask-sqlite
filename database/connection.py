"""Kết nối SQLite, khởi tạo bảng và ghi nhật ký."""
import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db():
    # g lưu dữ liệu trong ngữ cảnh Flask hiện tại; tái sử dụng kết nối thay vì mở nhiều lần.
    if 'db' not in g:
        # current_app cung cấp đường dẫn database của môi trường đang chạy.
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        # Cho phép đọc cột bằng tên, ví dụ row['full_name'], thay vì chỉ dùng row[1].
        g.db.row_factory = sqlite3.Row
        # SQLite phải bật khóa ngoại trên từng kết nối để kiểm tra liên kết giữa các bảng.
        g.db.execute('PRAGMA foreign_keys=ON')
        # Chờ tối đa 5.000 ms khi database đang bị kết nối khác khóa, rồi mới báo lỗi.
        g.db.execute('PRAGMA busy_timeout=5000')
    return g.db


def init_db():
    # Chạy các lệnh CREATE TABLE IF NOT EXISTS trong schema.sql; không reset dữ liệu cũ.
    get_db().executescript((Path(__file__).resolve().parent / 'schema.sql').read_text(encoding='utf-8'))


def audit(action, entity, record_id, detail=''):
    # Lưu người thực hiện, thao tác và bản ghi bị thay đổi; hàm gọi sẽ commit cùng dữ liệu.
    user = getattr(g, 'user', None)
    get_db().execute('INSERT INTO audit(user_id,action,entity,record_id,detail) VALUES(?,?,?,?,?)',
                     (user['id'] if user else None, action, entity, record_id, detail))


def invalidate_sessions(user_id):
    """Tăng phiên bản đăng nhập trong cùng giao dịch với thay đổi mật khẩu."""
    db = get_db()
    db.execute('''INSERT INTO session_versions(user_id,generation) VALUES(?,1)
                  ON CONFLICT(user_id) DO UPDATE SET generation=generation+1''', (user_id,))
    return db.execute('SELECT generation FROM session_versions WHERE user_id=?', (user_id,)).fetchone()[0]


def close_db(error=None):
    # pop() lấy kết nối và bỏ nó khỏi g; callback chạy cả khi xử lý yêu cầu bị lỗi.
    db = g.pop('db', None)
    if db:
        db.close()
