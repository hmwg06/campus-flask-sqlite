import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash
from app import create_app
from campus.db import get_db
from seed_data import populate_sample_data


class SampleDataTest(unittest.TestCase):
    def test_sample_data_preserves_admin_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'DATABASE': str(Path(temp) / 'db.sqlite3'),
                              'UPLOAD_FOLDER': str(Path(temp) / 'uploads')})
            with app.app_context():
                db = get_db()
                password_hash = generate_password_hash('OriginalPassword123')
                db.execute("INSERT INTO users(username,full_name,password_hash,role) VALUES('existing','Existing',?,'admin')", (password_hash,))
                db.commit()
                before = tuple(db.execute('SELECT * FROM users WHERE id=1').fetchone())
                result = populate_sample_data()
                self.assertEqual(result['students'], 12)
                self.assertEqual(result['enrollments'], 36)
                self.assertEqual(result['resources'], 6)
                self.assertEqual(tuple(db.execute('SELECT * FROM users WHERE id=1').fetchone()), before)
                self.assertEqual(populate_sample_data(), {'already_seeded': True})
                self.assertEqual(db.execute('SELECT count(*) FROM students').fetchone()[0], 12)
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
                self.assertEqual(len(list((Path(temp) / 'uploads').glob('*.txt'))), 6)
            client = app.test_client()
            with client.session_transaction() as session:
                session['user_id'] = 1
            for path in ['/', '/students', '/training', '/learning', '/reports', '/accounts']:
                self.assertEqual(client.get(path).status_code, 200)
