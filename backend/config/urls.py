from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("users.urls")),
    path("groups/", include("students.urls")),
    path("students/", include("students.students_urls")),
    path("attendance/", include("attendance.urls")),
    path("bot/", include("notifications.urls")),
    path("", RedirectView.as_view(url="/groups/", permanent=False)),
]
