from django.urls import path
# pyrefly: ignore [missing-import]
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("api/attendance/", views.attendance_api, name="attendance_api"),
    path("overtime/", views.overtime_dashboard, name="overtime"),
    path("leaves/", views.mispunch_dashboard, name="leaves"),
]
