import io
import unittest
from unittest.mock import patch

import app


class CommandTest(unittest.TestCase):
    def test_demo_command_is_unavailable(self):
        result = app.app.test_cli_runner().invoke(args=['seed-demo'])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("No such command 'seed-demo'", result.output)

    def test_help_works_with_windows_console_encoding(self):
        buffer = io.BytesIO()
        with io.TextIOWrapper(buffer, encoding='cp1252') as output:
            with patch('sys.argv', ['app.py', '--help']), patch('sys.stdout', output):
                with self.assertRaises(SystemExit) as result:
                    app.main()
            self.assertEqual(result.exception.code, 0)
            output.flush()
            self.assertIn('run', buffer.getvalue().decode('cp1252'))
            self.assertNotIn('refresh-neu', buffer.getvalue().decode('cp1252'))

    def test_startup(self):
        for command in (None, 'run'):
            with self.subTest(command=command):
                arguments = ['app.py'] + ([command] if command else [])
                with patch('sys.argv', arguments), patch.object(app.app, 'run') as run:
                    app.main()
                    run.assert_called_once_with(debug=False)

    def test_removed_import_commands_are_rejected(self):
        for command in ('import-neu-majors', 'refresh-neu'):
            with self.subTest(command=command):
                with patch('sys.argv', ['app.py', command]), patch('sys.stderr', io.StringIO()), \
                        patch.object(app.app, 'run') as run:
                    with self.assertRaises(SystemExit) as result:
                        app.main()
                    self.assertEqual(result.exception.code, 2)
                    run.assert_not_called()
