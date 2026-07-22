import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from attendance.models import UserProfile, Plant, Company, Section
from django.contrib.auth.models import User

print("============================================================")
print("INSPECTING PLANTS, SECTIONS, & USERS")
print("============================================================")

plants = Plant.objects.all()
print("Plants in DB:", [(p.id, p.name, p.code) for p in plants])

companies = Company.objects.all()
print("Companies in DB:", [(c.id, c.name, c.code) for c in companies])

profiles_with_plant = UserProfile.objects.filter(plant__isnull=False).count()
profiles_total = UserProfile.objects.count()
print(f"UserProfiles with Plant: {profiles_with_plant} / {profiles_total}")

if profiles_with_plant > 0:
    for p in UserProfile.objects.filter(plant__isnull=False)[:5]:
        print(f"User {p.user.username}: plant={p.plant.name}, section={p.section.name if p.section else None}")
