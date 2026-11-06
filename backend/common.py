"""Truy vấn và giới hạn dữ liệu theo quyền truy cập."""
from flask import abort, g

from database.connection import get_db

MANAGERS = ('admin', 'staff')


def query(sql, args=()):
    # Dấu ? trong SQL nhận giá trị từ args, tránh ghép trực tiếp dữ liệu người dùng vào SQL.
    # fetchall() trả về danh sách bản ghi; danh sách rỗng nếu không có kết quả.
    return get_db().execute(sql, args).fetchall()


def one(sql, args=()):
    # fetchone() lấy một bản ghi; trả về None nếu không tìm thấy.
    return get_db().execute(sql, args).fetchone()


def require(*roles):
    # *roles nhận nhiều vai trò được phép; abort(403) dừng yêu cầu vì thiếu quyền.
    if not g.user or g.user['role'] not in roles:
        abort(403)


def confirm_actor():
    """Recheck identity after acquiring a write lock or waiting for an external call."""
    user = one('''SELECT u.role,u.active,coalesce(v.generation,0) AS generation FROM users u
                  LEFT JOIN session_versions v ON v.user_id=u.id WHERE u.id=?''', (g.user['id'],))
    if not user or not user['active'] or user['role'] != g.user['role'] or user['generation'] != g.user['auth_generation']:
        abort(403, description='Quyền truy cập đã thay đổi. Thao tác chưa được lưu.')


def scope(table):
    """Return an SQL predicate + parameters against alias t; all table names are allowlisted."""
    # Trả về (điều kiện WHERE, danh sách tham số); t là tên viết tắt của bảng trong SQL.
    # Ví dụ: ('t.user_id=?', [4]) nghĩa là chỉ lấy các dòng có user_id bằng 4.
    role, uid = g.user['role'], g.user['id']
    if role in MANAGERS:
        # 1=1 luôn đúng: admin/cán bộ không bị lọc theo lớp hoặc hồ sơ cá nhân.
        return '1=1', []
    if table == 'students':
        if role == 'student':
            return 't.user_id=?', [uid]
        # EXISTS chỉ cho giảng viên thấy sinh viên có đăng ký lớp do mình phụ trách.
        return 'EXISTS (SELECT 1 FROM enrollments e JOIN classes c ON c.id=e.class_id WHERE e.student_id=t.id AND c.teacher_id=?)', [uid]
    if table == 'studies':
        # IN (SELECT ...) lọc quá trình học theo ID hồ sơ sinh viên mà người dùng được xem.
        if role == 'student':
            return 't.student_id IN (SELECT id FROM students WHERE user_id=?)', [uid]
        return 't.student_id IN (SELECT e.student_id FROM enrollments e JOIN classes c ON c.id=e.class_id WHERE c.teacher_id=?)', [uid]
    if table == 'classes':
        if role == 'teacher':
            return 't.teacher_id=?', [uid]
        return 't.id IN (SELECT e.class_id FROM enrollments e JOIN students s ON s.id=e.student_id WHERE s.user_id=?)', [uid]
    if table == 'enrollments':
        if role == 'teacher':
            return 't.class_id IN (SELECT id FROM classes WHERE teacher_id=?)', [uid]
        return 't.student_id IN (SELECT id FROM students WHERE user_id=?)', [uid]
    if table in ('resources', 'questions'):
        # Câu hỏi gắn với một học phần; học liệu có thể gắn nhiều học phần qua resource_subjects.
        subject = 't.subject_id' if table == 'questions' else 'rs.subject_id'
        enroll = f'{subject} IN (SELECT c.subject_id FROM classes c JOIN enrollments e ON e.class_id=c.id JOIN students s ON s.id=e.student_id WHERE s.user_id=?)'
        if table == 'resources':
            enroll = f'EXISTS (SELECT 1 FROM resource_subjects rs WHERE rs.resource_id=t.id AND {enroll})'
        if role == 'student':
            # Sinh viên chỉ thấy nội dung đã công bố và thuộc học phần mình đăng ký.
            return f"t.status='published' AND {enroll}", [uid]
        if table == 'questions':
            return ('(t.owner_id=? AND t.subject_id IN (SELECT subject_id FROM classes WHERE teacher_id=?)) '
                    'OR EXISTS (SELECT 1 FROM question_reviewers qr WHERE qr.subject_id=t.subject_id AND qr.user_id=?)'), [uid, uid, uid]
        # Giảng viên chỉ thấy học liệu do mình tạo và có TẤT CẢ học phần thuộc phạm vi phụ trách.
        return ('t.owner_id=? AND EXISTS (SELECT 1 FROM resource_subjects rs WHERE rs.resource_id=t.id) '
                'AND NOT EXISTS (SELECT 1 FROM resource_subjects rs WHERE rs.resource_id=t.id '
                'AND rs.subject_id NOT IN (SELECT subject_id FROM classes WHERE teacher_id=?))'), [uid, uid]
    return '1=1', []


def rows_for(table):
    condition, params = scope(table)
    # table phải do code/CATALOG kiểm soát; dấu ? chỉ thay được giá trị, không thay tên bảng.
    rows = query(f'SELECT t.* FROM {table} t WHERE {condition} ORDER BY t.id DESC', params)
    if table == 'enrollments' and g.user['role'] == 'student':
        # Che điểm chưa công bố ở dữ liệu gửi sang giao diện, không sửa điểm trong SQLite.
        return [dict(row, grade=row['grade'] if row['status'] == 'published' else None) for row in rows]
    return rows


def accessible(table, record_id):
    # Kiểm tra cả tồn tại lẫn phạm vi truy cập, kể cả khi người dùng tự gõ URL theo ID.
    row = one(f'SELECT * FROM {table} WHERE id=?', (record_id,))
    if not row:
        abort(404)
    condition, params = scope(table)
    # *params trải danh sách thành các phần tử để ghép sau record_id, đúng thứ tự dấu ? trong SQL.
    if not one(f'SELECT 1 FROM {table} t WHERE t.id=? AND ({condition})', [record_id, *params]):
        abort(403)
    return row


def can_edit(table):
    # Đây là quyền sửa theo vai trò; accessible() kiểm tra thêm quyền với bản ghi cụ thể.
    return g.user['role'] in MANAGERS or (g.user['role'] == 'teacher' and table in ('resources', 'questions'))


def options_for(key, active_only=False, current_id=None):
    if key in ('teachers', 'student_users'):
        role = 'teacher' if key == 'teachers' else 'student'
        users = query('SELECT id,full_name,username,active FROM users WHERE role=?', (role,))
        # Giữ lựa chọn hiện có dù tài khoản đã khóa để chỉnh sửa không làm mất liên kết cũ.
        return {str(r['id']): r['full_name'] + ' · ' + r['username'] + (' (đã khóa)' if not r['active'] else '')
                for r in users if not active_only or r['active'] or r['id'] == current_id}
    rows = rows_for(key)
    if key == 'subjects' and g.user['role'] == 'teacher':
        # Tập hợp {...} bỏ ID trùng; chỉ đưa học phần giảng viên phụ trách vào ô lựa chọn.
        assigned = {r[0] for r in query('SELECT subject_id FROM classes WHERE teacher_id=?', (g.user['id'],))}
        rows = [r for r in rows if r['id'] in assigned]
    # Tạo cặp 'ID dạng chuỗi' → 'nhãn hiển thị'; giá trị từ form HTML cũng là chuỗi.
    return {str(r['id']): ' · '.join(str(r[k]) for k in ('code', 'full_name', 'name', 'version') if k in r.keys()) for r in rows}
