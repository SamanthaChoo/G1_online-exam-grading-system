#!/usr/bin/env python
import os

os.chdir('online_exam_fastapi')

files = ['tests/test_mcq_create.py', 'tests/test_mcq_validation.py', 'tests/test_pagination.py']

for f in files:
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace('cleanup_db"', 'cleanup_db_between_tests"')
    with open(f, 'w') as file:
        file.write(content)
    print(f'Fixed {f}')

print('Done!')
