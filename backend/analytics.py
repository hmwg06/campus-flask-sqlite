"""Phân tích học tập: kết quả theo lớp, sử dụng học liệu và xuất CSV."""
import csv
import io
from .common import MANAGERS, one, query, require
from datetime import datetime, timezone
from flask import Response, render_template


# --- REPORTS ---
def report_data():
    require(*MANAGERS)
    # LEFT JOIN giữ cả lớp chưa có đăng ký; CASE chỉ tính điểm đã công bố vào trung bình.
    return query("""SELECT c.code,s.name,c.term,count(e.id) AS students,
                    sum(CASE WHEN e.status='published' THEN 1 ELSE 0 END) AS published,
                    round(avg(CASE WHEN e.status='published' THEN e.grade END),2) AS average
                    FROM classes c JOIN subjects s ON s.id=c.subject_id LEFT JOIN enrollments e ON e.class_id=c.id
                    GROUP BY c.id ORDER BY c.code""")


def reports():
    rows = report_data()
    # Thời điểm báo cáo dùng UTC; julianday tính chênh lệch theo ngày, nhân 24 để đổi sang giờ.
    return render_template('reports.html', title='Phân tích học tập', active='reports', rows=rows,
                           generated=datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC'),
                           activities=query('SELECT r.title,count(a.id) AS views FROM resources r LEFT JOIN activity a ON a.resource_id=r.id GROUP BY r.id ORDER BY views DESC'),
                           reviews=one("SELECT count(*) AS total,round(avg((julianday(reviewed_at)-julianday(created_at))*24),2) AS hours FROM resources WHERE reviewed_at IS NOT NULL"))


def export_report():
    rows = report_data()
    # Tạo CSV trong bộ nhớ, không cần ghi file tạm ra ổ đĩa.
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Mã lớp', 'Học phần', 'Học kỳ', 'Số đăng ký', 'Đã công bố', 'Điểm trung bình đã công bố'])
    for row in rows:
        # Thêm dấu ' trước ô bắt đầu bằng ký hiệu công thức để Excel coi đó là văn bản.
        writer.writerow([("'" + str(v)) if str(v).lstrip().startswith(('=', '+', '-', '@')) else v for v in row])
    # BOM UTF-8 giúp Excel nhận tiếng Việt; Content-Disposition yêu cầu tải file với tên này.
    return Response('\ufeff' + output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=bao-cao-dao-tao.csv'})
