# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/4/14 9:38
"""
from django.urls import path

from apps.goods import views

urlpatterns = [
    path('', views.inderx, name='index'),
    path('index/', views.inderx, name='index'),
]
