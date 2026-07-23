import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.db import transaction
from attendance.models import Section, UserProfile, Team

print("============================================================")
print("PERFORMING SECTION MASTER DATA CLEANUP & DUPLICATE MERGE")
print("============================================================")

def clean_section_name(name):
    clean = name
    if clean.startswith("Phase 2 - "):
        clean = clean[len("Phase 2 - "):]
    elif clean.startswith("Sector 63 - "):
        clean = clean[len("Sector 63 - "):]
    
    clean = clean.strip()
    # Normalize common variations to standard codes/names
    clean_upper = clean.upper().replace(" ", "_")
    if clean_upper == "SMT_PD":
        return "SMT_PD", "smt_pd"
    elif clean_upper == "ASSY_PD":
        return "ASSY_PD", "assy_pd"
    elif clean_upper == "MARKETING":
        return "MARKETING", "marketing"
    elif clean_upper == "PURCHASE":
        return "PURCHASE", "purchase"
    elif clean_upper == "3RD_PARTY_HR":
        return "3RD_PARTY_HR", "hr_3rd_party"
    else:
        code = clean_upper.lower()
        return clean_upper, code

with transaction.atomic():
    all_sections = list(Section.objects.all().order_by("id"))
    
    # Map target code -> list of section objects
    groups = {}
    for s in all_sections:
        target_name, target_code = clean_section_name(s.name)
        groups.setdefault(target_code, []).append((s, target_name, target_code))

    print(f"Found {len(groups)} unique section groups across {len(all_sections)} existing records.\n")

    for target_code, sec_tuples in groups.items():
        # Pick primary section (prefer one whose existing code equals target_code, else first)
        primary_tuple = None
        for t in sec_tuples:
            if t[0].code == target_code:
                primary_tuple = t
                break
        if not primary_tuple:
            primary_tuple = sec_tuples[0]

        primary_sec = primary_tuple[0]
        target_name = primary_tuple[1]

        # Update primary section details
        primary_sec.name = target_name
        primary_sec.code = target_code
        primary_sec.is_active = True
        primary_sec.save()

        # Handle secondary duplicates
        secondary_secs = [t[0] for t in sec_tuples if t[0].id != primary_sec.id]
        if secondary_secs:
            sec_ids = [s.id for s in secondary_secs]
            print(f"Merging duplicates for '{target_name}' (Target Code: '{target_code}'):")
            print(f"  Primary Section ID={primary_sec.id}")
            print(f"  Secondary Section IDs={sec_ids}")

            # Re-link UserProfiles
            relinked_profiles = UserProfile.objects.filter(section__in=secondary_secs).update(section=primary_sec)
            print(f"  Re-linked {relinked_profiles} UserProfile record(s) to Primary Section ID={primary_sec.id}")

            # Re-link Teams
            relinked_teams = Team.objects.filter(section__in=secondary_secs).update(section=primary_sec)
            print(f"  Re-linked {relinked_teams} Team record(s) to Primary Section ID={primary_sec.id}")

            # Delete secondary duplicates
            for s in secondary_secs:
                s.delete()
            print(f"  Deleted {len(secondary_secs)} secondary duplicate section record(s).\n")

print("============================================================")
print("CLEANUP COMPLETED! FINAL ACTIVE SECTIONS IN DB:")
print("============================================================")
final_sections = Section.objects.filter(is_active=True).order_by("name")
for s in final_sections:
    profiles_count = UserProfile.objects.filter(section=s).count()
    print(f"ID={s.id}, Code='{s.code}', Name='{s.name}' | Linked Profiles: {profiles_count}")

print(f"\nTotal Clean Active Sections: {final_sections.count()}")
