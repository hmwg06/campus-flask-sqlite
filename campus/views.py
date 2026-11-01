import csv
import io
import json
import math
import secrets
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from .catalog import CATALOG, ROLES, STATUS
from .db import audit, get_db

bp = Blueprint('web', __name__)
MANAGERS = ('admin', 'staff')


def query(sql, args=()):
    return get_db().execute(sql, args).fetchall()


def one(sql, args=()):
    return get_db().execute(sql, args).fetchone()


def require(*roles):
    if not g.user or g.user['role'] not in roles:
        abort(403)


@bp.before_app_request
def authenticate():
    session.setdefault('csrf_token', secrets.token_hex(32))
    g.user = one('SELECT * FROM users WHERE id=? AND active=1', (session.get('user_id'),))
    if request.method == 'POST':
        if not secrets.compare_digest(session['csrf_token'], request.form.get('csrf_token', '')):
            abort(400, description='Phiên biểu mẫu đã hết hạn. Vui lòng tải lại trang rồi thử lại.')
    if request.endpoint and request.endpoint not in ('web.login', 'web.setup', 'static') and not g.user:
        return redirect(url_for('web.login'))


@bp.after_app_request
def secure_response(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'self'; base-uri 'self'"
    if request.endpoint != 'static':
        response.headers['Cache-Control'] = 'no-store'
    return response


@bp.app_context_processor
def context():
    return dict(roles=ROLES, statuses=STATUS, catalog=CATALOG, manager=g.user and g.user['role'] in MANAGERS,
                csrf_token=session.get('csrf_token'), today=date.today().strftime('%d/%m/%Y'))


@bp.app_errorhandler(400)
@bp.app_errorhandler(403)
@bp.app_errorhandler(404)
@bp.app_errorhandler(413)
def error_page(error):
    return render_template('error.html', error=error, title='Không thể thực hiện yêu cầu'), error.code


@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if one('SELECT 1 FROM users'):
        return redirect(url_for('web.login'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        name = request.form.get('full_name', '').strip()
        if not username or not name or len(username) > 80 or len(name) > 160 or not 8 <= len(password) <= 256:
            flash('Điền đầy đủ thông tin. Mật khẩu cần từ 8 đến 256 ký tự.', 'error')
        else:
            db = get_db()
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM users').fetchone():
                db.rollback()
                return redirect(url_for('web.login'))
            db.execute("INSERT INTO users(username,full_name,password_hash,role) VALUES(?,?,?,'admin')", (username, name, generate_password_hash(password)))
            db.commit()
            flash('Đã tạo quản trị viên. Bạn có thể đăng nhập.', 'success')
            return redirect(url_for('web.login'))
    return render_template('login.html', setup=True, title='Khởi tạo hệ thống')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if not one('SELECT 1 FROM users'):
        return redirect(url_for('web.setup'))
    if request.method == 'POST':
        user = one('SELECT * FROM users WHERE username=? AND active=1', (request.form.get('username', '').strip(),))
        password = request.form.get('password', '')
        if user and len(password) <= 256 and check_password_hash(user['password_hash'], password):
            session.clear()
            session.update(user_id=user['id'], csrf_token=secrets.token_hex(32))
            return redirect(url_for('web.dashboard'))
        flash('Tên đăng nhập hoặc mật khẩu không đúng, hoặc tài khoản đã bị khóa.', 'error')
    return render_template('login.html', title='Đăng nhập')


@bp.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('web.login'))


def scope(table):
    """Return an SQL predicate + parameters against alias t; all table names are allowlisted."""
    role, uid = g.user['role'], g.user['id']
    if role in MANAGERS:
        return '1=1', []
    if table == 'students':
        if role == 'student':
            return 't.user_id=?', [uid]
        return 'EXISTS (SELECT 1 FROM enrollments e JOIN classes c ON c.id=e.class_id WHERE e.student_id=t.id AND c.teacher_id=?)', [uid]
    if table == 'studies':
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
        subject = 't.subject_id' if table == 'questions' else 'rs.subject_id'
        enroll = f'{subject} IN (SELECT c.subject_id FROM classes c JOIN enrollments e ON e.class_id=c.id JOIN students s ON s.id=e.student_id WHERE s.user_id=?)'
        if table == 'resources':
            enroll = f'EXISTS (SELECT 1 FROM resource_subjects rs WHERE rs.resource_id=t.id AND {enroll})'
        if role == 'student':
            return f"t.status='published' AND {enroll}", [uid]
        if table == 'questions':
            return 't.owner_id=? AND t.subject_id IN (SELECT subject_id FROM classes WHERE teacher_id=?)', [uid, uid]
        return ('t.owner_id=? AND EXISTS (SELECT 1 FROM resource_subjects rs WHERE rs.resource_id=t.id) '
                'AND NOT EXISTS (SELECT 1 FROM resource_subjects rs WHERE rs.resource_id=t.id '
                'AND rs.subject_id NOT IN (SELECT subject_id FROM classes WHERE teacher_id=?))'), [uid, uid]
    return '1=1', []


def rows_for(table):
    condition, params = scope(table)
    rows = query(f'SELECT t.* FROM {table} t WHERE {condition} ORDER BY t.id DESC', params)
    if table == 'enrollments' and g.user['role'] == 'student':
        return [dict(row, grade=row['grade'] if row['status'] == 'published' else None) for row in rows]
    return rows


def accessible(table, record_id):
    row = one(f'SELECT * FROM {table} WHERE id=?', (record_id,))
    if not row:
        abort(404)
    condition, params = scope(table)
    if not one(f'SELECT 1 FROM {table} t WHERE t.id=? AND ({condition})', [record_id, *params]):
        abort(403)
    return row


def can_edit(table):
    return g.user['role'] in MANAGERS or (g.user['role'] == 'teacher' and table in ('resources', 'questions'))


def options_for(key, active_only=False, current_id=None):
    if key in ('teachers', 'student_users'):
        role = 'teacher' if key == 'teachers' else 'student'
        users = query('SELECT id,full_name,username,active FROM users WHERE role=?', (role,))
        return {str(r['id']): r['full_name'] + ' · ' + r['username'] + (' (đã khóa)' if not r['active'] else '')
                for r in users if not active_only or r['active'] or r['id'] == current_id}
    rows = rows_for(key)
    if key == 'subjects' and g.user['role'] == 'teacher':
        assigned = {r[0] for r in query('SELECT subject_id FROM classes WHERE teacher_id=?', (g.user['id'],))}
        rows = [r for r in rows if r['id'] in assigned]
    return {str(r['id']): ' · '.join(str(r[k]) for k in ('code', 'full_name', 'name', 'version') if k in r.keys()) for r in rows}


def fields_for(table, existing=None, for_edit=False):
    fields = []
    for original in CATALOG[table]['fields']:
        field = dict(original)
        if field['kind'] in ('relation', 'multi'):
            current_id = existing[field['name']] if existing and field['kind'] == 'relation' else None
            field['choices'] = options_for(field['options'], active_only=for_edit, current_id=current_id)
        elif field['kind'] == 'select':
            field['choices'] = field['options']
        fields.append(field)
    return fields


@bp.get('/')
def dashboard():
    return render_template('dashboard.html', title='Tổng quan', active='dashboard',
                           counts={key: len(rows_for(key)) for key in ('students', 'classes', 'resources', 'questions')},
                           classes=rows_for('classes')[:5], subject_names=options_for('subjects'),
                           recent=query('SELECT a.*,u.full_name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 6') if g.user['role'] in MANAGERS else [])


@bp.get('/students')
def students():
    return listing('students')


@bp.get('/students/<int:record_id>')
def student_detail(record_id):
    student = accessible('students', record_id)
    studies = query('SELECT s.*,p.name,p.version FROM studies s JOIN programs p ON p.id=s.program_id WHERE s.student_id=?', (record_id,))
    enrollments = [r for r in rows_for('enrollments') if r['student_id'] == record_id]
    history = query("SELECT a.*,u.full_name FROM audit a LEFT JOIN users u ON u.id=a.user_id WHERE a.entity='students' AND a.record_id=? ORDER BY a.id DESC", (record_id,))
    return render_template('student.html', title=student['full_name'], active='students', student=student, studies=studies,
                           enrollments=enrollments, class_names=options_for('classes'), history=history)


@bp.get('/training')
def training():
    return render_template('training.html', title='Quản lý đào tạo', active='training',
                           counts={key: len(rows_for(key)) for key in ('programs', 'subjects', 'classes', 'enrollments')},
                           classes=rows_for('classes'), subject_names=options_for('subjects'),
                           teacher_names={str(r['id']): r['full_name'] for r in query("SELECT id,full_name FROM users WHERE role='teacher'")})


@bp.get('/learning')
def learning():
    q = request.args.get('q', '').strip().casefold()
    resources = [r for r in rows_for('resources') if q in (r['title'] + r['author']).casefold()]
    questions = rows_for('questions')
    return render_template('learning.html', title='Không gian học tập', active='learning', resources=resources,
                           questions=questions, subjects=options_for('subjects'), q=request.args.get('q', ''))


@bp.get('/records/<table>')
def listing(table):
    if table not in CATALOG:
        abort(404)
    if table == 'questions' and g.user['role'] == 'student':
        return redirect(url_for('web.learning'))
    rows = rows_for(table)
    search = request.args.get('q', '').strip().casefold()
    fields = [f for f in fields_for(table) if f['kind'] not in ('file', 'multi', 'textarea')]
    rendered = []
    for row in rows:
        cells = []
        for f in fields:
            value = row[f['name']]
            if f['kind'] in ('relation', 'select'):
                value = f['choices'].get(str(value), '—')
            cells.append('—' if value is None or value == '' else str(value))
        if search in ' '.join(cells).casefold():
            rendered.append(dict(id=row['id'], cells=cells))
    return render_template('listing.html', title=CATALOG[table]['title'], active=CATALOG[table]['module'],
                           table=table, fields=fields, rows=rendered, editable=can_edit(table), q=request.args.get('q', ''))


def validate(fields):
    data = {}
    for field in fields:
        name, kind = field['name'], field['kind']
        if kind == 'file':
            continue
        value = request.form.get(name, '').strip()
        if kind == 'multi':
            values = list(dict.fromkeys(request.form.getlist(name)))
            if not values or any(v not in field['choices'] for v in values):
                raise ValueError('Hãy chọn ít nhất một học phần được phép.')
            data[name] = [int(v) for v in values]
            continue
        if field['required'] and not value:
            raise ValueError(field['label'] + ' là bắt buộc.')
        if len(value) > (5000 if kind == 'textarea' else 500):
            raise ValueError(field['label'] + ' quá dài.')
        if value and kind in ('relation', 'select') and value not in field['choices']:
            raise ValueError(field['label'] + ' không hợp lệ hoặc không được phép.')
        if kind == 'relation':
            value = int(value) if value else None
        if kind in ('number', 'decimal'):
            try:
                value = (int(value) if kind == 'number' else float(value)) if value else None
            except ValueError:
                raise ValueError(field['label'] + ' phải là số.') from None
            maximum = 10 if name == 'grade' else 20 if name == 'semester' else 30
            if value is not None and (not math.isfinite(value) or not (0 if name == 'grade' else 1) <= value <= maximum):
                raise ValueError(field['label'] + ' nằm ngoài khoảng cho phép.')
        if value and kind == 'url':
            parsed = urlsplit(value)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                raise ValueError('Đường dẫn phải bắt đầu bằng http:// hoặc https://.')
        if value and kind == 'email' and ('@' not in value or '.' not in value.rsplit('@', 1)[-1]):
            raise ValueError('Email không hợp lệ.')
        if value and kind == 'date':
            try:
                date.fromisoformat(value)
            except ValueError:
                raise ValueError('Ngày không hợp lệ.') from None
        data[name] = value
    return data


@bp.route('/records/<table>/new', methods=['GET', 'POST'])
@bp.route('/records/<table>/<int:record_id>/edit', methods=['GET', 'POST'])
def edit_record(table, record_id=None):
    if table not in CATALOG:
        abort(404)
    if not can_edit(table):
        abort(403)
    existing = accessible(table, record_id) if record_id else None
    fields = fields_for(table, existing, for_edit=True)
    values = dict(existing) if existing else {}
    if existing and table == 'resources':
        values['subject_ids'] = [str(r[0]) for r in query('SELECT subject_id FROM resource_subjects WHERE resource_id=?', (record_id,))]
    if request.method == 'POST':
        values = request.form.to_dict()
        values['subject_ids'] = request.form.getlist('subject_ids')
        saved_path = None
        try:
            data = validate(fields)
            if table == 'enrollments' and data['status'] == 'published' and data['grade'] is None:
                raise ValueError('Cần nhập điểm trước khi công bố.')
            if existing and table in ('students', 'studies') and data['status'] != existing['status'] and not request.form.get('reason', '').strip():
                raise ValueError('Hãy nhập căn cứ thay đổi trạng thái.')
            subject_ids = data.pop('subject_ids', [])
            if table in ('resources', 'questions'):
                data.update(status='draft', reviewed_by=None, reviewed_at=None)
                if not existing:
                    data['owner_id'] = g.user['id']
                if table == 'questions' and existing:
                    data['version'] = existing['version'] + 1
            if table == 'resources':
                upload = request.files.get('file')
                if upload and upload.filename:
                    filename = secure_filename(upload.filename)
                    suffix = Path(filename).suffix.lower()
                    if suffix not in {'.pdf', '.txt', '.docx', '.pptx', '.xlsx', '.png', '.jpg', '.jpeg'}:
                        raise ValueError('Định dạng tệp không được hỗ trợ.')
                    folder = Path(current_app.config['UPLOAD_FOLDER'])
                    folder.mkdir(parents=True, exist_ok=True)
                    data['stored_name'] = secrets.token_hex(20) + suffix
                    data['original_name'] = filename
                    saved_path = folder / data['stored_name']
                    upload.save(saved_path)
                if not data['url'] and not data.get('stored_name') and not (existing and existing['stored_name']):
                    raise ValueError('Hãy tải lên tệp hoặc nhập đường dẫn học liệu.')
            db = get_db()
            if existing:
                db.execute(f"UPDATE {table} SET {','.join(k+'=?' for k in data)} WHERE id=?", [*data.values(), record_id])
            else:
                record_id = db.execute(f"INSERT INTO {table} ({','.join(data)}) VALUES ({','.join('?' for _ in data)})", list(data.values())).lastrowid
            if table == 'resources':
                db.execute('DELETE FROM resource_subjects WHERE resource_id=?', (record_id,))
                db.executemany('INSERT INTO resource_subjects VALUES(?,?)', [(record_id, sid) for sid in subject_ids])
            detail = json.dumps({'before': dict(existing) if existing else None, 'after': data, 'reason': request.form.get('reason', '')[:1000], 'subjects': subject_ids}, ensure_ascii=False)
            audit('Cập nhật' if existing else 'Tạo mới', table, record_id, detail)
            db.commit()
            flash('Đã lưu dữ liệu.' + (' Nội dung được đưa về bản nháp để kiểm duyệt.' if table in ('resources', 'questions') else ''), 'success')
            return redirect(url_for('web.listing', table=table))
        except (ValueError, sqlite3.IntegrityError) as error:
            get_db().rollback()
            if saved_path:
                saved_path.unlink(missing_ok=True)
            flash(str(error) if isinstance(error, ValueError) else 'Mã hoặc liên kết đã tồn tại, hoặc dữ liệu liên quan không hợp lệ.', 'error')
    return render_template('form.html', title=('Chỉnh sửa · ' if existing else 'Thêm mới · ') + CATALOG[table]['title'],
                           active=CATALOG[table]['module'], fields=fields, values=values, table=table, existing=existing)


@bp.post('/<table>/<int:record_id>/<action>')
def publication(table, record_id, action):
    require(*MANAGERS)
    if table not in ('resources', 'questions') or action not in ('publish', 'archive'):
        abort(404)
    accessible(table, record_id)
    status = 'published' if action == 'publish' else 'archived'
    db = get_db()
    db.execute(f'UPDATE {table} SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?', (status, g.user['id'], record_id))
    audit('Công bố' if action == 'publish' else 'Lưu trữ', table, record_id)
    db.commit()
    flash('Đã cập nhật trạng thái kiểm duyệt.', 'success')
    return redirect(url_for('web.learning'))


@bp.get('/resources/<int:record_id>/download')
def download(record_id):
    row = accessible('resources', record_id)
    db = get_db()
    db.execute('INSERT INTO activity(user_id,resource_id) VALUES(?,?)', (g.user['id'], record_id))
    db.commit()
    if row['stored_name']:
        path = Path(current_app.config['UPLOAD_FOLDER']) / row['stored_name']
        if not path.is_file():
            abort(404)
        return send_file(path, as_attachment=True, download_name=row['original_name'])
    if row['url']:
        return redirect(row['url'])
    abort(404)


@bp.post('/questions/<int:record_id>/answer')
def answer_question(record_id):
    require('student')
    question = accessible('questions', record_id)
    selected = request.form.get('answer', '')
    if selected not in 'ABCD' or len(selected) != 1:
        abort(400)
    flash('Chính xác!' if selected == question['answer'] else 'Chưa chính xác. Hãy xem lại bài học và thử lại.', 'success' if selected == question['answer'] else 'error')
    return redirect(url_for('web.learning'))


def report_data():
    require(*MANAGERS)
    return query("""SELECT c.code,s.name,c.term,count(e.id) AS students,
                    sum(CASE WHEN e.status='published' THEN 1 ELSE 0 END) AS published,
                    round(avg(CASE WHEN e.status='published' THEN e.grade END),2) AS average
                    FROM classes c JOIN subjects s ON s.id=c.subject_id LEFT JOIN enrollments e ON e.class_id=c.id
                    GROUP BY c.id ORDER BY c.code""")


@bp.get('/reports')
def reports():
    rows = report_data()
    return render_template('reports.html', title='Báo cáo & đánh giá', active='reports', rows=rows,
                           generated=datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC'),
                           activities=query('SELECT r.title,count(a.id) AS views FROM resources r LEFT JOIN activity a ON a.resource_id=r.id GROUP BY r.id ORDER BY views DESC'),
                           reviews=one("SELECT count(*) AS total,round(avg((julianday(reviewed_at)-julianday(created_at))*24),2) AS hours FROM resources WHERE reviewed_at IS NOT NULL"))


@bp.get('/reports/export')
def export_report():
    rows = report_data()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Mã lớp', 'Học phần', 'Học kỳ', 'Số đăng ký', 'Đã công bố', 'Điểm trung bình đã công bố'])
    for row in rows:
        writer.writerow([("'" + str(v)) if str(v).lstrip().startswith(('=', '+', '-', '@')) else v for v in row])
    return Response('\ufeff' + output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=bao-cao-dao-tao.csv'})


@bp.get('/accounts')
def accounts():
    require('admin')
    return render_template('accounts.html', title='Tài khoản & phân quyền', active='accounts', users=query('SELECT * FROM users ORDER BY id'),
                           logs=query('SELECT a.*,u.full_name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 100'))


@bp.route('/accounts/new', methods=['GET', 'POST'])
@bp.route('/accounts/<int:record_id>/edit', methods=['GET', 'POST'])
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
            if user and user['id'] == g.user['id'] and (role != 'admin' or active != '1'):
                raise ValueError('Không thể tự khóa hoặc hạ quyền quản trị viên đang đăng nhập.')
            if user and user['role'] != role:
                if one('SELECT 1 FROM students WHERE user_id=?', (record_id,)) and role != 'student':
                    raise ValueError('Tài khoản đang liên kết hồ sơ sinh viên; hãy gỡ liên kết trước khi đổi vai trò.')
                if one('SELECT 1 FROM classes WHERE teacher_id=?', (record_id,)) and role != 'teacher':
                    raise ValueError('Tài khoản đang phụ trách lớp; hãy phân công lại trước khi đổi vai trò.')
            if (not user or password) and not 8 <= len(password) <= 256:
                raise ValueError('Mật khẩu cần từ 8 đến 256 ký tự.')
            db = get_db()
            db.execute('BEGIN IMMEDIATE')
            if user and user['role'] == 'admin' and (role != 'admin' or active == '0'):
                if one("SELECT count(*) AS n FROM users WHERE role='admin' AND active=1")['n'] <= 1:
                    raise ValueError('Phải giữ lại ít nhất một quản trị viên hoạt động.')
            if user:
                db.execute('UPDATE users SET full_name=?,role=?,active=? WHERE id=?', (name, role, int(active), record_id))
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
            return redirect(url_for('web.accounts'))
        except (ValueError, sqlite3.IntegrityError) as error:
            get_db().rollback()
            flash(str(error) if isinstance(error, ValueError) else 'Tên đăng nhập đã tồn tại.', 'error')
    return render_template('account_form.html', title='Chỉnh sửa tài khoản' if user else 'Cấp tài khoản mới', active='accounts', values=values, existing=user)


@bp.route('/password', methods=['GET', 'POST'])
def password():
    if request.method == 'POST':
        old, new = request.form.get('old_password', ''), request.form.get('password', '')
        if len(old) > 256 or not check_password_hash(g.user['password_hash'], old):
            flash('Mật khẩu hiện tại không đúng.', 'error')
        elif not 8 <= len(new) <= 256 or new != request.form.get('confirm_password'):
            flash('Mật khẩu mới cần 8–256 ký tự và hai lần nhập phải giống nhau.', 'error')
        else:
            get_db().execute('UPDATE users SET password_hash=? WHERE id=?', (generate_password_hash(new), g.user['id']))
            audit('Đổi mật khẩu', 'users', g.user['id'])
            get_db().commit()
            flash('Đã đổi mật khẩu.', 'success')
            return redirect(url_for('web.dashboard'))
    return render_template('password.html', title='Đổi mật khẩu')
