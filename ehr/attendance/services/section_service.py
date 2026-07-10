from typing import Optional, Tuple
from django.contrib.auth.models import User
from attendance.models import Section


class SectionService:
    @staticmethod
    def create_section(
        name: str,
        code: str,
        description: str,
        location: str,
        created_by: User,
    ) -> Tuple[Optional[Section], str]:
        """
        Creates a new section.
        """
        if Section.objects.filter(code=code).exists():
            return None, f"Section with code '{code}' already exists."

        try:
            sec = Section.objects.create(
                name=name,
                code=code,
                description=description,
                location=location,
                created_by=created_by,
            )
            return sec, "Section created successfully."
        except Exception as e:
            return None, str(e)

    @staticmethod
    def update_section(
        sec_id: int,
        name: str,
        description: str,
        location: str,
        is_active: bool,
    ) -> Tuple[bool, str]:
        """
        Updates an existing section.
        """
        try:
            sec = Section.objects.get(id=sec_id)
            sec.name = name
            sec.description = description
            sec.location = location
            sec.is_active = is_active
            sec.save()
            return True, "Section updated successfully."
        except Section.DoesNotExist:
            return False, "Section not found."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def deactivate_section(sec_id: int) -> Tuple[bool, str]:
        """
        Soft deletes (deactivates) a section.
        """
        try:
            sec = Section.objects.get(id=sec_id)
            sec.is_active = False
            sec.save()
            return True, "Section deactivated successfully."
        except Section.DoesNotExist:
            return False, "Section not found."
        except Exception as e:
            return False, str(e)
