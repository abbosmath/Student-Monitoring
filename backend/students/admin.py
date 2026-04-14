from django.contrib import admin
from .models import Group, Student, GroupMembership, Schedule


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "subject", "teacher", "student_count"]

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["full_name", "parent", "total_points"]

@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["student", "group"]

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ["group", "day_of_week", "start_time", "end_time"]
