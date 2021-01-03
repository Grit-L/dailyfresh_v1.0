# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/4/14 9:38
"""
from django.urls import path
from order.views import OrderPlaceView, OrderCommitView, OrderCommitViewOPL
urlpatterns = [
	path('place', OrderPlaceView.as_view(), name='place'),
	path('commit', OrderCommitView.as_view(), name='commit'),
]
