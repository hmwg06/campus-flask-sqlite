"""AI drafting/review endpoints. AI output never decides publication or permissions."""
import json
import time

from flask import abort, current_app, flash, g, redirect, render_template, request, url_for

from database.connection import audit, get_db
from . import ai_client
from .common import accessible, confirm_actor, one, options_for, require


def begin_request(operation):
    if not current_app.config.get('OPENAI_API_KEY', '').strip():
        raise ai_client.AIError('Chưa cấu hình OPENAI_API_KEY trên máy chủ. Vui lòng liên hệ quản trị viên.')
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    confirm_actor()
    interval = current_app.config['AI_MIN_INTERVAL_SECONDS']
    now = int(time.time())
    if one('SELECT 1 FROM ai_requests WHERE user_id=? AND created_at>?', (g.user['id'], now - interval)):
        db.rollback()
        raise ai_client.AIError(f'Vui lòng chờ ít nhất {interval} giây giữa hai yêu cầu AI.')
    db.execute('INSERT INTO ai_requests(user_id,operation,created_at) VALUES(?,?,?)', (g.user['id'], operation, now))
    db.commit()


def generate():
    require('admin', 'staff', 'teacher')
    values = request.form.to_dict() if request.method == 'POST' else {}
    subjects = options_for('subjects', active_only=True)
    if request.method == 'POST':
        try:
            subject_id = values.get('subject_id', '')
            if subject_id not in subjects:
                abort(403)
            topic = values.get('topic', '').strip()
            source = values.get('source', '').strip()
            reference = values.get('reference', '').strip()
            difficulty = values.get('difficulty', '')
            try:
                count = int(values.get('count', ''))
            except ValueError:
                raise ai_client.AIError('Số câu phải là số nguyên từ 1 đến 10.') from None
            if not 1 <= count <= 10 or difficulty not in ('basic', 'intermediate', 'advanced'):
                raise ai_client.AIError('Chọn độ khó hợp lệ và số câu từ 1 đến 10.')
            if not 1 <= len(topic) <= 300 or not 1 <= len(source) <= 300 or not 20 <= len(reference) <= 20000:
                raise ai_client.AIError('Nhập chủ đề và nguồn tối đa 300 ký tự; nội dung tham khảo từ 20 đến 20.000 ký tự.')
            begin_request('generate')
            result, model = ai_client.generate_questions(subjects[subject_id], topic, difficulty, count, reference)
            db = get_db()
            db.execute('BEGIN IMMEDIATE')
            confirm_actor()
            if subject_id not in options_for('subjects', active_only=True):
                abort(403)
            ids = []
            for draft in result.questions:
                record_id = db.execute('''INSERT INTO questions
                    (subject_id,prompt,choice_a,choice_b,choice_c,choice_d,answer,source,owner_id,status)
                    VALUES(?,?,?,?,?,?,?,?,?,'draft')''',
                    (int(subject_id), draft.prompt, draft.choice_a, draft.choice_b, draft.choice_c,
                     draft.choice_d, draft.answer, source, g.user['id'])).lastrowid
                db.execute('''INSERT INTO question_ai_metadata
                    (question_id,question_version,model,reference_text,instructions,explanation) VALUES(?,1,?,?,?,?)''',
                    (record_id, model, reference, json.dumps({'topic':topic,'difficulty':difficulty}, ensure_ascii=False), draft.explanation))
                audit('AI hỗ trợ tạo bản nháp', 'questions', record_id, json.dumps({'model':model}))
                ids.append(record_id)
            db.commit()
            flash(f'Đã lưu {len(ids)} câu hỏi ở trạng thái nháp. Cần kiểm duyệt chuyên môn trước khi sử dụng.', 'success')
            return redirect(url_for('learning', _anchor='questions'))
        except ai_client.AIError as error:
            get_db().rollback()
            flash(str(error), 'error')
    return render_template('ai_questions.html', title='Soạn câu hỏi với OpenAI', active='learning',
                           subjects=subjects, values=values, ai_ready=bool(current_app.config.get('OPENAI_API_KEY')),
                           model=current_app.config['OPENAI_MODEL'])


def review(record_id):
    require('admin', 'staff', 'teacher')
    question = accessible('questions', record_id)
    if request.form.get('version') != str(question['version']):
        flash('Câu hỏi đã thay đổi. Hãy tải lại trang trước khi rà soát bằng AI.', 'error')
        return redirect(url_for('review_question', record_id=record_id))
    reference = request.form.get('reference', '').strip()
    if len(reference) > 20000:
        abort(400, description='Tài liệu tham khảo tối đa 20.000 ký tự.')
    subject = one('SELECT name FROM subjects WHERE id=?', (question['subject_id'],))
    try:
        begin_request('review')
        payload = {key:question[key] for key in ('prompt','choice_a','choice_b','choice_c','choice_d','answer','source')}
        result, model = ai_client.analyze_question(payload, subject['name'], reference)
        db = get_db()
        db.execute('BEGIN IMMEDIATE')
        confirm_actor()
        current = accessible('questions', record_id)
        if current['version'] != question['version']:
            db.rollback()
            flash('Câu hỏi đã đổi phiên bản trong khi AI xử lý. Kết quả cũ không được lưu.', 'error')
        else:
            db.execute('''INSERT INTO question_ai_reviews
                (question_id,question_version,user_id,model,reference_text,result_json) VALUES(?,?,?,?,?,?)''',
                (record_id, question['version'], g.user['id'], model, reference, result.model_dump_json()))
            audit('AI hỗ trợ rà soát', 'questions', record_id, json.dumps({'version':question['version'],'model':model}))
            db.commit()
            flash('Đã lưu nhận xét AI. Người kiểm duyệt cần xác minh trước khi quyết định.', 'success')
    except ai_client.AIError as error:
        get_db().rollback()
        flash(str(error), 'error')
    return redirect(url_for('review_question', record_id=record_id))
