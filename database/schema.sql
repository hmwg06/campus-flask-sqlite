CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','staff','teacher','student')),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS programs (
 id INTEGER PRIMARY KEY, code TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', UNIQUE(code,version)
);
CREATE TABLE IF NOT EXISTS subjects (
 id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 credits INTEGER NOT NULL CHECK(credits BETWEEN 1 AND 30), description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS curriculum (
 id INTEGER PRIMARY KEY, program_id INTEGER NOT NULL REFERENCES programs(id),
 subject_id INTEGER NOT NULL REFERENCES subjects(id), semester INTEGER NOT NULL CHECK(semester BETWEEN 1 AND 20), UNIQUE(program_id,subject_id)
);
CREATE TABLE IF NOT EXISTS students (
 id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '',
 cohort TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('studying','paused','graduated','withdrawn')), user_id INTEGER UNIQUE REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS studies (
 id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id), program_id INTEGER NOT NULL REFERENCES programs(id),
 start_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('studying','paused','graduated','withdrawn')), UNIQUE(student_id,program_id)
);
CREATE TABLE IF NOT EXISTS classes (
 id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, subject_id INTEGER NOT NULL REFERENCES subjects(id),
 teacher_id INTEGER NOT NULL REFERENCES users(id), term TEXT NOT NULL, schedule TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS enrollments (
 id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id), class_id INTEGER NOT NULL REFERENCES classes(id),
 grade REAL CHECK(grade BETWEEN 0 AND 10), status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published')),
 UNIQUE(student_id,class_id), CHECK(status != 'published' OR grade IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS resources (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL, source TEXT NOT NULL, version TEXT NOT NULL,
 license TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', stored_name TEXT, original_name TEXT,
 owner_id INTEGER NOT NULL REFERENCES users(id), status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','archived')),
 reviewed_by INTEGER REFERENCES users(id), reviewed_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS resource_subjects (
 resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE, subject_id INTEGER NOT NULL REFERENCES subjects(id), PRIMARY KEY(resource_id,subject_id)
);
CREATE TABLE IF NOT EXISTS questions (
 id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL REFERENCES subjects(id), prompt TEXT NOT NULL,
 choice_a TEXT NOT NULL, choice_b TEXT NOT NULL, choice_c TEXT NOT NULL, choice_d TEXT NOT NULL,
 answer TEXT NOT NULL CHECK(answer IN ('A','B','C','D')), source TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, owner_id INTEGER NOT NULL REFERENCES users(id),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','archived')),
 reviewed_by INTEGER REFERENCES users(id), reviewed_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), action TEXT NOT NULL, entity TEXT NOT NULL,
 record_id INTEGER, detail TEXT NOT NULL DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS activity (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), resource_id INTEGER NOT NULL REFERENCES resources(id), created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS enrollment_student_idx ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS class_teacher_idx ON classes(teacher_id);
CREATE INDEX IF NOT EXISTS audit_entity_idx ON audit(entity,record_id);
CREATE TABLE IF NOT EXISTS question_attempts (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 question_id INTEGER NOT NULL REFERENCES questions(id), question_version INTEGER NOT NULL,
 selected_answer TEXT NOT NULL CHECK(selected_answer IN ('A','B','C','D')),
 is_correct INTEGER NOT NULL CHECK(is_correct IN (0,1)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS attempt_user_question_idx ON question_attempts(user_id,question_id,question_version,id);
CREATE TABLE IF NOT EXISTS session_versions (
 user_id INTEGER PRIMARY KEY REFERENCES users(id), generation INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS password_recovery (
 user_id INTEGER PRIMARY KEY REFERENCES users(id), requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 token_hash TEXT UNIQUE, password_stamp TEXT, expires_at TEXT
);
CREATE TABLE IF NOT EXISTS lecturers (
 id INTEGER PRIMARY KEY, source_key TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL,
 academic_title TEXT NOT NULL DEFAULT '', department TEXT NOT NULL, position TEXT NOT NULL DEFAULT '',
 source_url TEXT NOT NULL, profile_url TEXT NOT NULL DEFAULT '', retrieved_date TEXT NOT NULL
);
