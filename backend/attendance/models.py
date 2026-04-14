from django.db import models
from students.models import Student, Group
from users.models import Teacher


class Attendance(models.Model):
    STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("late", "Late"),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendances")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "group", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student} - {self.date} - {self.status}"


class Performance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="performances")
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True)
    points = models.IntegerField()
    comment = models.TextField(blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student} +{self.points} pts"
