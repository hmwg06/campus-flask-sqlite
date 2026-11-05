"""Chạy website bằng python app.py; cấu hình và route nằm trong backend/app.py."""
import argparse

from backend.app import create_app


app = create_app()


def main():
    # Tham số command là tùy chọn: python app.py và python app.py run đều mở website.
    # argparse tự xử lý --help và từ chối lệnh không nằm trong choices.
    parser = argparse.ArgumentParser(description='LMS - Flask + SQLite')
    parser.add_argument('command', nargs='?', default='run', choices=['run'],
                        help='run: start website')
    parser.parse_args()
    app.run(debug=False)


if __name__ == '__main__':
    main()
