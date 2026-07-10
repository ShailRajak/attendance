from django.contrib.auth.models import User
from django.db import transaction
from attendance.models import UserProfile, Role, Section


class UserService:
    @staticmethod
    def update_user_profile(
        user_id: int, role_code: str, section_code: str, is_active: bool
    ) -> tuple[bool, str]:
        """
        Update user profile role, section and active status in a transaction.
        """
        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                user.is_active = is_active
                user.save()

                profile, _ = UserProfile.objects.get_or_create(user=user)

                # Fetch Role
                role = Role.objects.get(code=role_code)
                profile.role = role

                # Fetch Section (optional)
                if section_code:
                    section = Section.objects.get(code=section_code)
                    profile.section = section
                else:
                    profile.section = None

                profile.save()
                return True, "User profile updated successfully."
        except User.DoesNotExist:
            return False, "User not found."
        except Role.DoesNotExist:
            return False, f"Role with code '{role_code}' not found."
        except Section.DoesNotExist:
            return False, f"Section with code '{section_code}' not found."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def reset_password(user_id: int, new_password: str) -> tuple[bool, str]:
        """
        Set a new password for the specified user.
        """
        try:
            user = User.objects.get(id=user_id)
            user.set_password(new_password)
            user.save()
            return True, "Password reset successfully."
        except User.DoesNotExist:
            return False, "User not found."
        except Exception as e:
            return False, str(e)
