import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.models import Section

print("Total Sections in DB:", Section.objects.count())
for s in Section.objects.all():
    print(f"ID: {s.id}, Code: '{s.code}', Name: '{s.name}', Active: {s.is_active}")
