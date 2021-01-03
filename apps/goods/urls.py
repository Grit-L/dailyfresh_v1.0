# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/4/14 9:38
"""
from django.urls import path, re_path

from goods.views import IndexView, GoodsDetailView, GoodsListView

urlpatterns = [
    path('index', IndexView.as_view(), name='index'),
    path('goods/<int:goods_id>', GoodsDetailView.as_view(), name='detail'),
	path('list/<int:type_id>/<int:page>', GoodsListView.as_view(), name='list'),

]
