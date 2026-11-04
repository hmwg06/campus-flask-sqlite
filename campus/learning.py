"""M10: học liệu, kiểm duyệt, tải tài liệu và luyện câu hỏi."""
from pathlib import Path

from flask import abort, current_app, flash, g, redirect, render_template, request, send_file, url_for

from .common import MANAGERS, accessible, options_for, require, rows_for
from .db import audit, get_db


def learning():
    q = request.args.get('q', '').strip().casefold()
    resources = [r for r in rows_for('resources') if q in (r['title'] + r['author']).casefold()]
    questions = rows_for('questions')
    return render_template('learning.html', title='Không gian học tập', active='learning', resources=resources,
                           questions=questions, subjects=options_for('subjects'), q=request.args.get('q', ''))


def publication(table, record_id, action):
    require(*MANAGERS)
    # URL động vẫn phải giới hạn tên bảng và hành động trước khi ghép tên bảng vào SQL.
    if table not in ('resources', 'questions') or action not in ('publish', 'archive'):
        abort(404)
    accessible(table, record_id)
    status = 'published' if action == 'publish' else 'archived'
    db = get_db()
    db.execute(f'UPDATE {table} SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?', (status, g.user['id'], record_id))
    audit('Công bố' if action == 'publish' else 'Lưu trữ', table, record_id)
    db.commit()
    flash('Đã cập nhật trạng thái kiểm duyệt.', 'success')
    return redirect(url_for('learning'))


def download(record_id):
    # Xác nhận quyền trước khi lấy file hoặc chuyển tới liên kết học liệu.
    row = accessible('resources', record_id)
    db = get_db()
    db.execute('INSERT INTO activity(user_id,resource_id) VALUES(?,?)', (g.user['id'], record_id))
    db.commit()
    if row['stored_name']:
        path = Path(current_app.config['UPLOAD_FOLDER']) / row['stored_name']
        if not path.is_file():
            abort(404)
        # Gửi file dưới dạng tải xuống, dùng tên gốc thay vì tên ngẫu nhiên trên ổ đĩa.
        return send_file(path, as_attachment=True, download_name=row['original_name'])
    if row['url']:
        return redirect(row['url'])
    abort(404)


def answer_question(record_id):
    require('student')
    question = accessible('questions', record_id)
    selected = request.form.get('answer', '')
    # Chỉ nhận đúng một ký tự A/B/C/D; chuỗi rỗng cũng cần bị loại dù '' in 'ABCD' là True.
    if selected not in 'ABCD' or len(selected) != 1:
        abort(400)
    flash('Chính xác!' if selected == question['answer'] else 'Chưa chính xác. Hãy xem lại bài học và thử lại.', 'success' if selected == question['answer'] else 'error')
    return redirect(url_for('learning'))
