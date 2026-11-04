"""Danh sách và biểu mẫu thêm/sửa dùng chung cho các mục quản lý."""
import json
import math
import secrets
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from .catalog import CATALOG
from .common import accessible, can_edit, options_for, query, rows_for
from .db import audit, get_db


def fields_for(table, existing=None, for_edit=False):
    fields = []
    for original in CATALOG[table]['fields']:
        # Sao chép trước khi thêm choices để không sửa cấu hình CATALOG dùng chung.
        field = dict(original)
        if field['kind'] in ('relation', 'multi'):
            current_id = existing[field['name']] if existing and field['kind'] == 'relation' else None
            field['choices'] = options_for(field['options'], active_only=for_edit, current_id=current_id)
        elif field['kind'] == 'select':
            field['choices'] = field['options']
        fields.append(field)
    return fields


def validate(fields):
    # Kiểm tra lại ở server: dữ liệu POST có thể được gửi trực tiếp, bỏ qua form HTML.
    data = {}
    for field in fields:
        name, kind = field['name'], field['kind']
        if kind == 'file':
            # Tệp nằm trong request.files, được kiểm tra và lưu riêng ở edit_record().
            continue
        value = request.form.get(name, '').strip()
        if kind == 'multi':
            # getlist() đọc nhiều giá trị cùng tên; dict.fromkeys() bỏ trùng, giữ thứ tự.
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
            # Chuyển ID từ chuỗi sang số; None được sqlite3 lưu thành NULL khi không chọn liên kết.
            value = int(value) if value else None
        if kind in ('number', 'decimal'):
            try:
                value = (int(value) if kind == 'number' else float(value)) if value else None
            except ValueError:
                raise ValueError(field['label'] + ' phải là số.') from None
            maximum = 10 if name == 'grade' else 20 if name == 'semester' else 30
            # isfinite() loại NaN/vô cực; điểm cho phép 0, học kỳ và số tín chỉ bắt đầu từ 1.
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
                # Kiểm tra ngày dạng năm-tháng-ngày và loại ngày không tồn tại, như 2026-02-30.
                date.fromisoformat(value)
            except ValueError:
                raise ValueError('Ngày không hợp lệ.') from None
        data[name] = value
    return data


