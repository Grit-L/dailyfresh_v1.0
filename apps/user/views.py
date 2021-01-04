from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
import re

from user.models import User, Address
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
# from utils.mixin import LoginRequiredMixin

from celery_tasks.tasks import send_register_active_email
from dailyfresh import settings


# /user/register
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
			return render(request, 'register.html', {'errmsg': '请同意协议!'})
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
		return redirect(reverse('user:login'))


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
			# 跳转到登录页面
			return redirect(reverse('user:login'))
		except SignatureExpired:
			return HttpResponse('激活链接已失效，请重新发送')


# /user/login
class LoginView(View):
	"""
	登录视图
	"""

	def get(self, request):
		if 'username' in request.COOKIES:
			username = request.COOKIES.get('username')
			checked = 'checked'
		else:
			username = ''
			checked = ''
		return render(request, 'login.html', {'username': username, 'checked': checked})

	def post(self, request):
		# 获取数据
		username = request.POST.get('username')
		password = request.POST.get('pwd')

		# 校验数据
		if not all([username, password]):
			return render(request, 'login.html', {'errmsg': '请输入账号或密码'})

		# 登录校验 业务处理
		user = authenticate(username=username, password=password)
		# print(user)
		if user is not None:
			# 判断用户是否激活
			if user.is_active:
				# 记录登陆状态 session
				login(request, user)
				# 获取登录后跳转地址
				# 从哪个页面退出，登录后就进入哪个页面。若next为none 默认进入后面那个页面
				next_url = request.GET.get('next', reverse('goods:index'))
				response = redirect(next_url)

				# 是否记住用户名
				remember = request.POST.get('remember')
				if remember == 'on':
					response.set_cookie('username', username, max_age=24 * 3600)
				else:
					response.delete_cookie('username')
				return response
			else:
				return render(request, 'login.html', {'errmsg': '账户未激活'})
		else:
			return render(request, 'login.html', {'errmsg': '用户名或密码错误'})


# /user/logout
class LogoutView(View):
	"""
	退出视图
	"""

	def get(self, request):
		# 删除session
		logout(request)
		return redirect(reverse('goods:index'))


# /user
class UserInfoView(LoginRequiredMixin, View):
	"""
	用户中心 用户信息
	"""

	def get(self, request):
		user = request.user
		address = Address.objects.get_default_address(user)
		# 获取历史浏览记录
		# 获取redis基本配置，连接
		con = get_redis_connection('default')
		history_key = 'history_%s' % user.id
		# 获取用户最新浏览商品id
		sku_li = con.lrange(history_key, 0, 4)
		# 数据库查询商品的具体信息
		goods_li = []
		for sku_id in sku_li:
			good = GoodsSKU.objects.get(id=sku_id)
			goods_li.append(good)
		# 组织上下文
		context = {'page': 'user',
		           'address': address,
		           'goods': goods_li
		           }
		return render(request, 'user_center_info.html', context=context)


# /user/order
class UserOrderView(LoginRequiredMixin, View):
	"""
	用户中心 全部订单
	"""

	def get(self, request, page):
		# 获取数据
		user = request.user
		# 获取订单数据
		orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

		if not page:
			return redirect(reverse('user:user'))
		# 获取订单商品数据
		for order in orders:
			order_skus = OrderGoods.objects.filter(order_id=order.order_id)
			for order_sku in order_skus:
				price = order_sku.price
				count = order_sku.count
				amount = price*int(count)
				order_sku.amount = amount

			# 动态给order增加属性，保存订单状态标题
			order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
			# 动态给order增加属性，保存订单商品的信息
			order.order_skus = order_skus
		# 分页
		# 获取分页信息
		# 1) 生成paginator对象
		# 属性：num_pages(总页数) page_range(页数列表 [1, 2, 3, 4])
		paginator = Paginator(orders, 3)
		# 2) 获取第page页的内容
		try:
			page = int(page)
		except Exception as e:
			page = 1
		if page > paginator.num_pages:
			page = 1
		# 3) 获取page对象
		# 方法：//has_next() //has_previous()
		# 属性：//object_list(此页上的对象列表) number(此页的基于 1 的页码)
		#       paginator (关联的 Paginator 对象。)
		order_page = paginator.page(page)

		# 列表数展示控制，页面上最多显示5个页码
		# 1.总页数小于5页，页面上显示所有页码
		# 2.如果当前页是前3页，显示1-5页
		# 3.如果当前页是后3页，显示后5页
		# 4.其他情况，显示当前页的前2页，当前页，当前页的后2页
		num_pages = paginator.num_pages
		if num_pages < 5:
			pages = range(1, num_pages)
		elif page <= 3:
			pages = range(1, 6)
		elif num_pages - page <= 2:
			pages = range(num_pages - 4, num_pages + 1)
		else:
			pages = range(page - 2, page + 3)

		context={
			'order_page': order_page,
			'pages': pages,
			'page': 'order'
		}
		return render(request, 'user_center_order.html', context)


# /user/address
class UserAddressView(LoginRequiredMixin, View):
	"""
	用户中心 地址
	"""

	def get(self, request):
		# 获取用户地址
		user = request.user
		try:
			address = Address.objects.get(user=user, is_default=True)
		except Address.DoesNotExist:
			address = None
		# address = Address.objects.get_default_address(user)
		# 获取全部地址
		addresses = Address.objects.filter(user=user)

		return render(request, 'user_center_site.html',
		              {'page': 'address', 'address': address, 'addresses': addresses})

	def post(self, request):
		# 获取数据
		receiver = request.POST.get('receiver')
		addr = request.POST.get('addr')
		zip_code = request.POST.get('zip_code')
		phone = request.POST.get('phone')
		print("%s:%s:%s" % (receiver, addr, phone))
		# 数据校验
		if not all([receiver, addr, phone]):
			return render(request, 'user_center_site.html', {'errmsg': '请完善数据'})
		if not re.match(r'^1[3589]\d{9}$|^147\d{8}$|^179\d{8}$', phone):
			return render(request, 'user_center_site.html', {'errmsg': '请输入正确手机号码'})
		if len(zip_code) != 6:
			return render(request, 'user_center_site.html', {'errmsg': '邮件编码错误'})

		# 业务处理,如果用户已存在默认收货地址，添加的地址不作为默认地址，否则作为默认
		user = request.user
		address = Address.objects.get_default_address(user)

		if address:
			is_default = False
		else:
			is_default = True

		# 添加到数据库
		addr = Address.objects.create(user=user,
		                              receiver=receiver,
		                              addr=addr,
		                              zip_code=zip_code,
		                              phone=phone,
		                              is_default=is_default)
		addr.save()
		# 返回视图
		return redirect(reverse('user:address'))
