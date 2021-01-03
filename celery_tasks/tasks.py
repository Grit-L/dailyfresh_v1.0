# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/6/12 16:56
"""
from celery import Celery
from django.core.mail import send_mail
from django.template import loader

from dailyfresh import settings

# broker和worker在同一台机子上则需要加上本段代码
# django环境变量初始化
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
django.setup()


from goods.models import GoodsType, IndexGoodsBanner, \
    IndexTypeGoodsBanner, IndexPromotionBanner

# 创建Celery类实例对象
app = Celery('celery_tasks.tasks', broker='redis://*.*.*.*:6379/1')

# 定义任务函数
# 用户注册发送激活邮件
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


# 生成静态页面
@app.task
def generic_static_index_html():
    types = GoodsType.objects.all()
    # 获取首页轮播商品信息
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')
    # 获取首页促销活动信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 获取首页分类商品展示信息
    for type in types:
        # 获取type种类首页分类商品的图片展示信息
        goods_images = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
        # 获取type种类首页分类商品的文字展示信息
        goods_titles = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')

        # type动态增加属性
        type.image_banners = goods_images
        type.title_banners = goods_titles

    # 组织上下文
    context = {
        'types': types,
        'goods_banners': goods_banners,
        'promotion_banners': promotion_banners,
    }
    # 生成模板文件对象
    temp = loader.get_template('static_index.html')
    static_index_html = temp.render(context)
    # 讲生成的静态文件放在static页面下面
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
    with open(save_path, 'w') as fp:
        fp.write(static_index_html)
