# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/6/12 16:56
"""
from celery import Celery
from django.core.mail import send_mail
from dailyfresh import settings
# broker和worker在同一台机子上则需要加上本段代码
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
django.setup()

app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/1')


@app.task
def send_register_active_email(to_mail, username, token):
    subject = '天天生鲜欢迎信息'
    sender = settings.EMAIL_HOST_USER
    html_message = '<h1>%s, 欢迎成为天天生鲜注册会员<h1>' \
                   '请点击下面链接激活账户<br/>' \
                   '<a href="http://127.0.0.1:8000/user/active/%s">' \
                   'http://127.0.0.1:8000/user/active/%s</a>' % (username, token, token)
    receiver = [to_mail]
    send_mail(subject=subject, message='', from_email=sender, recipient_list=receiver, html_message=html_message)
