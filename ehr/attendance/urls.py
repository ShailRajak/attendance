from django.urls import path

# pyrefly: ignore [missing-import]
from . import views
# pyrefly: ignore [missing-import]
from . import views_admin

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("api/attendance/", views.attendance_api, name="attendance_api"),
    path("api/attendance/chart-drilldown/", views.attendance_drilldown_api, name="attendance_drilldown_api"),
    path("overtime/", views.overtime_dashboard, name="overtime"),
    path("leaves/", views.leaves_dashboard, name="leaves"),
    path("feedback/", views.submit_feedback, name="feedback"),
    path("sw.js", views.pwa_service_worker, name="pwa_service_worker"),
    path("manifest.json", views.pwa_manifest, name="pwa_manifest"),
    path("offline/", views.offline_view, name="offline"),

    # Administration Portal
    path("admin-portal/", views_admin.admin_dashboard, name="admin_dashboard"),
    
    # Companies
    path("admin-portal/companies/", views_admin.admin_companies, name="admin_companies"),
    path("admin-portal/companies/create/", views_admin.admin_company_create, name="admin_company_create"),
    path("admin-portal/companies/<int:comp_id>/edit/", views_admin.admin_company_edit, name="admin_company_edit"),

    # Plants
    path("admin-portal/plants/", views_admin.admin_plants, name="admin_plants"),
    path("admin-portal/plants/create/", views_admin.admin_plant_create, name="admin_plant_create"),
    path("admin-portal/plants/<int:plant_id>/edit/", views_admin.admin_plant_edit, name="admin_plant_edit"),

    # Departments
    path("admin-portal/departments/", views_admin.admin_departments, name="admin_departments"),
    path("admin-portal/departments/create/", views_admin.admin_department_create, name="admin_department_create"),
    path("admin-portal/departments/<int:dept_id>/edit/", views_admin.admin_department_edit, name="admin_department_edit"),

    # Sections
    path("admin-portal/sections/", views_admin.admin_sections, name="admin_sections"),
    path("admin-portal/sections/create/", views_admin.admin_section_create, name="admin_section_create"),
    path("admin-portal/sections/<int:sec_id>/edit/", views_admin.admin_section_edit, name="admin_section_edit"),

    # Teams
    path("admin-portal/teams/", views_admin.admin_teams, name="admin_teams"),
    path("admin-portal/teams/create/", views_admin.admin_team_create, name="admin_team_create"),
    path("admin-portal/teams/<int:team_id>/edit/", views_admin.admin_team_edit, name="admin_team_edit"),

    # Roles
    path("admin-portal/roles/", views_admin.admin_roles, name="admin_roles"),
    path("admin-portal/roles/create/", views_admin.admin_role_create, name="admin_role_create"),
    path("admin-portal/roles/<int:role_id>/edit/", views_admin.admin_role_edit, name="admin_role_edit"),

    # Permissions
    path("admin-portal/permissions/", views_admin.admin_permissions, name="admin_permissions"),

    # Users
    path("admin-portal/users/", views_admin.admin_users, name="admin_users"),
    path("admin-portal/users/<int:user_id>/edit/", views_admin.admin_user_edit, name="admin_user_edit"),

    # Audit Logs
    path("admin-portal/audit-logs/", views_admin.admin_audit_logs, name="admin_audit_logs"),

    # Import Excel
    path("admin-portal/import/", views_admin.admin_import_excel, name="admin_import_excel"),

    # AJAX Dynamic Node Loading
    path("api/org-nodes/", views_admin.get_org_nodes, name="get_org_nodes"),
]
