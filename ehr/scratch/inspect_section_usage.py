import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.models import Section, UserProfile, Team

print("============================================================")
print("INSPECTING FK REFERENCES TO SECTIONS")
print("============================================================")

for s in Section.objects.all().order_by("id"):
    profiles_count = UserProfile.objects.filter(section=s).count()
    teams_count = Team.objects.filter(section=s).count()
    print(f"Section ID={s.id}, Code='{s.code}', Name='{s.name}' -> Profiles: {profiles_count}, Teams: {teams_count}")
