"""Student revision pages and personal metrics from actual question attempts."""
from datetime import datetime, timedelta, timezone

from flask import abort, g, render_template, request

from .common import query, require, rows_for, scope


def summary():
    require('student')
    courses = [dict(row) for row in query('''
        SELECT DISTINCT s.id,s.code,s.name,s.credits FROM subjects s
        JOIN classes c ON c.subject_id=s.id JOIN enrollments e ON e.class_id=c.id
        JOIN students st ON st.id=e.student_id WHERE st.user_id=? ORDER BY s.name
    ''', (g.user['id'],))]
    questions = rows_for('questions')
    condition, params = scope('questions')
    attempts = query(f'''SELECT a.*,t.subject_id,t.prompt,s.name AS subject_name
        FROM question_attempts a JOIN questions t ON t.id=a.question_id
        JOIN subjects s ON s.id=t.subject_id
        WHERE a.user_id=? AND a.question_version=t.version AND ({condition})
        ORDER BY a.id DESC''', [g.user['id'], *params])
    latest = {}
    for attempt in attempts:
        latest.setdefault(attempt['question_id'], attempt)
    for course in courses:
        subject_questions = [q for q in questions if q['subject_id'] == course['id']]
        subject_attempts = [a for a in attempts if a['subject_id'] == course['id']]
        course.update(total=len(subject_questions), attempts=len(subject_attempts),
                      correct=sum(a['is_correct'] for a in subject_attempts),
                      answered=sum(q['id'] in latest for q in subject_questions),
                      wrong=sum(q['id'] in latest and not latest[q['id']]['is_correct'] for q in subject_questions))
        course['accuracy'] = round(100 * course['correct'] / course['attempts']) if course['attempts'] else None
    today = datetime.now(timezone.utc).date()
    daily = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_attempts = [a for a in attempts if a['created_at'][:10] == day.isoformat()]
        daily.append(dict(label=day.strftime('%d/%m'), attempts=len(day_attempts),
                          correct=sum(a['is_correct'] for a in day_attempts)))
    correct = sum(a['is_correct'] for a in attempts)
    recommended = sorted((c for c in courses if c['total']),
                         key=lambda c: (-c['wrong'], c['answered'] / c['total'], c['name']))[:3]
    return dict(courses=courses, questions=questions, latest=latest, attempts=len(attempts),
                correct=correct, accuracy=round(100 * correct / len(attempts)) if attempts else None,
                wrong=sum(not a['is_correct'] for a in latest.values()), answered=len(latest),
                recent=attempts[:8], daily=daily, daily_max=max(1, *(d['attempts'] for d in daily)),
                recommended=recommended)


def dashboard():
    return render_template('student_dashboard.html', title='Tổng quan học tập', active='dashboard', study=summary())


def courses():
    data = summary()
    resources = {r['id']: dict(r) for r in rows_for('resources')}
    links = query('SELECT resource_id,subject_id FROM resource_subjects')
    for course in data['courses']:
        course['resources'] = [resources[r['resource_id']] for r in links
                               if r['subject_id'] == course['id'] and r['resource_id'] in resources]
    return render_template('student_courses.html', title='Học phần của tôi', active='courses', study=data)


def practice():
    data = summary()
    raw_subject = request.args.get('subject', '')
    try:
        subject = int(raw_subject) if raw_subject else None
        page = int(request.args.get('page', '1'))
    except ValueError:
        abort(400)
    if page < 1:
        abort(400)
    if subject is not None and subject not in {c['id'] for c in data['courses']}:
        abort(403)
    mode = request.args.get('mode', 'all')
    if mode not in ('all', 'wrong', 'new'):
        abort(400)
    questions = []
    for q in data['questions']:
        last = data['latest'].get(q['id'])
        if subject is not None and q['subject_id'] != subject:
            continue
        if mode == 'wrong' and (not last or last['is_correct']):
            continue
        if mode == 'new' and last:
            continue
        questions.append(q)
    total = len(questions)
    pages = max(1, (total + 9) // 10)
    page = min(page, pages)
    return render_template('practice.html', title='Luyện tập', active='practice', study=data,
                           questions=questions[(page - 1) * 10:page * 10], subject=subject,
                           subject_names={c['id']: c['name'] for c in data['courses']},
                           mode=mode, page=page, pages=pages, total=total)
