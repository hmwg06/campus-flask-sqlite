"""Add a clearly labelled sample dataset without replacing existing records.

Run: .venv/Scripts/python.exe seed_data.py
New demo accounts use random passwords; an administrator can set passwords in UI.
"""
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app
from werkzeug.security import generate_password_hash

from app import app
from campus.db import get_db


STUDENTS = [
    'Nguyễn Minh Anh', 'Trần Quốc Bảo', 'Lê Hoàng Phúc', 'Phạm Ngọc Linh',
    'Hoàng Thu Hà', 'Vũ Đức Huy', 'Đặng Khánh Vy', 'Bùi Gia Hân',
    'Đỗ Tuấn Kiệt', 'Ngô Thanh Trúc', 'Dương Hải Nam', 'Đinh Thảo Nguyên',
]
SUBJECTS = [
    ('PY', 'Lập trình Python', 3, 0, 0, 'Biến và kiểu dữ liệu',
     'Biến dùng để đặt tên cho giá trị. Python có các kiểu int, float, str và bool.\nBài tập: nhập họ tên, năm sinh và in lời chào. Không dùng dữ liệu cá nhân thật khi thực hành.'),
    ('DB', 'Cơ sở dữ liệu', 3, 0, 0, 'Bảng và khóa chính',
     'Cơ sở dữ liệu quan hệ lưu dữ liệu theo bảng. Khóa chính xác định duy nhất mỗi dòng.\nBài tập: thiết kế bảng sinh viên gồm mã, tên và khóa học; đề xuất khóa chính phù hợp.'),
    ('WEB', 'Phát triển ứng dụng web', 3, 0, 1, 'Cấu trúc trang HTML',
     'HTML mô tả nội dung và cấu trúc trang. CSS trình bày giao diện. JavaScript hỗ trợ tương tác.\nBài tập: tạo trang giới thiệu học phần có tiêu đề, danh sách và biểu mẫu.'),
    ('STAT', 'Thống kê ứng dụng', 3, 1, 1, 'Trung bình cộng',
     'Trung bình cộng bằng tổng giá trị chia cho số quan sát. Luôn ghi rõ tập dữ liệu được tính.\nBài tập: tính trung bình của 6, 7, 8, 9 và diễn giải kết quả.'),
    ('MGT', 'Nguyên lý quản trị', 3, 1, 2, 'Lập kế hoạch công việc',
     'Kế hoạch cần nêu mục tiêu, công việc, người phụ trách, thời hạn và cách đánh giá.\nBài tập: lập kế hoạch cho một buổi sinh hoạt câu lạc bộ với kinh phí giả định.'),
    ('MKT', 'Marketing căn bản', 2, 1, 2, 'Tìm hiểu nhu cầu khách hàng',
     'Trước khi đề xuất sản phẩm cần xác định nhóm khách hàng và vấn đề họ muốn giải quyết.\nBài tập: soạn năm câu hỏi khảo sát nhu cầu cho một dịch vụ học tập giả định.'),
]
QUESTIONS = [
    ('Kiểu dữ liệu nào thường biểu diễn số nguyên trong Python?', ['int', 'str', 'list', 'dict'], 'A'),
    ('Khóa chính có mục đích gì?', ['Trang trí bảng', 'Xác định duy nhất một dòng', 'Thay thế mọi cột', 'Ẩn dữ liệu'], 'B'),
    ('Ngôn ngữ nào mô tả cấu trúc trang web?', ['SQL', 'CSS', 'HTML', 'CSV'], 'C'),
    ('Trung bình cộng của 6, 7, 8 và 9 là bao nhiêu?', ['6', '7', '8', '7.5'], 'D'),
    ('Một kế hoạch công việc cần có yếu tố nào?', ['Mục tiêu và thời hạn', 'Chỉ tên dự án', 'Chỉ hình ảnh', 'Không cần người phụ trách'], 'A'),
    ('Khảo sát khách hàng giúp làm rõ điều gì?', ['Màu của máy tính', 'Nhu cầu của nhóm khách hàng', 'Mã nguồn website', 'Tốc độ mạng nội bộ'], 'B'),
]


