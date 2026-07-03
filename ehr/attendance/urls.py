from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    
    # HRMS Employee Module
    path("employees/", views.employee_list, name="employee_list"),
    path("employee/<str:employee_id>/", views.employee_detail, name="employee_detail"),
    
    # HRMS Request Portals
    path("leaves/", views.leave_portal, name="leave_portal"),
    path("overtime/", views.overtime_portal, name="overtime_portal"),
    path("corrections/", views.correction_portal, name="correction_portal"),
    
    # HRMS Approval Portal (Managers & HR Admins)
    path("approvals/", views.approval_portal, name="approval_portal"),
    
    # HRMS Reports & Export Services
    path("reports/", views.reports_portal, name="reports_portal"),
    path("reports/export/", views.export_report, name="export_report"),
]