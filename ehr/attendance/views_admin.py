from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.db import transaction

from attendance.models import Role, Section, Permission, UserProfile, Company, Plant, Department, Team, AuditLog
from attendance.services.rbac_service import RBACService
from attendance.services.role_service import RoleService
from attendance.services.section_service import SectionService
from attendance.services.user_service import UserService
from attendance.services.permission_service import PermissionService
from attendance.services.audit_service import AuditService
from attendance.services.import_service import ImportService


def admin_permission_required(perm_code=None):
    """
    Decorator for views that require admin permissions.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if perm_code and RBACService.has_permission(request.user, perm_code):
                return view_func(request, *args, **kwargs)
            # Default check: if no code, check if they have any management perm
            if not perm_code and (
                RBACService.has_permission(request.user, "role.manage")
                or RBACService.has_permission(request.user, "section.manage")
                or RBACService.has_permission(request.user, "permission.manage")
                or RBACService.has_permission(request.user, "user.manage")
            ):
                return view_func(request, *args, **kwargs)

            messages.error(
                request, "You do not have administrative permission to access this page."
            )
            return redirect("home")
        return _wrapped_view
    return decorator


@admin_permission_required()
def admin_dashboard(request):
    """
    Administration Dashboard landing page.
    """
    context = {
        "active_tab": "admin",
        "companies_count": Company.objects.count(),
        "plants_count": Plant.objects.count(),
        "departments_count": Department.objects.count(),
        "sections_count": Section.objects.count(),
        "teams_count": Team.objects.count(),
        "roles_count": Role.objects.count(),
        "permissions_count": Permission.objects.count(),
        "users_count": User.objects.count(),
        "audit_count": AuditLog.objects.count(),
    }
    return render(request, "attendance/admin/dashboard.html", context)


# ==========================================================
# COMPANIES CRUD
# ==========================================================

@admin_permission_required("role.manage")
def admin_companies(request):
    query = request.GET.get("q", "").strip()
    companies = Company.objects.all().order_by("-is_active", "name")

    if query:
        companies = companies.filter(Q(name__icontains=query) | Q(code__icontains=query))

    paginator = Paginator(companies, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"active_tab": "admin", "page_obj": page_obj, "query": query}
    return render(request, "attendance/admin/companies.html", context)


@admin_permission_required("role.manage")
def admin_company_create(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        description = request.POST.get("description", "").strip()

        if Company.objects.filter(code=code).exists():
            messages.error(request, f"Company code '{code}' already exists.")
        else:
            comp = Company.objects.create(name=name, code=code, description=description)
            AuditService.log(
                user=request.user,
                action_type="COMPANY_CREATED",
                description=f"Created company {name} (code: {code})",
            )
            messages.success(request, f"Company '{name}' created successfully.")
            return redirect("admin_companies")

    return render(request, "attendance/admin/company_form.html", {"active_tab": "admin", "is_create": True})


@admin_permission_required("role.manage")
def admin_company_edit(request, comp_id):
    comp = get_object_or_404(Company, id=comp_id)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "deactivate":
            comp.is_active = False
            comp.save()
            AuditService.log(
                user=request.user,
                action_type="COMPANY_DEACTIVATED",
                description=f"Deactivated company {comp.name}",
            )
            messages.success(request, f"Company '{comp.name}' soft-deleted successfully.")
            return redirect("admin_companies")
        elif action == "restore":
            comp.is_active = True
            comp.save()
            AuditService.log(
                user=request.user,
                action_type="COMPANY_RESTORED",
                description=f"Restored company {comp.name}",
            )
            messages.success(request, f"Company '{comp.name}' restored successfully.")
            return redirect("admin_companies")

        comp.name = request.POST.get("name", "").strip()
        comp.description = request.POST.get("description", "").strip()
        comp.is_active = request.POST.get("is_active") == "on"
        comp.save()

        AuditService.log(
            user=request.user,
            action_type="COMPANY_UPDATED",
            description=f"Updated company {comp.name}",
        )
        messages.success(request, f"Company '{comp.name}' updated successfully.")
        return redirect("admin_companies")

    return render(request, "attendance/admin/company_form.html", {"active_tab": "admin", "company": comp, "is_create": False})


# ==========================================================
# PLANTS CRUD
# ==========================================================

@admin_permission_required("role.manage")
def admin_plants(request):
    query = request.GET.get("q", "").strip()
    plants = Plant.objects.all().select_related("company").order_by("-is_active", "name")

    if query:
        plants = plants.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(city__icontains=query))

    paginator = Paginator(plants, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"active_tab": "admin", "page_obj": page_obj, "query": query}
    return render(request, "attendance/admin/plants.html", context)


@admin_permission_required("role.manage")
def admin_plant_create(request):
    companies = Company.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        company_code = request.POST.get("company", "").strip()
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        address = request.POST.get("address", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        country = request.POST.get("country", "").strip()
        description = request.POST.get("description", "").strip()

        try:
            company = Company.objects.get(code=company_code)
            if Plant.objects.filter(code=code).exists():
                messages.error(request, f"Plant code '{code}' already exists.")
            else:
                plant = Plant.objects.create(
                    company=company,
                    name=name,
                    code=code,
                    address=address,
                    city=city,
                    state=state,
                    country=country,
                    description=description,
                )
                AuditService.log(
                    user=request.user,
                    action_type="PLANT_CREATED",
                    description=f"Created plant {name} under {company.name}",
                )
                messages.success(request, f"Plant '{name}' created successfully.")
                return redirect("admin_plants")
        except Company.DoesNotExist:
            messages.error(request, "Selected company does not exist.")

    return render(request, "attendance/admin/plant_form.html", {"active_tab": "admin", "companies": companies, "is_create": True})


@admin_permission_required("role.manage")
def admin_plant_edit(request, plant_id):
    plant = get_object_or_404(Plant, id=plant_id)
    companies = Company.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "deactivate":
            plant.is_active = False
            plant.save()
            AuditService.log(
                user=request.user,
                action_type="PLANT_DEACTIVATED",
                description=f"Deactivated plant {plant.name}",
            )
            messages.success(request, f"Plant '{plant.name}' soft-deleted successfully.")
            return redirect("admin_plants")
        elif action == "restore":
            plant.is_active = True
            plant.save()
            AuditService.log(
                user=request.user,
                action_type="PLANT_RESTORED",
                description=f"Restored plant {plant.name}",
            )
            messages.success(request, f"Plant '{plant.name}' restored successfully.")
            return redirect("admin_plants")

        company_code = request.POST.get("company", "").strip()
        try:
            company = Company.objects.get(code=company_code)
            plant.company = company
            plant.name = request.POST.get("name", "").strip()
            plant.address = request.POST.get("address", "").strip()
            plant.city = request.POST.get("city", "").strip()
            plant.state = request.POST.get("state", "").strip()
            plant.country = request.POST.get("country", "").strip()
            plant.description = request.POST.get("description", "").strip()
            plant.is_active = request.POST.get("is_active") == "on"
            plant.save()

            AuditService.log(
                user=request.user,
                action_type="PLANT_UPDATED",
                description=f"Updated plant {plant.name}",
            )
            messages.success(request, f"Plant '{plant.name}' updated successfully.")
            return redirect("admin_plants")
        except Company.DoesNotExist:
            messages.error(request, "Selected company does not exist.")

    return render(request, "attendance/admin/plant_form.html", {"active_tab": "admin", "plant": plant, "companies": companies, "is_create": False})


# ==========================================================
# DEPARTMENTS CRUD
# ==========================================================

@admin_permission_required("role.manage")
def admin_departments(request):
    query = request.GET.get("q", "").strip()
    departments = Department.objects.all().select_related("plant").order_by("-is_active", "name")

    if query:
        departments = departments.filter(Q(name__icontains=query) | Q(code__icontains=query))

    paginator = Paginator(departments, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"active_tab": "admin", "page_obj": page_obj, "query": query}
    return render(request, "attendance/admin/departments.html", context)


@admin_permission_required("role.manage")
def admin_department_create(request):
    plants = Plant.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        plant_code = request.POST.get("plant", "").strip()
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        description = request.POST.get("description", "").strip()

        try:
            plant = Plant.objects.get(code=plant_code)
            if Department.objects.filter(code=code).exists():
                messages.error(request, f"Department code '{code}' already exists.")
            else:
                Department.objects.create(
                    plant=plant,
                    name=name,
                    code=code,
                    description=description,
                )
                AuditService.log(
                    user=request.user,
                    action_type="DEPARTMENT_CREATED",
                    description=f"Created department {name} under plant {plant.name}",
                )
                messages.success(request, f"Department '{name}' created successfully.")
                return redirect("admin_departments")
        except Plant.DoesNotExist:
            messages.error(request, "Selected plant does not exist.")

    return render(request, "attendance/admin/department_form.html", {"active_tab": "admin", "plants": plants, "is_create": True})


@admin_permission_required("role.manage")
def admin_department_edit(request, dept_id):
    dept = get_object_or_404(Department, id=dept_id)
    plants = Plant.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "deactivate":
            dept.is_active = False
            dept.save()
            AuditService.log(
                user=request.user,
                action_type="DEPARTMENT_DEACTIVATED",
                description=f"Deactivated department {dept.name}",
            )
            messages.success(request, f"Department '{dept.name}' soft-deleted successfully.")
            return redirect("admin_departments")
        elif action == "restore":
            dept.is_active = True
            dept.save()
            AuditService.log(
                user=request.user,
                action_type="DEPARTMENT_RESTORED",
                description=f"Restored department {dept.name}",
            )
            messages.success(request, f"Department '{dept.name}' restored successfully.")
            return redirect("admin_departments")

        plant_code = request.POST.get("plant", "").strip()
        try:
            plant = Plant.objects.get(code=plant_code)
            dept.plant = plant
            dept.name = request.POST.get("name", "").strip()
            dept.description = request.POST.get("description", "").strip()
            dept.is_active = request.POST.get("is_active") == "on"
            dept.save()

            AuditService.log(
                user=request.user,
                action_type="DEPARTMENT_UPDATED",
                description=f"Updated department {dept.name}",
            )
            messages.success(request, f"Department '{dept.name}' updated successfully.")
            return redirect("admin_departments")
        except Plant.DoesNotExist:
            messages.error(request, "Selected plant does not exist.")

    return render(request, "attendance/admin/department_form.html", {"active_tab": "admin", "department": dept, "plants": plants, "is_create": False})


# ==========================================================
# SECTIONS CRUD (With Department Mapping)
# ==========================================================

@admin_permission_required("section.manage")
def admin_sections(request):
    query = request.GET.get("q", "").strip()
    sections = Section.objects.all().select_related("department").order_by("-is_active", "name")

    if query:
        sections = sections.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(location__icontains=query)
        )

    paginator = Paginator(sections, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"active_tab": "admin", "page_obj": page_obj, "query": query}
    return render(request, "attendance/admin/sections.html", context)


@admin_permission_required("section.manage")
def admin_section_create(request):
    departments = Department.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        dept_code = request.POST.get("department", "").strip()
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        description = request.POST.get("description", "").strip()
        location = request.POST.get("location", "").strip()

        try:
            dept = Department.objects.get(code=dept_code)
            if Section.objects.filter(code=code).exists():
                messages.error(request, f"Section code '{code}' already exists.")
            else:
                Section.objects.create(
                    department=dept,
                    name=name,
                    code=code,
                    description=description,
                    location=location,
                )
                AuditService.log(
                    user=request.user,
                    action_type="SECTION_CREATED",
                    description=f"Created section {name} under department {dept.name}",
                )
                messages.success(request, f"Section '{name}' created successfully.")
                return redirect("admin_sections")
        except Department.DoesNotExist:
            messages.error(request, "Selected department does not exist.")

    return render(request, "attendance/admin/section_form.html", {"active_tab": "admin", "departments": departments, "is_create": True})


@admin_permission_required("section.manage")
def admin_section_edit(request, sec_id):
    section = get_object_or_404(Section, id=sec_id)
    departments = Department.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "deactivate":
            section.is_active = False
            section.save()
            AuditService.log(
                user=request.user,
                action_type="SECTION_DEACTIVATED",
                description=f"Deactivated section {section.name}",
            )
            messages.success(request, f"Section '{section.name}' soft-deleted successfully.")
            return redirect("admin_sections")
        elif action == "restore":
            section.is_active = True
            section.save()
            AuditService.log(
                user=request.user,
                action_type="SECTION_RESTORED",
                description=f"Restored section {section.name}",
            )
            messages.success(request, f"Section '{section.name}' restored successfully.")
            return redirect("admin_sections")

        dept_code = request.POST.get("department", "").strip()
        try:
            dept = Department.objects.get(code=dept_code)
            section.department = dept
            section.name = request.POST.get("name", "").strip()
            section.description = request.POST.get("description", "").strip()
            section.location = request.POST.get("location", "").strip()
            section.is_active = request.POST.get("is_active") == "on"
            section.save()

            AuditService.log(
                user=request.user,
                action_type="SECTION_UPDATED",
                description=f"Updated section {section.name}",
            )
            messages.success(request, f"Section '{section.name}' updated successfully.")
            return redirect("admin_sections")
        except Department.DoesNotExist:
            messages.error(request, "Selected department does not exist.")

    return render(request, "attendance/admin/section_form.html", {"active_tab": "admin", "section": section, "departments": departments, "is_create": False})


# ==========================================================
# TEAMS CRUD
# ==========================================================

@admin_permission_required("role.manage")
def admin_teams(request):
    query = request.GET.get("q", "").strip()
    teams = Team.objects.all().select_related("section", "leader").order_by("-is_active", "name")

    if query:
        teams = teams.filter(Q(name__icontains=query) | Q(code__icontains=query))

    paginator = Paginator(teams, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"active_tab": "admin", "page_obj": page_obj, "query": query}
    return render(request, "attendance/admin/teams.html", context)


@admin_permission_required("role.manage")
def admin_team_create(request):
    sections = Section.objects.filter(is_active=True).order_by("name")
    users = User.objects.filter(is_active=True).order_by("username")

    if request.method == "POST":
        sec_code = request.POST.get("section", "").strip()
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        leader_id = request.POST.get("leader", "").strip()
        description = request.POST.get("description", "").strip()

        try:
            sec = Section.objects.get(code=sec_code)
            leader_obj = User.objects.get(id=leader_id) if leader_id else None

            if Team.objects.filter(code=code).exists():
                messages.error(request, f"Team code '{code}' already exists.")
            else:
                Team.objects.create(
                    section=sec,
                    name=name,
                    code=code,
                    leader=leader_obj,
                    description=description,
                )
                AuditService.log(
                    user=request.user,
                    action_type="TEAM_CREATED",
                    description=f"Created team {name} under section {sec.name}",
                )
                messages.success(request, f"Team '{name}' created successfully.")
                return redirect("admin_teams")
        except Section.DoesNotExist:
            messages.error(request, "Selected section does not exist.")
        except User.DoesNotExist:
            messages.error(request, "Selected leader does not exist.")

    return render(request, "attendance/admin/team_form.html", {"active_tab": "admin", "sections": sections, "users": users, "is_create": True})


@admin_permission_required("role.manage")
def admin_team_edit(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    sections = Section.objects.filter(is_active=True).order_by("name")
    users = User.objects.filter(is_active=True).order_by("username")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "deactivate":
            team.is_active = False
            team.save()
            AuditService.log(
                user=request.user,
                action_type="TEAM_DEACTIVATED",
                description=f"Deactivated team {team.name}",
            )
            messages.success(request, f"Team '{team.name}' soft-deleted successfully.")
            return redirect("admin_teams")
        elif action == "restore":
            team.is_active = True
            team.save()
            AuditService.log(
                user=request.user,
                action_type="TEAM_RESTORED",
                description=f"Restored team {team.name}",
            )
            messages.success(request, f"Team '{team.name}' restored successfully.")
            return redirect("admin_teams")

        sec_code = request.POST.get("section", "").strip()
        leader_id = request.POST.get("leader", "").strip()

        try:
            sec = Section.objects.get(code=sec_code)
            leader_obj = User.objects.get(id=leader_id) if leader_id else None

            team.section = sec
            team.name = request.POST.get("name", "").strip()
            team.leader = leader_obj
            team.description = request.POST.get("description", "").strip()
            team.is_active = request.POST.get("is_active") == "on"
            team.save()

            AuditService.log(
                user=request.user,
                action_type="TEAM_UPDATED",
                description=f"Updated team {team.name}",
            )
            messages.success(request, f"Team '{team.name}' updated successfully.")
            return redirect("admin_teams")
        except Section.DoesNotExist:
            messages.error(request, "Selected section does not exist.")
        except User.DoesNotExist:
            messages.error(request, "Selected leader does not exist.")

    return render(request, "attendance/admin/team_form.html", {"active_tab": "admin", "team": team, "sections": sections, "users": users, "is_create": False})


# ==========================================================
# ROLES CRUD & PERMISSIONS
# ==========================================================

@admin_permission_required("role.manage")
def admin_roles(request):
    query = request.GET.get("q", "").strip()
    roles = Role.objects.all().order_by("-is_active", "name")

    if query:
        roles = roles.filter(Q(name__icontains=query) | Q(code__icontains=query))

    paginator = Paginator(roles, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"active_tab": "admin", "page_obj": page_obj, "query": query}
    return render(request, "attendance/admin/roles.html", context)


@admin_permission_required("role.manage")
def admin_role_create(request):
    permissions_grouped = PermissionService.get_permissions_by_module()

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        description = request.POST.get("description", "").strip()
        data_scope = request.POST.get("data_scope", "OWN").strip()
        permission_ids = request.POST.getlist("permissions")

        role, msg = RoleService.create_role(
            name=name,
            code=code,
            description=description,
            data_scope=data_scope,
            created_by=request.user,
        )

        if role:
            PermissionService.update_role_permissions(role, [int(pid) for pid in permission_ids])
            AuditService.log(
                user=request.user,
                action_type="ROLE_CREATED",
                description=f"Created role {name} (code: {code}, scope: {data_scope})",
            )
            messages.success(request, msg)
            return redirect("admin_roles")
        else:
            messages.error(request, msg)

    context = {
        "active_tab": "admin",
        "permissions_grouped": permissions_grouped,
        "is_create": True,
    }
    return render(request, "attendance/admin/role_form.html", context)


@admin_permission_required("role.manage")
def admin_role_edit(request, role_id):
    role = get_object_or_404(Role, id=role_id)
    permissions_grouped = PermissionService.get_permissions_by_module()
    assigned_perm_ids = set(
        role.role_permissions.values_list("permission_id", flat=True)
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "deactivate":
            success, msg = RoleService.deactivate_role(role.id)
            if success:
                AuditService.log(
                    user=request.user,
                    action_type="ROLE_DEACTIVATED",
                    description=f"Deactivated role {role.name}",
                )
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect("admin_roles")
        elif action == "restore":
            role.is_active = True
            role.save()
            AuditService.log(
                user=request.user,
                action_type="ROLE_RESTORED",
                description=f"Restored role {role.name}",
            )
            messages.success(request, f"Role '{role.name}' restored successfully.")
            return redirect("admin_roles")

        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        data_scope = request.POST.get("data_scope", "OWN").strip()
        is_active = request.POST.get("is_active") == "on"
        permission_ids = request.POST.getlist("permissions")

        success, msg = RoleService.update_role(
            role_id=role.id,
            name=name,
            description=description,
            data_scope=data_scope,
            is_active=is_active,
        )

        if success:
            PermissionService.update_role_permissions(role, [int(pid) for pid in permission_ids])
            AuditService.log(
                user=request.user,
                action_type="ROLE_UPDATED",
                description=f"Updated role {role.name} and mapped permissions",
            )
            messages.success(request, msg)
            return redirect("admin_roles")
        else:
            messages.error(request, msg)

    context = {
        "active_tab": "admin",
        "role": role,
        "permissions_grouped": permissions_grouped,
        "assigned_perm_ids": assigned_perm_ids,
        "is_create": False,
    }
    return render(request, "attendance/admin/role_form.html", context)


@admin_permission_required("permission.manage")
def admin_permissions(request):
    permissions_grouped = PermissionService.get_permissions_by_module()
    context = {"active_tab": "admin", "permissions_grouped": permissions_grouped}
    return render(request, "attendance/admin/permissions.html", context)


# ==========================================================
# USERS CRUD (Hierarchical Assignment)
# ==========================================================

@admin_permission_required("user.manage")
def admin_users(request):
    query = request.GET.get("q", "").strip()
    role_filter = request.GET.get("role", "")
    company_filter = request.GET.get("company", "")
    plant_filter = request.GET.get("plant", "")
    department_filter = request.GET.get("department", "")

    users = User.objects.all().select_related("profile__role", "profile__company", "profile__plant", "profile__department", "profile__section", "profile__team").order_by("username")

    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )

    if role_filter:
        users = users.filter(profile__role__code=role_filter)
    if company_filter:
        users = users.filter(profile__company__code=company_filter)
    if plant_filter:
        users = users.filter(profile__plant__code=plant_filter)
    if department_filter:
        users = users.filter(profile__department__code=department_filter)

    paginator = Paginator(users, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    all_roles = Role.objects.filter(is_active=True).order_by("name")
    all_companies = Company.objects.filter(is_active=True).order_by("name")

    context = {
        "active_tab": "admin",
        "page_obj": page_obj,
        "query": query,
        "role_filter": role_filter,
        "company_filter": company_filter,
        "plant_filter": plant_filter,
        "department_filter": department_filter,
        "all_roles": all_roles,
        "all_companies": all_companies,
    }
    return render(request, "attendance/admin/users.html", context)


@admin_permission_required("user.manage")
def admin_user_edit(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=target_user)

    all_roles = Role.objects.filter(is_active=True).order_by("name")
    
    # Query plants for fixed company (ismartu)
    all_plants = Plant.objects.filter(company__code="ismartu", is_active=True)
    if profile.plant:
        all_plants = all_plants | Plant.objects.filter(id=profile.plant.id)
    all_plants = all_plants.distinct().order_by("name")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "reset_password":
            new_password = request.POST.get("new_password", "").strip()
            if not new_password:
                messages.error(request, "Password cannot be empty.")
            else:
                success, msg = UserService.reset_password(target_user.id, new_password)
                if success:
                    AuditService.log(
                        user=request.user,
                        action_type="USER_PASSWORD_RESET",
                        description=f"Reset password for user {target_user.username}",
                        target_user=target_user,
                    )
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            return redirect("admin_user_edit", user_id=target_user.id)

        role_code = request.POST.get("role", "")
        company_code = "ismartu"
        plant_code = request.POST.get("plant", "")
        sec_code = request.POST.get("section", "")
        team_code = request.POST.get("team", "")
        is_active = request.POST.get("is_active") == "on"

        try:
            role_obj = Role.objects.get(code=role_code)
            comp_obj = Company.objects.get(code=company_code) if company_code else None
            plant_obj = Plant.objects.get(code=plant_code) if plant_code else None
            sec_obj = Section.objects.get(code=sec_code) if sec_code else None
            team_obj = Team.objects.get(code=team_code) if team_code else None

            # Resolve parents automatically
            if team_obj and not sec_obj:
                sec_obj = team_obj.section
            
            dept_obj = None
            if sec_obj:
                dept_obj = sec_obj.department

            # Track changes for Audit
            changes = []
            if profile.role != role_obj:
                changes.append(f"role to {role_obj.name}")
            if profile.company != comp_obj:
                changes.append(f"company to {comp_obj.name if comp_obj else 'None'}")
            if profile.plant != plant_obj:
                changes.append(f"plant to {plant_obj.name if plant_obj else 'None'}")
            if profile.department != dept_obj:
                changes.append(f"department to {dept_obj.name if dept_obj else 'None'}")
            if profile.section != sec_obj:
                changes.append(f"section to {sec_obj.name if sec_obj else 'None'}")
            if profile.team != team_obj:
                changes.append(f"team to {team_obj.name if team_obj else 'None'}")

            profile.role = role_obj
            profile.company = comp_obj
            profile.plant = plant_obj
            profile.department = dept_obj
            profile.section = sec_obj
            profile.team = team_obj
            profile.save()

            target_user.is_active = is_active
            target_user.save()

            if changes:
                AuditService.log(
                    user=request.user,
                    action_type="ORG_ASSIGNMENT_CHANGED",
                    description=f"Changed user {target_user.username} assignment: {', '.join(changes)}",
                    target_user=target_user,
                )

            messages.success(request, f"User '{target_user.username}' updated successfully.")
            return redirect("admin_users")

        except Exception as e:
            messages.error(request, f"Error updating user profile: {e}")

    # Fetch sections under the plant for pre-populating on load
    all_sections = Section.objects.none()
    if profile.plant:
        all_sections = Section.objects.filter(department__plant=profile.plant, is_active=True)
        if profile.section:
            all_sections = all_sections | Section.objects.filter(id=profile.section.id)
        all_sections = all_sections.distinct().order_by("name")

    context = {
        "active_tab": "admin",
        "target_user": target_user,
        "profile": profile,
        "all_roles": all_roles,
        "all_plants": all_plants,
        "all_sections": all_sections,
    }
    return render(request, "attendance/admin/user_form.html", context)


# ==========================================================
# AUDIT LOGS VIEW
# ==========================================================

@admin_permission_required("role.manage")
def admin_audit_logs(request):
    query = request.GET.get("q", "").strip()
    logs = AuditLog.objects.all().select_related("user", "target_user").order_by("-timestamp")

    if query:
        logs = logs.filter(
            Q(action_type__icontains=query)
            | Q(description__icontains=query)
            | Q(user__username__icontains=query)
        )

    paginator = Paginator(logs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"active_tab": "admin", "page_obj": page_obj, "query": query}
    return render(request, "attendance/admin/audit_logs.html", context)


# ==========================================================
# BULK EXCEL IMPORT
# ==========================================================

@admin_permission_required("role.manage")
def admin_import_excel(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]
        success_count, errors = ImportService.import_from_excel(excel_file, request.user)

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            messages.success(request, f"Successfully imported {success_count} organizational nodes and employees.")
            return redirect("admin_dashboard")

    return render(request, "attendance/admin/import.html", {"active_tab": "admin"})


# ==========================================================
# AJAX ENDPOINT
# ==========================================================

def get_org_nodes(request):
    """
    AJAX endpoint to return JSON lists of plants, departments, sections, or teams
    dependent on the selected parent node.
    """
    node_type = request.GET.get("type")

    if node_type == "plants":
        company_code = request.GET.get("company_code")
        plants = Plant.objects.filter(company__code=company_code, is_active=True).order_by("name")
        data = [{"code": p.code, "name": p.name} for p in plants]
        return JsonResponse({"success": True, "data": data})

    elif node_type == "departments":
        plant_code = request.GET.get("plant_code")
        depts = Department.objects.filter(plant__code=plant_code, is_active=True).order_by("name")
        data = [{"code": d.code, "name": d.name} for d in depts]
        return JsonResponse({"success": True, "data": data})

    elif node_type == "sections":
        plant_code = request.GET.get("plant_code")
        dept_code = request.GET.get("department_code")
        if plant_code:
            sections = Section.objects.filter(department__plant__code=plant_code, is_active=True).order_by("name")
        else:
            sections = Section.objects.filter(department__code=dept_code, is_active=True).order_by("name")
        data = [{"code": s.code, "name": s.name} for s in sections]
        return JsonResponse({"success": True, "data": data})

    elif node_type == "teams":
        sec_code = request.GET.get("section_code")
        teams = Team.objects.filter(section__code=sec_code, is_active=True).order_by("name")
        data = [{"code": t.code, "name": t.name} for t in teams]
        return JsonResponse({"success": True, "data": data})

    return JsonResponse({"success": False, "message": "Invalid type parameter"}, status=400)
