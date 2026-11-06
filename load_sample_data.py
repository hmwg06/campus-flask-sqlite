"""Load the published presentation dataset into a new local instance."""
import argparse
import getpass
import json
import os
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parent
TABLES = (
    'users', 'programs', 'subjects', 'curriculum', 'students', 'studies',
    'classes', 'enrollments', 'resources', 'resource_subjects', 'questions',
    'lecturers', 'question_reviewers', 'question_ai_metadata',
    'question_ai_reviews', 'question_reviews', 'question_attempts', 'activity', 'audit',
)


def load_samples(instance_dir, password):
    if not 8 <= len(password) <= 256:
        raise ValueError('Mật khẩu cần từ 8 đến 256 ký tự.')
    folder = Path(instance_dir).resolve()
    target = folder / 'campus.sqlite3'
    if target.exists():
        raise FileExistsError('Database đã tồn tại. Không ghi đè dữ liệu hiện có.')
    payload = json.loads((ROOT / 'sample_data' / 'data.json').read_text(encoding='utf-8'))
    if payload.get('format_version') != 1 or set(payload.get('tables', {})) != set(TABLES):
        raise ValueError('Định dạng bộ dữ liệu không hợp lệ.')
    tables = payload['tables']
    source_folder = (ROOT / 'sample_data' / 'uploads').resolve()
    names = {r['stored_name'] for r in tables['resources'] if r['stored_name']}
    for name in names:
        path = (source_folder / name).resolve()
        if Path(name).name != name or path.parent != source_folder or not path.is_file():
            raise ValueError('Tệp học liệu không hợp lệ hoặc bị thiếu.')
        if (folder / 'uploads' / name).exists():
            raise FileExistsError('Tệp học liệu đã tồn tại. Không ghi đè.')
    folder.mkdir(parents=True, exist_ok=True)
    created_files = []
    with TemporaryDirectory(prefix='.sample-import-', dir=folder) as temporary:
        temporary_db = Path(temporary) / 'campus.sqlite3'
        try:
            with closing(sqlite3.connect(temporary_db)) as db, db:
                db.execute('PRAGMA foreign_keys=ON')
                db.executescript((ROOT / 'database' / 'schema.sql').read_text(encoding='utf-8'))
                for table in TABLES:
                    columns = {r[1] for r in db.execute(f'PRAGMA table_info({table})')}
                    for record in tables[table]:
                        row = dict(record)
                        if not row or not set(row) <= columns:
                            raise ValueError('Trường dữ liệu không hợp lệ trong ' + table)
                        if table == 'users':
                            if 'password_hash' in row:
                                raise ValueError('Bộ dữ liệu không được chứa hash mật khẩu.')
                            row['password_hash'] = generate_password_hash(password)
                        db.execute(
                            f'INSERT INTO {table} ({",".join(row)}) VALUES ({",".join("?" for _ in row)})',
                            list(row.values()),
                        )
                if db.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('Liên kết dữ liệu không hợp lệ.')
            uploads = folder / 'uploads'
            uploads.mkdir(exist_ok=True)
            for name in sorted(names):
                path = uploads / name
                with path.open('xb') as output:
                    created_files.append(path)
                    with (source_folder / name).open('rb') as source:
                        shutil.copyfileobj(source, output)
            # Publish the complete database atomically without replacing an existing file.
            os.link(temporary_db, target)
        except BaseException:
            for path in created_files:
                path.unlink(missing_ok=True)
            raise
    return {table: len(records) for table, records in tables.items()}


def main():
    parser = argparse.ArgumentParser(description='Nạp dữ liệu trình diễn LMS vào database mới.')
    parser.add_argument('--instance-dir', type=Path, default=ROOT / 'instance',
                        help='Thư mục đích, mặc định instance cạnh app.py.')
    args = parser.parse_args()
    if (args.instance_dir / 'campus.sqlite3').exists():
        parser.exit(1, 'Database đã tồn tại. Không ghi đè dữ liệu hiện có.\n')
    password = os.environ.get('LMS_SAMPLE_PASSWORD')
    if password is None:
        password = getpass.getpass('Đặt mật khẩu cho các tài khoản trình diễn: ')
        if password != getpass.getpass('Nhập lại mật khẩu: '):
            parser.exit(1, 'Hai mật khẩu không khớp.\n')
    try:
        counts = load_samples(args.instance_dir, password)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, str(error) + '\n')
    print(f'Đã nạp {counts["students"]} sinh viên, {counts["resources"]} học liệu, {counts["questions"]} câu hỏi.')
    print('Danh sách tên đăng nhập nằm trong TAI-KHOAN.md. Mật khẩu là mật khẩu bạn vừa đặt.')


if __name__ == '__main__':
    main()
