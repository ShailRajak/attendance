import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.models import Section, Department

standard_sections = [
    ("s63_smt", "SMT_PD"),
    ("s63_assy", "ASSY_PD"),
    ("hr_3rd_party", "3RD_PARTY_HR"),
    ("ad", "AD"),
    ("assy_qa", "ASSY_QA"),
    ("assy_wh", "ASSY_WH"),
    ("em", "EM"),
    ("hr", "HR"),
    ("ie", "IE"),
    ("marketing", "MARKETING"),
    ("npi", "NPI"),
    ("pe", "PE"),
    ("planning", "PLANNING"),
    ("purchase", "PURCHASE"),
    ("smt_eng", "SMT_ENG"),
    ("smt_qa", "SMT_QA"),
    ("smt_wh", "SMT_WH"),
    ("trc", "TRC"),
    ("other", "OTHER"),
]

print("Ensuring standard sections exist in Section table...")
default_dept = Department.objects.first()

for code, name in standard_sections:
    sec, created = Section.objects.get_or_create(
        code=code,
        defaults={
            "name": name,
            "is_active": True,
            "department": default_dept
        }
    )
    if not created and sec.name != name and not sec.name.startswith("Sector") and not sec.name.startswith("Phase"):
        sec.name = name
        sec.save()
    print(f"Section: {sec.code} -> {sec.name} (Created: {created})")

print("\nTotal Active Sections in DB:", Section.objects.filter(is_active=True).count())
