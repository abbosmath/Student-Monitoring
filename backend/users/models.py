from django.contrib.auth.models import User
from django.db import models


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="teacher")
    full_name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.full_name or self.user.username


class Parent(models.Model):
    full_name = models.CharField(max_length=255)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.full_name
