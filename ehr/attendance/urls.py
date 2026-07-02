from django.urls import path
# pyrefly: ignore [missing-import]
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("api/", views.attendance_api, name="attendance_api"),
]