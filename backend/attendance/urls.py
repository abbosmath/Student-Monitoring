from django.urls import path
from . import views

urlpatterns = [
    path("<int:group_id>/", views.take_attendance, name="take_attendance"),
    path("<int:group_id>/history/", views.attendance_history, name="attendance_history"),
]
