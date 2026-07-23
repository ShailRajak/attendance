import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.models import Role, Section, UserProfile

print("=== ALL ROLES ===")
for r in Role.objects.all():
    print(f"ID={r.id}, Code={r.code}, Name={r.name}, Scope={r.data_scope}, Active={r.is_active}")

print("\n=== ALL SECTIONS (active) ===")
for s in Section.objects.filter(is_active=True):
    print(f"ID={s.id}, Code={s.code}, Name={s.name}, Dept={s.department.name if s.department else 'None'}")
