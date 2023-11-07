import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
    from django.core.management import execute_from_command_line

    args = sys.argv + ['makemigrations']
    execute_from_command_line(args)