# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/4/14 9:38
"""
from django.urls import path, re_path
from apps.user import views
from user.views import RegisterView, ActiveView, LoginView, LogoutView, UserInfoView\
    , UserOrderView, UserAddressView


urlpatterns = [
    path('register', RegisterView.as_view(), name='register'),
    re_path('active/(?P<token>.*)$', ActiveView.as_view(), name='active'),
    path('login', LoginView.as_view(), name='login'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('', UserInfoView.as_view(), name='user'),
    path('order', UserOrderView.as_view(), name='order'),
    path('address', UserAddressView.as_view(), name='address'),
]