def listing(table):
    # CATALOG là danh sách bảng được phép; chặn tên bảng lạ lấy từ URL.
    if table not in CATALOG:
        abort(404)
    if table == 'questions' and g.user['role'] == 'student':
        return redirect(url_for('learning'))
    rows = rows_for(table)
    search = request.args.get('q', '').strip().casefold()
    fields = [f for f in fields_for(table) if f['kind'] not in ('file', 'multi', 'textarea')]
    rendered = []
    for row in rows:
        cells = []
        for f in fields:
            value = row[f['name']]
            if f['kind'] in ('relation', 'select'):
                # Đổi ID/mã trạng thái thành nhãn dễ đọc; dùng dấu — nếu thiếu nhãn tương ứng.
                value = f['choices'].get(str(value), '—')
            cells.append('—' if value is None or value == '' else str(value))
        if search in ' '.join(cells).casefold():
            rendered.append(dict(id=row['id'], cells=cells))
    return render_template('listing.html', title=CATALOG[table]['title'], active=CATALOG[table]['module'],
                           table=table, fields=fields, rows=rendered, editable=can_edit(table), q=request.args.get('q', ''))


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
        # Giữ lại dữ liệu vừa nhập để hiển thị lại form nếu kiểm tra hoặc lưu thất bại.
        values = request.form.to_dict()
        values['subject_ids'] = request.form.getlist('subject_ids')
        saved_path = None
        try:
            data = validate(fields)
            if table == 'enrollments' and data['status'] == 'published' and data['grade'] is None:
                raise ValueError('Cần nhập điểm trước khi công bố.')
            if existing and table in ('students', 'studies') and data['status'] != existing['status'] and not request.form.get('reason', '').strip():
                raise ValueError('Hãy nhập căn cứ thay đổi trạng thái.')
            # pop() lấy và bỏ subject_ids khỏi data: đây là liên kết nhiều học phần, không phải cột resources.
            subject_ids = data.pop('subject_ids', [])
            if table in ('resources', 'questions'):
                # Nội dung đã sửa phải được duyệt lại; xóa dấu xác nhận công bố trước đó.
                data.update(status='draft', reviewed_by=None, reviewed_at=None)
                if not existing:
                    data['owner_id'] = g.user['id']
                if table == 'questions' and existing:
                    data['version'] = existing['version'] + 1
            if table == 'resources':
                upload = request.files.get('file')
                if upload and upload.filename:
                    # Chuẩn hóa tên file để loại thành phần đường dẫn và ký tự không phù hợp.
                    filename = secure_filename(upload.filename)
                    # Chuẩn hóa đuôi file sang chữ thường trước khi so với danh sách cho phép.
                    # Đây là kiểm tra phần mở rộng, không phải kiểm tra toàn bộ nội dung file.
                    suffix = Path(filename).suffix.lower()
                    if suffix not in {'.pdf', '.txt', '.docx', '.pptx', '.xlsx', '.png', '.jpg', '.jpeg'}:
                        raise ValueError('Định dạng tệp không được hỗ trợ.')
                    folder = Path(current_app.config['UPLOAD_FOLDER'])
                    folder.mkdir(parents=True, exist_ok=True)
                    # Tên lưu ngẫu nhiên tránh trùng file; original_name dùng khi tải xuống.
                    data['stored_name'] = secrets.token_hex(20) + suffix
                    data['original_name'] = filename
                    saved_path = folder / data['stored_name']
                    upload.save(saved_path)
                if not data['url'] and not data.get('stored_name') and not (existing and existing['stored_name']):
                    raise ValueError('Hãy tải lên tệp hoặc nhập đường dẫn học liệu.')
            db = get_db()
            # Tên cột lấy từ cấu hình đã kiểm tra; các giá trị vẫn truyền riêng qua dấu ?.
            if existing:
                # join tạo phần SET, ví dụ 'code=?,name=?'; data.values() cung cấp giá trị cùng thứ tự.
                db.execute(f"UPDATE {table} SET {','.join(k+'=?' for k in data)} WHERE id=?", [*data.values(), record_id])
            else:
                # lastrowid là ID vừa được SQLite cấp, dùng cho liên kết và nhật ký.
                record_id = db.execute(f"INSERT INTO {table} ({','.join(data)}) VALUES ({','.join('?' for _ in data)})", list(data.values())).lastrowid
            if table == 'resources':
                # Thay danh sách học phần liên kết; mọi thay đổi này sẽ commit cùng bản ghi chính.
                db.execute('DELETE FROM resource_subjects WHERE resource_id=?', (record_id,))
                db.executemany('INSERT INTO resource_subjects VALUES(?,?)', [(record_id, sid) for sid in subject_ids])
            # Lưu trước/sau để tra cứu lịch sử; ensure_ascii=False giữ tiếng Việt dễ đọc trong JSON.
            detail = json.dumps({'before': dict(existing) if existing else None, 'after': data, 'reason': request.form.get('reason', '')[:1000], 'subjects': subject_ids}, ensure_ascii=False)
            audit('Cập nhật' if existing else 'Tạo mới', table, record_id, detail)
            # Chỉ commit sau khi lưu xong bản ghi, liên kết học phần và nhật ký.
            db.commit()
            flash('Đã lưu dữ liệu.' + (' Nội dung được đưa về bản nháp để kiểm duyệt.' if table in ('resources', 'questions') else ''), 'success')
            # Chuyển về trang danh sách sau POST để tải lại trang không gửi lại yêu cầu lưu.
            return redirect(url_for('listing', table=table))
        except (ValueError, sqlite3.IntegrityError) as error:
            # IntegrityError thường do trùng mã hoặc sai khóa ngoại; hủy phần ghi chưa thành công.
            get_db().rollback()
            if saved_path:
                # File không thuộc giao dịch SQL nên phải tự xóa file vừa tải khi lưu thất bại.
                saved_path.unlink(missing_ok=True)
            flash(str(error) if isinstance(error, ValueError) else 'Mã hoặc liên kết đã tồn tại, hoặc dữ liệu liên quan không hợp lệ.', 'error')
    return render_template('form.html', title=('Chỉnh sửa · ' if existing else 'Thêm mới · ') + CATALOG[table]['title'],
                           active=CATALOG[table]['module'], fields=fields, values=values, table=table, existing=existing)
