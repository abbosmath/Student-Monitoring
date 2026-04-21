from django.urls import path
from students.views.students import (
    students_list,
    student_create,
    student_detail,
    student_edit,
    student_delete,
    give_points,
    deduct_points,
)

urlpatterns = [
    path("", students_list, name="students_list"),
    path("create/", student_create, name="student_create"),
    path("<int:student_id>/", student_detail, name="student_detail"),
    path("<int:student_id>/edit/", student_edit, name="student_edit"),
    path("<int:student_id>/delete/", student_delete, name="student_delete"),
    path("<int:student_id>/points/", give_points, name="give_points"),
    path("<int:student_id>/deduct/", deduct_points, name="deduct_points"),
]
