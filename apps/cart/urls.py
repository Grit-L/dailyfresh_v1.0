# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/4/14 9:38
"""
from django.urls import path

from cart.views import CartAddView, CartInfoView, CartUpdateView, \
	CartDeleteView

urlpatterns = [
	path('add', CartAddView.as_view(), name='add'),  # 添加购物车
	path('', CartInfoView.as_view(), name='show'),  # 购物车详情页
	path('update', CartUpdateView.as_view(), name='update'),  # 更新购物车商品数量
	path('delete', CartDeleteView.as_view(), name='delete')  # 删除购物车商品
]
