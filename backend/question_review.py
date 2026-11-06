"""Human subject-review assignments and version-bound publication decisions."""
import json

from flask import abort, current_app, flash, g, redirect, render_template, request, url_for

from database.connection import audit, get_db
from .common import accessible, confirm_actor, one, query, require


def can_review(question):
    return bool(g.user and g.user['role'] in ('admin', 'staff', 'teacher')
                and g.user['id'] != question['owner_id']
                and one('SELECT 1 FROM question_reviewers WHERE subject_id=? AND user_id=?',
                        (question['subject_id'], g.user['id'])))


def assignments():
    require('admin')
    if request.method == 'POST':
        try:
            subject_id = int(request.form.get('subject_id', ''))
            user_id = int(request.form.get('user_id', ''))
        except ValueError:
            abort(400)
        action = request.form.get('action')
        if action not in ('assign', 'remove'):
            abort(400)
        db = get_db()
        db.execute('BEGIN IMMEDIATE')
        confirm_actor()
        if not one('SELECT 1 FROM subjects WHERE id=?', (subject_id,)):
            abort(404)
        if action == 'assign':
            if not one("SELECT 1 FROM users WHERE id=? AND active=1 AND role IN ('admin','staff','teacher')", (user_id,)):
                abort(400, description='Chọn tài khoản chuyên môn đang hoạt động.')
            db.execute('INSERT OR IGNORE INTO question_reviewers(subject_id,user_id,assigned_by) VALUES(?,?,?)',
                       (subject_id, user_id, g.user['id']))
        else:
            db.execute('DELETE FROM question_reviewers WHERE subject_id=? AND user_id=?', (subject_id, user_id))
        audit('Phân công kiểm duyệt' if action == 'assign' else 'Gỡ phân công kiểm duyệt', 'subjects', subject_id,
              json.dumps({'reviewer_id': user_id}))
        db.commit()
        flash('Đã cập nhật phân công kiểm duyệt chuyên môn.', 'success')
        return redirect(url_for('question_reviewers'))
    return render_template('question_reviewers.html', title='Phân công kiểm duyệt', active='learning',
                           subjects=query('SELECT id,code,name FROM subjects ORDER BY name'),
                           users=query("SELECT id,full_name,username,role FROM users WHERE active=1 AND role IN ('admin','staff','teacher') ORDER BY full_name"),
                           assignments=query('''SELECT r.*,s.name AS subject_name,u.full_name,u.username,u.active
                                FROM question_reviewers r JOIN subjects s ON s.id=r.subject_id
                                JOIN users u ON u.id=r.user_id ORDER BY s.name,u.full_name'''))


def review(record_id):
    require('admin', 'staff', 'teacher')
    db = get_db()
    if request.method == 'POST':
        db.execute('BEGIN IMMEDIATE')
        confirm_actor()
    question = accessible('questions', record_id)
    if request.method == 'POST':
        if not can_review(question):
            abort(403, description='Cần được phân công kiểm duyệt học phần và không phải người tạo câu hỏi.')
        if request.form.get('version') != str(question['version']):
            db.rollback()
            flash('Câu hỏi đã thay đổi. Vui lòng đọc lại phiên bản mới trước khi quyết định.', 'error')
            return redirect(url_for('review_question', record_id=record_id))
        decision = request.form.get('decision')
        notes = request.form.get('notes', '').strip()
        if decision not in ('approve', 'revise') or not 10 <= len(notes) <= 2000 or request.form.get('confirmed') != '1':
            db.rollback()
            flash('Cần xác nhận đã kiểm tra chuyên môn và ghi nhận xét từ 10 đến 2.000 ký tự.', 'error')
            return redirect(url_for('review_question', record_id=record_id))
        db.execute('INSERT INTO question_reviews(question_id,question_version,reviewer_id,decision,notes) VALUES(?,?,?,?,?)',
                   (record_id, question['version'], g.user['id'], decision, notes))
        if decision == 'approve':
            db.execute("UPDATE questions SET status='published',reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",
                       (g.user['id'], record_id))
        else:
            db.execute("UPDATE questions SET status='draft',reviewed_by=NULL,reviewed_at=NULL WHERE id=?", (record_id,))
        audit('Duyệt chuyên môn & công bố' if decision == 'approve' else 'Yêu cầu chỉnh sửa câu hỏi', 'questions', record_id,
              json.dumps({'version': question['version'], 'notes': notes}, ensure_ascii=False))
        db.commit()
        flash('Đã duyệt và công bố câu hỏi.' if decision == 'approve' else 'Câu hỏi đã được đưa về nháp để chỉnh sửa.', 'success')
        return redirect(url_for('review_question', record_id=record_id))
    metadata = one('SELECT * FROM question_ai_metadata WHERE question_id=?', (record_id,))
    analyses = [dict(row, result=json.loads(row['result_json'])) for row in query('''
        SELECT a.*,u.full_name FROM question_ai_reviews a JOIN users u ON u.id=a.user_id
        WHERE a.question_id=? ORDER BY a.id DESC LIMIT 10''', (record_id,))]
    history = query('''SELECT r.*,u.full_name FROM question_reviews r JOIN users u ON u.id=r.reviewer_id
                       WHERE r.question_id=? ORDER BY r.id DESC LIMIT 20''', (record_id,))
    reviewers = query('''SELECT u.full_name FROM question_reviewers r JOIN users u ON u.id=r.user_id
                        WHERE r.subject_id=? AND u.active=1 AND u.role IN ('admin','staff','teacher')''', (question['subject_id'],))
    return render_template('question_review.html', title='Rà soát & kiểm duyệt câu hỏi', active='learning',
                           question=question, subject=one('SELECT name FROM subjects WHERE id=?', (question['subject_id'],)),
                           metadata=metadata, analyses=analyses, history=history, reviewers=reviewers,
                           may_review=can_review(question), may_edit=g.user['role'] in ('admin','staff') or question['owner_id']==g.user['id'],
                           ai_ready=bool(current_app.config.get('OPENAI_API_KEY')))
