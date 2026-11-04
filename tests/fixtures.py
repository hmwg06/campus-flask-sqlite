"""Dữ liệu kiểm thử chỉ dùng với SQLite tạm, không phải lệnh của website."""
from flask import current_app
from werkzeug.security import generate_password_hash
from campus.db import get_db


def create_test_records(password):
    if not current_app.testing:
        raise RuntimeError("Test fixtures require TESTING=True")
    db = get_db()
    if db.execute('SELECT 1 FROM users').fetchone():
        raise ValueError('Cơ sở dữ liệu đã có tài khoản; không thêm dữ liệu mẫu để tránh trộn dữ liệu.')
    for username, name, role in [('admin', 'Quản trị hệ thống', 'admin'), ('staff', 'Phòng đào tạo', 'staff'),
                                  ('teacher', 'TS. Lê Hoàng Nam', 'teacher'), ('student', 'Nguyễn Minh Anh', 'student')]:
        db.execute('INSERT INTO users(username,full_name,password_hash,role) VALUES(?,?,?,?)',
                   (username, name, generate_password_hash(password), role))
    db.execute("INSERT INTO programs(code,name,version,description) VALUES('CNTT','Công nghệ thông tin','2026','Chương trình cử nhân Công nghệ thông tin')")
    db.execute("INSERT INTO programs(code,name,version,description) VALUES('QTKD','Quản trị kinh doanh','2026','Chương trình cử nhân Quản trị kinh doanh')")
    db.execute("INSERT INTO subjects(code,name,credits,description) VALUES('IT101','Nhập môn lập trình',3,'Tư duy lập trình và Python')")
    db.execute("INSERT INTO subjects(code,name,credits,description) VALUES('IT202','Cơ sở dữ liệu',3,'Mô hình quan hệ và SQL')")
    db.execute('INSERT INTO curriculum(program_id,subject_id,semester) VALUES(1,1,1),(1,2,2)')
    db.execute("INSERT INTO students(code,full_name,email,cohort,status,user_id) VALUES('SV2026001','Nguyễn Minh Anh','minhanh@example.edu','K2026','studying',4)")
    db.execute("INSERT INTO students(code,full_name,email,cohort,status) VALUES('SV2026002','Trần Quốc Bảo','quocbao@example.edu','K2026','studying')")
    db.execute("INSERT INTO studies(student_id,program_id,start_date,status) VALUES(1,1,'2026-09-01','studying'),(2,1,'2026-09-01','studying')")
    db.execute("INSERT INTO classes(code,subject_id,teacher_id,term,schedule) VALUES('IT101-01',1,3,'HK1 · 2026–2027','Thứ 2 • 07:30–10:00'),('IT202-01',2,3,'HK1 · 2026–2027','Thứ 4 • 13:30–16:00')")
    db.execute("INSERT INTO enrollments(student_id,class_id,grade,status) VALUES(1,1,8.5,'published'),(2,1,NULL,'draft'),(1,2,NULL,'draft')")
    db.execute("INSERT INTO resources(title,author,source,version,license,url,owner_id,status) VALUES('Bài giảng Python – bản nháp','Lê Hoàng Nam','Biên soạn nội bộ','1.0','Chỉ dùng nội bộ','https://docs.python.org/3/tutorial/',3,'draft')")
    db.execute("INSERT INTO resources(title,author,source,version,license,url,owner_id,status,reviewed_by,reviewed_at) VALUES('Tài liệu SQL cơ bản','SQLite','SQLite documentation','1.0','Theo điều khoản nguồn','https://www.sqlite.org/lang.html',3,'published',1,CURRENT_TIMESTAMP)")
    db.execute('INSERT INTO resource_subjects VALUES(1,1),(2,2)')
    db.execute("INSERT INTO questions(subject_id,prompt,choice_a,choice_b,choice_c,choice_d,answer,source,owner_id) VALUES(1,'Câu hỏi bản nháp: Kiểu dữ liệu nào lưu số nguyên?','int','str','list','dict','A','Biên soạn nội bộ',3)")
    db.commit()
