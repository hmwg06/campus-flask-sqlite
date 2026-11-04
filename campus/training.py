"""M04: tổng quan đào tạo và danh sách giảng viên."""
from flask import render_template, request

from .common import options_for, query, rows_for


def training():
    # teacher_names ánh xạ ID tài khoản giảng viên sang họ tên để hiển thị trong bảng lớp.
    return render_template('training.html', title='Quản lý đào tạo', active='training',
                           counts={key: len(rows_for(key)) for key in ('programs', 'subjects', 'classes', 'enrollments')},
                           classes=rows_for('classes'), subject_names=options_for('subjects'),
                           teacher_names={str(r['id']): r['full_name'] for r in query("SELECT id,full_name FROM users WHERE role='teacher'")})


def lecturers():
    # request.args đọc tham số sau dấu ?, ví dụ ?q=Nguyễn; casefold() tìm không phân biệt hoa/thường.
    search = request.args.get('q', '').strip().casefold()
    department = request.args.get('department', '').strip()
    all_rows = query('SELECT * FROM lecturers ORDER BY department,full_name')
    # Kết hợp hai bộ lọc: đúng đơn vị nếu đã chọn và chứa từ tìm kiếm trong thông tin giảng viên.
    rows = [row for row in all_rows if (not department or row['department'] == department)
            and search in ' '.join(row[key] for key in ('full_name', 'academic_title', 'department', 'position')).casefold()]
    return render_template('lecturers.html', title='Giảng viên NEU', active='training', rows=rows,
                           q=request.args.get('q', ''), department=department,
                           departments=sorted({row['department'] for row in all_rows}))
