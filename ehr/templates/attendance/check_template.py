import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')

import django
django.setup()

from django.template.loader import get_template
try:
    template = get_template('attendance/base.html')
    print('Template parsed successfully')
except Exception as e:
    print(f'Error: {e}')