from django.urls import path
from . import views

urlpatterns = [
    path('', views.preference_group_list, name='group_list'),
    path('groups/new/', views.preference_group_create, name='group_create'),
    path('groups/<int:group_id>/edit/', views.preference_group_edit, name='group_edit'),
    path('groups/<int:group_id>/delete/', views.preference_group_delete, name='group_delete'),
]