from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path("contribute/", views.contribute_page, name="contribute_page"),
    path("feedback/", views.feedback_page, name="feedback_page"),
    path("post-login-check/", views.post_login_check, name=""),
    
    # path("sign-up/", views.sign_up.as_view(), name="sign_up"),
    path("aboutuser/<uuid:uuid>", views.signup_about , name="signup_about"),
    path("character/<uuid:uuid>", views.signup_character, name="signup_character"),
    path("skills/<uuid:uuid>", views.signup_skills, name="signup_skills"),
    path("", views.home_page, name="index"),
    path('load-more-feed/', views.load_more_feed, name='load_more_feed'),
    path('feed/log/<str:log_sig>/', views.view_log_in_feed, name='view_log_in_feed'),
    
    path("explore-dev/", views.explore_dev, name="explore_dev"),
    path("api/load-more-recommendations/", views.load_more_recommendations, name="load_more_recommendations"),
    path("api/search-developers/", views.search_developers_api, name="search_developers_api"),

    # User-profile
    path("user-profile/<str:user_name>/", views.user_profile, name="user_profile"),
    path("<str:username>/user-follow-list/", views.follow_list, name="follow_list"),
    path("unfollow/<int:otheruserinfo_id>/", views.unfollow_user, name = 'unfollow_user'),
    path("follow/<int:otheruserinfo_id>/", views.follow_user, name = 'follow_user'),
    path("api/quick-follow/", views.quick_follow_user, name='quick_follow_user'),

    path('update-banner/', views.update_banner, name='update_banner'),
    path("settings/", views.settings_page, name="settings_page"),
    path('delete-data/', views.delete_data, name = 'delete_data'),
    
    path("delete_account/<uuid:uuid>/", views.delete_account, name="delete_acount"),
    path('coding-style/update/', views.update_coding_style, name='update_coding_style'),
    path('coding-style/get/', views.get_coding_styles, name='get_coding_styles'),
    
    # Notifications
    path('notifications/', views.notification_page, name='notification_page'),
    path('notifications/load-more/', views.load_more_notifications, name='load_more_notifications'),
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('notifications/count/', views.get_notification_count_api, name='get_notification_count'),
    path('notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    
    # Geolocation (for Local feed) - MVP system
    path('api/geolocation/browser/update/', views.update_user_geolocation, name='update_browser_geolocation'),
    path('api/geolocation/ip/update/', views.update_ip_geolocation, name='update_ip_geolocation'),
    path('api/geolocation/status/', views.get_user_geolocation_status, name='geolocation_status'),
    path('api/geolocation/permission/denied/', views.set_permission_denied, name='set_permission_denied'),
]
