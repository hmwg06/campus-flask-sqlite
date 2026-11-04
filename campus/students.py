"""M03: danh sách sinh viên, hồ sơ và kết quả học tập."""
from flask import render_template

from .common import accessible, options_for, query, rows_for
from .records import listing


def students():
    # Tái sử dụng trang danh sách chung, với cấu hình cột lấy từ CATALOG['students'].
    return listing('students')


def student_detail(record_id):
    student = accessible('students', record_id)
    # JOIN ghép quá trình theo học với chương trình để lấy tên và phiên bản thay vì chỉ có ID.
    studies = query('SELECT s.*,p.name,p.version FROM studies s JOIN programs p ON p.id=s.program_id WHERE s.student_id=?', (record_id,))
    enrollments = [r for r in rows_for('enrollments') if r['student_id'] == record_id]
    history = query("SELECT a.*,u.full_name FROM audit a LEFT JOIN users u ON u.id=a.user_id WHERE a.entity='students' AND a.record_id=? ORDER BY a.id DESC", (record_id,))
    return render_template('student.html', title=student['full_name'], active='students', student=student, studies=studies,
                           enrollments=enrollments, class_names=options_for('classes'), history=history)
