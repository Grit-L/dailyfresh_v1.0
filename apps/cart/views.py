from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic.base import View
from django_redis import get_redis_connection
from django.contrib.auth.mixins import LoginRequiredMixin

from goods.models import GoodsSKU


# /cart/add
class CartAddView(View):
	def post(self, request):
		# 获取当前用户
		user = request.user
		# 校验用户是否登录
		if not user.is_authenticated:
			# 用户未登录
			return JsonResponse({'res': 0, 'errmsg': '请先登录用户'})
		# 获取数据
		sku_id = request.POST.get('sku_id')
		count = request.POST.get('count')
		# 校验数据
		# 1)完整性校验
		if not all([sku_id, count]):
			return JsonResponse({'res': 1, 'errmsg': '发送数据不完整'})
		# 2)sku_id是否存在
		try:
			sku = GoodsSKU.objects.get(id=sku_id)
		except GoodsSKU.DoesNotExist:
			return JsonResponse({'res': 2, 'errmsg': '商品不存在'})
		# 3）校验数目是否正确
		try:
			count = int(count)
		except Exception as e:
			return JsonResponse({'res': 3, 'errmsg': '商品数目错误'})
		# 业务处理
		cart_key = 'cart_%s' % user.id
		conn = get_redis_connection('default')
		# 判断商品是否已存在
		cart_count = conn.hget(cart_key, sku.id)
		if cart_count:
			# 若商品已在购物车，获取购物车中商品数目
			count += int(cart_count)
			# 校验商品的库存
		if count > sku.stock:
			return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})

		# 设置hash中sku_id对应的值
		# hset->如果sku_id已经存在，更新数据， 如果sku_id不存在，添加数据
		conn.hset(cart_key, sku_id, count)

		# 计算用户购物车商品的条目数
		total_count = conn.hlen(cart_key)

		return JsonResponse({'res': 5, 'total_count': total_count, 'msg': '添加成功'})


# /cart
class CartInfoView(LoginRequiredMixin, View):
	def get(self, request):
		user = request.user
		cart_key = 'cart_%s' % user.id
		conn = get_redis_connection('default')
		# 获取购物车商品
		# hgetall: 返回值{'商品id': 商品数量}
		skus_cart = conn.hgetall(cart_key)
		skus = []
		# total_count总数量 total_price总价格
		total_count = 0
		total_price = 0
		for sku_id, count in skus_cart.items():
			sku = GoodsSKU.objects.get(id=sku_id)
			price = sku.price
			count = int(count)
			amount = price*count
			total_count += count
			total_price += amount
			# 动态赋值 amount商品小计价格 count商品小计数量
			sku.amount = amount
			sku.count = count
			skus.append(sku)

		context = {
			'skus': skus,
			'total_count': total_count,
			'total_price': total_price
		}

		return render(request, 'cart.html', context)


# /cart/update
class CartUpdateView(View):
	def post(self, request):
		# 获取当前用户
		user = request.user
		# 校验用户是否登录
		if not user.is_authenticated:
			# 用户未登录
			return JsonResponse({'res': 0, 'errmsg': '请先登录用户'})
			# 获取数据
		sku_id = request.POST.get('sku_id')
		count = request.POST.get('count')
		# 校验数据
		# 1)完整性校验
		if not all([sku_id, count]):
			return JsonResponse({'res': 1, 'errmsg': '发送数据不完整'})
		# 2)sku_id是否存在
		try:
			sku = GoodsSKU.objects.get(id=sku_id)
		except GoodsSKU.DoesNotExist:
			return JsonResponse({'res': 2, 'errmsg': '商品不存在'})
		# 3）校验数目是否正确
		try:
			count = int(count)
		except Exception as e:
			return JsonResponse({'res': 3, 'errmsg': '商品数目错误'})
		# 业务处理
		# 校验商品的库存
		if count > sku.stock:
			return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})

		conn = get_redis_connection('default')
		cart_key = 'cart_%s' % user.id
		# 重新设置商品的数量值
		conn.hset(cart_key, sku_id, count)

		# 计算购物车中商品的总件数
		total_count = 0
		# 返回一个列表，值为各个商品的数量
		val_list = conn.hvals(cart_key)
		for count in val_list:
			total_count += int(count)

		return JsonResponse({'res': 5, 'total_count': total_count})


class CartDeleteView(View):
	def post(self, request):
		# 获取当前用户
		user = request.user
		# 校验用户是否登录
		if not user.is_authenticated:
			# 用户未登录
			return JsonResponse({'res': 0, 'errmsg': '请先登录用户'})
		# 获取数据
		sku_id = request.POST.get('sku_id')
		count = request.POST.get('count')
		# 校验数据
		# 1)完整性校验
		if not sku_id:
			return JsonResponse({'res': 1, 'errmsg': '无效的商品id'})
		# 2)sku_id是否存在
		try:
			sku = GoodsSKU.objects.get(id=sku_id)
		except GoodsSKU.DoesNotExist:
			return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

		# 业务处理
		conn = get_redis_connection('default')
		cart_key = 'cart_%s' % user.id
		# 删除对应的商品
		conn.hdel(cart_key, sku_id)

		# 计算购物车中商品的总件数
		total_count = 0
		# 返回一个列表，值为各个商品的数量
		val_list = conn.hvals(cart_key)
		for count in val_list:
			total_count += int(count)

		return JsonResponse({'res': 3, 'total_count': total_count})
