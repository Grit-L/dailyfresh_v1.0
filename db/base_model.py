# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/4/14 10:46
"""
from django.db import models


class BaseModel(models.Model):
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    edit_time = models.DateTimeField(auto_now=True, verbose_name='修改时间')
    is_del = models.BooleanField(default=False, verbose_name='删除标识')

    class Meta:
        """说明是个抽象模型类"""
        abstract = True
