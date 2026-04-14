from django.contrib import admin
from .models import Attendance, Performance

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["student", "group", "date", "status"]
    list_filter = ["status", "group", "date"]

@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
    list_display = ["student", "points", "comment", "date", "teacher"]
