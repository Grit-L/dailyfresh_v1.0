# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/4/14 9:38
"""
from django.urls import path
from apps.goods import views


urlpatterns = [
    path('index/', views.index, name='index'),
    path('', views.index, name='index'),
]