def populate_sample_data():
    db = get_db()
    created_files = []
    db.execute('BEGIN IMMEDIATE')
    try:
        if db.execute("SELECT 1 FROM audit WHERE entity='demo_seed' AND record_id=1").fetchone():
            db.rollback()
            return {'already_seeded': True}
        if not db.execute("SELECT 1 FROM users WHERE role='admin' AND active=1").fetchone():
            raise ValueError('Hãy tạo tài khoản quản trị trước khi thêm bộ dữ liệu này.')
        for table, column, pattern in [('users', 'username', 'demo.%'), ('students', 'code', 'DEMO-%'),
                                       ('programs', 'code', 'DEMO-%'), ('subjects', 'code', 'DEMO-%'),
                                       ('classes', 'code', 'DEMO-%')]:
            if db.execute(f'SELECT 1 FROM {table} WHERE {column} LIKE ?', (pattern,)).fetchone():
                raise ValueError('Đã có mã DEMO hoặc tài khoản demo; dừng để không trộn dữ liệu.')

        counts = {}

        def insert(table, **data):
            cursor = db.execute(f"INSERT INTO {table} ({','.join(data)}) VALUES ({','.join('?' for _ in data)})", list(data.values()))
            counts[table] = counts.get(table, 0) + 1
            return cursor.lastrowid

        def account(username, name, role):
            return insert('users', username=username, full_name=name + ' (Mẫu)', role=role,
                          password_hash=generate_password_hash(secrets.token_urlsafe(32)))

        account('demo.staff', 'Cán bộ Phòng đào tạo', 'staff')
        teachers = [account('demo.teacher' + str(i + 1), name, 'teacher') for i, name in enumerate(
            ['Lê Hoàng Nam', 'Trần Thu Hương', 'Nguyễn Đức Thành'])]
        programs = [insert('programs', code=code, name=name + ' (Mẫu)', version='2026',
                           description='Chương trình minh họa để thử nghiệm, không phải quy định đào tạo chính thức.')
                    for code, name in [('DEMO-CNTT', 'Công nghệ thông tin'), ('DEMO-QTKD', 'Quản trị kinh doanh')]]
        subjects, classes, resources = [], [], []
        folder = Path(current_app.config['UPLOAD_FOLDER'])
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        for i, (code, name, credits, program, teacher, lesson, body) in enumerate(SUBJECTS):
            subject = insert('subjects', code='DEMO-' + code, name=name + ' (Mẫu)', credits=credits,
                             description='Học phần minh họa. ' + lesson + '.')
            subjects.append(subject)
            insert('curriculum', program_id=programs[program], subject_id=subject, semester=1 + i % 2)
            classes.append(insert('classes', code='DEMO-' + code + '-01', subject_id=subject,
                                  teacher_id=teachers[teacher], term='HK1 · 2026–2027 (Mẫu)',
                                  schedule=f'Thứ {2 + i % 5} · ' + ('07:30–10:00' if i % 2 == 0 else '13:30–16:00')))
            filename = 'demo-' + secrets.token_hex(16) + '.txt'
            path = folder / filename
            created_files.append(path)
            path.write_text('HỌC LIỆU MẪU — KHÔNG PHẢI TÀI LIỆU CHÍNH THỨC\n\n' + name + '\n' + lesson + '\n\n' + body + '\n', encoding='utf-8')
            status = 'draft' if i == 5 else 'published'
            resource = insert('resources', title='[DEMO] ' + lesson, author=['Lê Hoàng Nam', 'Trần Thu Hương', 'Nguyễn Đức Thành'][teacher] + ' (nhân vật mẫu)',
                              source='Nội dung minh họa tự biên soạn cho bộ dữ liệu mẫu', version='1.0',
                              license='Tài liệu mẫu dùng cho thử nghiệm nội bộ', stored_name=filename,
                              original_name=code.lower() + '-bai-hoc-mau.txt', owner_id=teachers[teacher],
                              status=status, reviewed_at=timestamp if status == 'published' else None)
            resources.append(resource)
            insert('resource_subjects', resource_id=resource, subject_id=subject)
            prompt, answers, answer = QUESTIONS[i]
            insert('questions', subject_id=subject, prompt='[DEMO] ' + prompt, choice_a=answers[0], choice_b=answers[1],
                   choice_c=answers[2], choice_d=answers[3], answer=answer, source='Câu hỏi mẫu tự biên soạn',
                   owner_id=teachers[teacher], status=status, reviewed_at=timestamp if status == 'published' else None)
        # Demonstrate shared learning resources and a student in two programs.
        insert('resource_subjects', resource_id=resources[0], subject_id=subjects[1])
        for i, name in enumerate(STUDENTS):
            user = account(f'demo.student{i + 1:02}', name, 'student')
            status = 'paused' if i == 10 else 'studying'
            student = insert('students', code=f'DEMO-SV{i + 1:03}', full_name=name + ' (Mẫu)',
                             email=f'demo.student{i + 1:02}@example.invalid', cohort='K2026', status=status, user_id=user)
            program = 0 if i < 6 else 1
            insert('studies', student_id=student, program_id=programs[program], start_date='2026-09-01', status=status)
            if i == 0:
                insert('studies', student_id=student, program_id=programs[1], start_date='2026-10-01', status='studying')
            for j in range(program * 3, program * 3 + 3):
                published = j % 3 != 2 and status == 'studying'
                insert('enrollments', student_id=student, class_id=classes[j],
                       grade=round(5.5 + ((i * 7 + j * 3) % 45) / 10, 1) if published else None,
                       status='published' if published else 'draft')
            # Sample analytics, confined to demo students and their published resources.
            for j in range(program * 3, program * 3 + 2):
                insert('activity', user_id=user, resource_id=resources[j])
        db.execute("INSERT INTO audit(action,entity,record_id,detail) VALUES(?,?,?,?)",
                   ('Nạp dữ liệu mẫu', 'demo_seed', 1, json.dumps({'note': 'Tất cả bản ghi DEMO, điểm, trạng thái kiểm duyệt và hoạt động trong lô này là dữ liệu mô phỏng; không đại diện hoạt động thực tế.', 'added': counts}, ensure_ascii=False)))
        db.commit()
        return counts
    except Exception:
        db.rollback()
        for path in created_files:
            path.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    with app.app_context():
        db = get_db()
        if not db.execute("SELECT 1 FROM audit WHERE entity='demo_seed' AND record_id=1").fetchone():
            backup = Path(app.instance_path) / 'backups'
            backup.mkdir(exist_ok=True)
            destination = backup / ('before-sample-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
            with sqlite3.connect(destination) as target:
                db.backup(target)
            print('Backup:', destination)
        print(json.dumps(populate_sample_data(), ensure_ascii=True, indent=2))
        print('Integrity:', db.execute('PRAGMA integrity_check').fetchone()[0])
        print('Foreign-key errors:', len(db.execute('PRAGMA foreign_key_check').fetchall()))
