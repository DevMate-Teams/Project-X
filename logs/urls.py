from django.urls import path
from . import views

urlpatterns = [
    path("save-log/", views.save_log, name="save_log"),
    path("delete-log/<str:sig>/", views.delete_log, name="delete_log"),
    path("reaction/<str:sig>/", views.toggle_reaction, name="toggle_reaction"),
    path("comment/add/<str:sig>/", views.add_comment, name="add_comment"),
    path("comment/delete/<int:comment_id>/", views.delete_comment, name="delete_comment"),
    
    path("load-more-profile-logs/<str:username>/", views.load_more_profile_logs, name="load_more_profile_logs"),
    
]
