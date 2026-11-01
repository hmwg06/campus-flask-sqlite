import io
import tempfile
import unittest
from pathlib import Path

from app import create_app
from campus.db import get_db, seed_demo


class CampusTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'DATABASE': str(Path(self.temp.name) / 'test.db'),
                               'UPLOAD_FOLDER': str(Path(self.temp.name) / 'uploads'), 'SECRET_KEY': 'test'})
        with self.app.app_context():
            seed_demo('Campus123!')
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, data=None):
        self.client.get('/login')
        with self.client.session_transaction() as session:
            token = session['csrf_token']
        return self.client.post(path, data={**(data or {}), 'csrf_token': token}, follow_redirects=True)

    def login(self, username='admin'):
        return self.post('/login', {'username': username, 'password': 'Campus123!'})

    def test_login_csrf_and_all_pages(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        self.assertEqual(self.client.post('/login', data={}).status_code, 400)
        self.assertIn('không đúng', self.post('/login', {'username': 'admin', 'password': 'bad'}).text)
        self.login()
        for path in ['/', '/students', '/training', '/learning', '/reports', '/accounts',
                     '/records/programs', '/records/subjects', '/records/classes', '/records/enrollments',
                     '/records/resources', '/records/questions', '/records/programs/new']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_student_scope_and_permissions(self):
        self.login('student')
        page = self.client.get('/students').text
        self.assertIn('Nguyễn Minh Anh', page)
        self.assertNotIn('Trần Quốc Bảo', page)
        self.assertEqual(self.client.get('/accounts').status_code, 403)
        self.assertEqual(self.client.get('/records/students/new').status_code, 403)
        self.assertEqual(self.client.get('/students/2').status_code, 403)
        self.assertEqual(self.post('/records/programs/new', {'code': 'X', 'name': 'X'}).status_code, 403)
        self.assertEqual(self.client.get('/reports/export').status_code, 403)

    def test_validated_create_and_persistence(self):
        self.login()
        payload = {'code': 'NEW', 'name': 'Chương trình mới', 'version': '2026', 'description': 'Test'}
        self.assertEqual(self.post('/records/programs/new', payload).status_code, 200)
        self.assertIn('đã tồn tại', self.post('/records/programs/new', payload).text)
        self.assertIn('bắt buộc', self.post('/records/programs/new', {'code': ''}).text)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT count(*) FROM programs WHERE code='NEW'").fetchone()[0], 1)

    def test_review_and_grade_visibility(self):
        self.login('teacher')
        self.assertEqual(self.post('/resources/1/publish').status_code, 403)
        self.assertEqual(self.post('/questions/1/publish').status_code, 403)
        self.post('/logout')
        self.login('student')
        self.assertNotIn('Câu hỏi bản nháp', self.client.get('/learning').text)
        self.assertEqual(self.client.get('/resources/1/download').status_code, 403)
        self.post('/logout')
        self.login()
        self.post('/questions/1/publish')
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT status FROM questions WHERE id=1').fetchone()[0], 'published')

    def test_account_revocation_and_last_admin(self):
        self.login()
        response = self.post('/accounts/1/edit', {'full_name': 'Admin', 'role': 'student', 'active': '0'})
        self.assertIn('quản trị viên', response.text)
        with self.app.app_context():
            get_db().execute("UPDATE users SET active=0 WHERE username='student'")
            get_db().commit()
        self.post('/logout')
        self.assertIn('không đúng', self.login('student').text)

    def test_upload_and_csv(self):
        self.login()
        payload = {'title': 'Tài liệu kiểm thử', 'subject_ids': '1', 'author': 'Test', 'source': 'Nội bộ',
                   'version': '1', 'license': 'Nội bộ', 'url': '', 'file': (io.BytesIO(b'%PDF-1.4 test'), 'lesson.pdf')}
        self.assertEqual(self.post('/records/resources/new', payload).status_code, 200)
        with self.app.app_context():
            row = get_db().execute("SELECT * FROM resources WHERE title='Tài liệu kiểm thử'").fetchone()
            self.assertTrue(row['stored_name'])
        response = self.client.get('/reports/export')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response.content_type)

    def test_all_forms_and_role_pages(self):
        from campus.catalog import CATALOG
        self.login()
        for table in CATALOG:
            for suffix in ('new', '1/edit'):
                with self.subTest(table=table, suffix=suffix):
                    self.assertEqual(self.client.get(f'/records/{table}/{suffix}').status_code, 200)
        for path in ['/students/1', '/accounts/1/edit', '/accounts/new', '/password', '/missing']:
            self.assertEqual(self.client.get(path).status_code, 404 if path == '/missing' else 200)
        for role in ['staff', 'teacher', 'student']:
            self.post('/logout')
            self.login(role)
            for path in ['/', '/students', '/training', '/learning', '/records/classes', '/records/enrollments', '/students/1']:
                with self.subTest(role=role, path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)

    def test_grade_validation_publication_and_history(self):
        self.login()
        data = {'student_id': '1', 'class_id': '1', 'grade': 'NaN', 'status': 'published'}
        self.assertIn('khoảng cho phép', self.post('/records/enrollments/1/edit', data).text)
        data.update(grade='9.7', status='draft')
        self.post('/records/enrollments/1/edit', data)
        self.post('/logout')
        self.login('student')
        self.assertNotIn('9.7', self.client.get('/students/1').text)
        self.post('/logout')
        self.login()
        data['status'] = 'published'
        self.post('/records/enrollments/1/edit', data)
        student = {'code': 'SV2026001', 'full_name': 'Nguyễn Minh Anh', 'cohort': 'K2026', 'email': '', 'user_id': '4', 'status': 'paused'}
        self.assertIn('căn cứ', self.post('/records/students/1/edit', student).text)
        self.post('/records/students/1/edit', {**student, 'reason': 'Quyết định 123'})
        self.assertIn('Quyết định 123', self.client.get('/students/1').text)
        self.post('/logout')
        self.login('student')
        self.assertIn('9.7', self.client.get('/students/1').text)

    def test_cross_class_access_and_resource_edit_resets_review(self):
        self.login('teacher')
        with self.app.app_context():
            get_db().execute("UPDATE classes SET teacher_id=1 WHERE id=2")
            get_db().commit()
        self.assertEqual(self.client.get('/records/classes/2/edit').status_code, 403)
        payload = {'subject_id': '2', 'prompt': 'Invalid class', 'choice_a': 'A', 'choice_b': 'B',
                   'choice_c': 'C', 'choice_d': 'D', 'answer': 'A', 'source': 'Test'}
        self.assertIn('không hợp lệ', self.post('/records/questions/new', payload).text)
        self.post('/logout')
        self.login('student')
        with self.app.app_context():
            get_db().execute('DELETE FROM enrollments WHERE student_id=1 AND class_id=2')
            get_db().commit()
        self.assertEqual(self.client.get('/resources/2/download').status_code, 403)
        self.post('/logout')
        self.login()
        self.post('/resources/1/publish')
        payload = {'title': 'Revised', 'subject_ids': '1', 'author': 'Test', 'source': 'Test', 'version': '2', 'license': 'Test', 'url': 'https://example.com'}
        self.post('/records/resources/1/edit', payload)
        with self.app.app_context():
            row = get_db().execute('SELECT * FROM resources WHERE id=1').fetchone()
            self.assertEqual(row['status'], 'draft')
            self.assertIsNone(row['reviewed_by'])

    def test_active_session_revocation_and_malicious_upload(self):
        self.login('student')
        with self.app.app_context():
            get_db().execute('UPDATE users SET active=0 WHERE id=4')
            get_db().commit()
        self.assertEqual(self.client.get('/students').status_code, 302)
        self.login()
        payload = {'title': 'Unsafe', 'subject_ids': '1', 'author': 'Test', 'source': 'Test',
                   'version': '1', 'license': 'Test', 'file': (io.BytesIO(b'<script></script>'), 'evil.html')}
        self.assertIn('không được hỗ trợ', self.post('/records/resources/new', payload).text)
        with self.app.app_context():
            self.assertIsNone(get_db().execute("SELECT id FROM resources WHERE title='Unsafe'").fetchone())

    def test_reopening_database_and_csv_formula_protection(self):
        with self.app.app_context():
            get_db().execute("UPDATE classes SET code='=1+1' WHERE id=1")
            get_db().commit()
        reopened = create_app(self.app.config)
        with reopened.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM students').fetchone()[0], 2)
        self.login()
        self.assertIn("'=1+1", self.client.get('/reports/export').text)

    def test_first_run_setup(self):
        clean = create_app({'TESTING': True, 'DATABASE': str(Path(self.temp.name) / 'empty.db'), 'SECRET_KEY': 'test'})
        client = clean.test_client()
        self.assertIn('Khởi tạo hệ thống', client.get('/', follow_redirects=True).text)
        with client.session_transaction() as session:
            token = session['csrf_token']
        response = client.post('/setup', data={'csrf_token': token, 'username': 'owner', 'full_name': 'Owner', 'password': 'Strong123!'}, follow_redirects=True)
        self.assertIn('Đã tạo quản trị viên', response.text)
        self.assertEqual(client.get('/setup').status_code, 302)

    def test_revoked_teacher_subject_loses_content_access(self):
        self.login('teacher')
        with self.app.app_context():
            get_db().execute('UPDATE classes SET teacher_id=1 WHERE id=1')
            get_db().commit()
        self.assertEqual(self.client.get('/resources/1/download').status_code, 403)
        self.assertEqual(self.client.get('/records/questions/1/edit').status_code, 403)
        self.assertEqual(self.client.get('/records/resources/1/edit').status_code, 403)

    def test_inactive_account_links_preserved_on_edit(self):
        self.login()
        with self.app.app_context():
            get_db().execute('UPDATE users SET active=0 WHERE id IN (3,4)')
            get_db().commit()
        html = self.client.get('/records/students/1/edit').text
        self.assertIn('value="4" selected', html)
        payload = {'code': 'SV2026001', 'full_name': 'Nguyễn Minh Anh', 'cohort': 'K2026', 'status': 'studying', 'user_id': '4', 'email': ''}
        self.post('/records/students/1/edit', payload)
        payload = {'code': 'IT101-01', 'subject_id': '1', 'teacher_id': '3', 'term': 'HK2', 'schedule': ''}
        self.post('/records/classes/1/edit', payload)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT user_id FROM students WHERE id=1').fetchone()[0], 4)
            self.assertEqual(get_db().execute('SELECT term FROM classes WHERE id=1').fetchone()[0], 'HK2')


if __name__ == '__main__':
    unittest.main()
