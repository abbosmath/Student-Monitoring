from django.urls import path
from students.views.groups import (
    groups_list,
    group_create,
    group_detail,
    group_edit,
    group_delete,
    add_student_to_group,
    remove_student_from_group,
)

urlpatterns = [
    path("", groups_list, name="groups_list"),
    path("create/", group_create, name="group_create"),
    path("<int:group_id>/", group_detail, name="group_detail"),
    path("<int:group_id>/edit/", group_edit, name="group_edit"),
    path("<int:group_id>/delete/", group_delete, name="group_delete"),
    path("<int:group_id>/add-student/", add_student_to_group, name="add_student_to_group"),
    path("<int:group_id>/remove-student/<int:student_id>/", remove_student_from_group, name="remove_student_from_group"),
]
