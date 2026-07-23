import os
import sys
import django

sys.path.append(r'c:\Users\shailendra.rajak\Documents\GitHub\attendance\ehr')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ehr.settings')
django.setup()

from django.apps import apps
from attendance.models import Section

print("============================================================")
print("ALL MODELS REFERENCING SECTION MODEL")
print("============================================================")

section_model = Section

related_fields = []
for model in apps.get_models():
    for field in model._meta.get_fields():
        if field.is_relation and field.related_model == section_model:
            related_fields.append((model, field))
            print(f"Model: {model.__name__} (app: {model._meta.app_label}), Field: {field.name}, Type: {type(field).__name__}")

print("\n============================================================")
print("CURRENT SECTION RECORDS IN DB")
print("============================================================")
for s in Section.objects.all().order_by("id"):
    print(f"ID={s.id}, Code='{s.code}', Name='{s.name}', Active={s.is_active}")
