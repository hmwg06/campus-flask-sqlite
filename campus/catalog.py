"""Vai trò, trạng thái và cấu hình các trường biểu mẫu."""
ROLES = {'admin': 'Quản trị viên', 'staff': 'Cán bộ quản lý', 'teacher': 'Giảng viên', 'student': 'Sinh viên'}

STATUS = {'studying': 'Đang học', 'paused': 'Bảo lưu', 'graduated': 'Tốt nghiệp', 'withdrawn': 'Thôi học',
          'draft': 'Bản nháp', 'published': 'Đã công bố', 'archived': 'Đã lưu trữ'}

STUDY_STATUS = {k: STATUS[k] for k in ('studying', 'paused', 'graduated', 'withdrawn')}

def field(name, label, kind='text', required=True, options=None):
    # name là tên cột/input; label là nhãn; kind quyết định kiểu nhập và kiểm tra.
    # required=False cho phép bỏ trống; options chứa lựa chọn hoặc tên danh mục liên kết.
    return dict(name=name, label=label, kind=kind, required=required, options=options)

# Mỗi mục mô tả một bảng được phép quản lý: dùng chung cho form và trang danh sách.
# relation chọn một bản ghi liên quan; multi chọn nhiều; select chọn giá trị cố định.
CATALOG = {
    'students': dict(
        title='Hồ sơ sinh viên', module='students',
        fields=[
            field('code', 'Mã sinh viên'),
            field('full_name', 'Họ và tên'),
            field('email', 'Email', 'email', False),
            field('cohort', 'Khóa'),
            field('status', 'Trạng thái', 'select', options=STUDY_STATUS),
            field('user_id', 'Tài khoản sinh viên', 'relation', False, 'student_users'),
        ],
    ),
    'studies': dict(
        title='Quá trình theo học', module='students',
        fields=[
            field('student_id', 'Sinh viên', 'relation', options='students'),
            field('program_id', 'Chương trình / phiên bản', 'relation', options='programs'),
            field('start_date', 'Ngày bắt đầu', 'date'),
            field('status', 'Trạng thái', 'select', options=STUDY_STATUS),
        ],
    ),
    'programs': dict(
        title='Chương trình đào tạo', module='training',
        fields=[
            field('code', 'Mã chương trình'),
            field('name', 'Tên chương trình'),
            field('version', 'Phiên bản'),
            field('description', 'Mô tả', 'textarea', False),
        ],
    ),
    'subjects': dict(
        title='Học phần', module='training',
        fields=[
            field('code', 'Mã học phần'),
            field('name', 'Tên học phần'),
            field('credits', 'Số tín chỉ', 'number'),
            field('description', 'Mô tả', 'textarea', False),
        ],
    ),
    'curriculum': dict(
        title='Khung chương trình', module='training',
        fields=[
            field('program_id', 'Chương trình / phiên bản', 'relation', options='programs'),
            field('subject_id', 'Học phần', 'relation', options='subjects'),
            field('semester', 'Học kỳ dự kiến', 'number'),
        ],
    ),
    'classes': dict(
        title='Lớp học phần', module='training',
        fields=[
            field('code', 'Mã lớp'),
            field('subject_id', 'Học phần', 'relation', options='subjects'),
            field('teacher_id', 'Giảng viên phụ trách', 'relation', options='teachers'),
            field('term', 'Học kỳ / năm học'),
            field('schedule', 'Lịch học', required=False),
        ],
    ),
    'enrollments': dict(
        title='Đăng ký & kết quả', module='training',
        fields=[
            field('student_id', 'Sinh viên', 'relation', options='students'),
            field('class_id', 'Lớp học phần', 'relation', options='classes'),
            field('grade', 'Điểm (0–10)', 'decimal', False),
            field('status', 'Công bố kết quả', 'select', options={'draft': 'Chưa công bố', 'published': 'Đã công bố'}),
        ],
    ),
    'resources': dict(
        title='Kho học liệu', module='learning',
        fields=[
            field('title', 'Tên học liệu'),
            field('subject_ids', 'Học phần liên quan', 'multi', options='subjects'),
            field('author', 'Tác giả'),
            field('source', 'Nguồn tài liệu'),
            field('version', 'Phiên bản'),
            field('license', 'Quyền sử dụng / bản quyền'),
            field('url', 'Đường dẫn học liệu', 'url', False),
            field('file', 'Tệp đính kèm (PDF, TXT, DOCX, PPTX, XLSX, PNG, JPG; tối đa 16 MB)', 'file', False),
        ],
    ),
    'questions': dict(
        title='Ngân hàng câu hỏi', module='learning',
        fields=[
            field('subject_id', 'Học phần', 'relation', options='subjects'),
            field('prompt', 'Nội dung câu hỏi', 'textarea'),
            field('choice_a', 'Phương án A'),
            field('choice_b', 'Phương án B'),
            field('choice_c', 'Phương án C'),
            field('choice_d', 'Phương án D'),
            field('answer', 'Đáp án đúng', 'select', options={k: k for k in 'ABCD'}),
            field('source', 'Nguồn / ghi chú biên soạn'),
        ],
    ),
}
