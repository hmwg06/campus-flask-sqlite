"""Trang tổng quan và thống kê nhanh."""
from flask import g, render_template

from .common import MANAGERS, options_for, query, rows_for


def dashboard():
    # len(rows_for(...)) đếm trong phạm vi được xem, không lấy tổng dữ liệu của mọi người.
    # [:5] lấy tối đa 5 lớp để hiển thị gọn trên trang tổng quan.
    return render_template('dashboard.html', title='Tổng quan', active='dashboard',
                           counts={key: len(rows_for(key)) for key in ('students', 'classes', 'resources', 'questions')},
                           classes=rows_for('classes')[:5], subject_names=options_for('subjects'),
                           recent=query('SELECT a.*,u.full_name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 6') if g.user['role'] in MANAGERS else [])
