# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/4/14 9:38
"""
from django.urls import path, re_path
from apps.user import views
from user.views import RegisterView, ActiveView, LoginView


urlpatterns = [
    path('register', RegisterView.as_view(), name='register'),
    re_path('active/(?P<token>.*)$', ActiveView.as_view(), name='active'),
    path('login', LoginView.as_view(), name='login'),
    path('logout', LoginView.as_view(), name='logout'),
]
