from django.contrib import admin
from .models import Teacher, Parent

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ["full_name", "subject", "user"]

@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ["full_name", "telegram_id", "phone"]
