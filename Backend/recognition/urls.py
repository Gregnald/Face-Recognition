from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
import os
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('live_feed/', views.live_feed, name='live_feed'),
    path('live_video/', views.live_video, name='live_video'),
    path('capture_frame/', views.capture_frame, name='capture_frame'),
    path('login', views.login, name="login"),
    path('userlogin/', views.userlogin, name='userlogin'),
    path('signup', views.signup, name="signup"),
    path('usersignup/', views.usersignup, name='usersignup'),
] + static('/captured_frames/', document_root=os.path.join(settings.BASE_DIR, 'captured_frames'))