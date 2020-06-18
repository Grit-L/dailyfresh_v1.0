from django.contrib.auth import authenticate,login
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
import re

from user.models import User
from celery_tasks.tasks import send_register_active_email
from dailyfresh import settings


class RegisterView(View):
    """
    注册类视图
    """
    def get(self, request):
        """
        显示注册页面
        :param request:
        :return:
        """
        return render(request, 'register.html')

    def post(self, request):
        """
        进行注册处理
        :param request:
        :return:
        """
        # 数据校验
        # 获取数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 是否为空判断
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '用户信息不完善'})
        # 邮箱校验
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        # 是否统一协议
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})
        # 校验用户名是否重复
        # 如果数据库不存在数据，使用get方法会出现错误
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            User.username = None

        if User.username:
            return render(request, 'register.html', {'errmsg': '用户已存在'})

        # 进行业务处理：进行注册,django内置的用户认证系统
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()
        # 发送激活邮件，包含激活链接 /user/active/id
        # 加密用户的身份信息,生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info).decode('utf-8')
        # 异步发送邮件
        send_register_active_email.delay(email, username, token)
        # 返回应答,跳转到index
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """
    激活视图
    """

    def get(self, request, token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info['confirm']
            # 根据id获取用户,将账号激活
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            return redirect(reverse('user:login'))
        except SignatureExpired:
            return HttpResponse('激活链接已失效，请重新发送')


class LoginView(View):
    """
    登录视图
    """
    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        # 获取数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '请输入账号或密码'})

        # 登录校验 业务处理
        user = authenticate(username=username, password=password)
        if user is not None:
            # 判断用户是否激活
            if user.is_active:
                login(request, user)
                # 登录后跳转
                next_url = request.GET.get('next', reverse('goods:index'))
                response = redirect(next_url)

                # 是否记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    response.set_cookie('username', username, max_age=24 * 3600)
                else:
                    response.delete_cookie(username)
            else:
                return HttpResponse(request, 'login.html', {'errmsg': '账户未激活'})
        else:
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})
