from datetime import datetime

from alipay import AliPay
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic.base import View
from django_redis import get_redis_connection

from order.models import OrderInfo, OrderGoods
from goods.models import GoodsSKU
from user.models import Address


# /order/place
from dailyfresh import settings


class OrderPlaceView(View):
	'''
	订单页
	'''
	def post(self, request):
		user = request.user
		# 获取数据
		sku_id_list = request.POST.getlist('sku_ids')
		# 校验数据
		if not sku_id_list:
			# 购物车数据为空，跳转回购物车页
			return redirect(reverse('cart:show'))
		conn = get_redis_connection('default')
		cart_key = 'cart_%d' % user.id

		skus = []
		total_count = 0
		total_price = 0

		for sku_id in sku_id_list:
			sku = GoodsSKU.objects.get(id=sku_id)
			# 数目从redis获取
			count = conn.hget(cart_key, sku_id)
			count = int(count)
			amount = sku.price*count
			# 动态赋值
			sku.amount = amount
			sku.count = count
			skus.append(sku)
			total_count += count
			total_price += amount

		# 邮费价格
		transit_price = 10
		# 总的需要支付价格
		total_pay = transit_price + total_price
		# 邮寄地址
		addrs = Address.objects.filter(user=user)
		# 转换成字符串形式
		sku_ids = ','.join(sku_id_list)

		context = {
			'skus': skus,
			'total_count': total_count,
			'total_price': total_price,
			'transit_price': transit_price,
			'total_pay': total_pay,
			'addrs': addrs,
			'sku_ids': sku_ids}

		return render(request, 'place_order.html', context)


# /order/commit
# 加悲观锁处理并发问题
class OrderCommitView(View):
	'''
	订单提交
	'''
	@transaction.atomic
	def post(self, request):
		user = request.user
		if not user.is_authenticated:
			# 用户未登录
			return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
		# 获取数据
		addr_id = request.POST.get('addr_id')
		pay_method = request.POST.get('pay_method')
		sku_ids = request.POST.get('sku_ids')

		# 校验数据
		# 完整性校验
		if not all([addr_id, pay_method, sku_ids]):
			return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
		# 支付方式校验
		if pay_method not in OrderInfo.PAY_METHODS.keys():
			return JsonResponse({'res': 2, 'errmsg': '支付方式不存在'})
		# 校验地址
		try:
			addr = Address.objects.get(id=addr_id)
		except Address.DoesNotExist:
			return JsonResponse({'res': 7, 'errmsg': '地址不存在'})

		# todo: 其余df_order_info 订单数据库字段获取
		# 订单id: 20171122181630 + 用户id
		order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
		# 运费写死
		transit_price = 10
		# 数量和价格小计先设置为0 后面再获取
		total_count = 0
		total_price = 0

		# todo: 设置事务保存点
		save_id = transaction.savepoint()
		try:
			# 业务处理
			# todo: 添加到订单表
			order = OrderInfo.objects.create(order_id=order_id,
			                                 user=user,
			                                 addr=addr,
			                                 pay_method=pay_method,
			                                 total_count=total_count,
			                                 total_price=total_price,
			                                 transit_price=transit_price
			                                 )
			# todo: 用户的订单中有几个商品，需要向df_order_goods表中加入几条记录
			conn = get_redis_connection('default')
			cart_key = 'cart_%s' % user.id

			sku_ids = sku_ids.split(',')
			# 判断sku_ids字段
			for sku_id in sku_ids:
				try:
					# select * from df_goods_sku where id=sku_id for update;
					# 加悲观锁查询
					sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
				except GoodsSKU.DoesNotExist:
					# 商品不存在,事务回滚
					transaction.savepoint_rollback(save_id)
					return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

				# redis数据库获取count
				count = conn.hget(cart_key, sku_id)
				count = int(count)
				price = sku.price

				# 判断库存
				if count > sku.stock:
					# 事务回滚
					transaction.savepoint_rollback(save_id)
					JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

				# todo: 向df_order_goods表中添加一条记录
				OrderGoods.objects.create(order=order,
				                          sku=sku,
				                          count=count,
				                          price=price
				                          )

				# todo:  库存以及销量改变
				sku.stock -= count
				sku.sales += count
				sku.save()
				# todo: 累加计算订单商品的总数量和总价格
				amount = price * count
				total_count += count
				total_price += amount

			# todo: 更新订单信息表中的商品的总数量和总价格
			order.total_count = total_count
			order.total_price = total_price
			order.save()
		except Exception as e:
			# 事务回滚
			transaction.savepoint_rollback(save_id)
			print(e)
			return JsonResponse({'res': 4, 'errmsg': '下单失败'})

		# 提交事务
		transaction.savepoint_commit(save_id)
		# todo: 删除购物车 解包：*sku_ids -> 1,4,3
		conn.hdel(cart_key, *sku_ids)
		return JsonResponse({'res': 5, 'message': '成功下单'})


# /order/commit
# 加乐观锁处理并发问题
class OrderCommitViewOPL(View):
	'''
	订单提交
	'''
	@transaction.atomic
	def post(self, request):
		user = request.user
		if not user.is_authenticated:
			# 用户未登录
			return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
		# 获取数据
		addr_id = request.POST.get('addr_id')
		pay_method = request.POST.get('pay_method')
		sku_ids = request.POST.get('sku_ids')

		# 校验数据
		# 完整性校验
		if not all([addr_id, pay_method, sku_ids]):
			return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
		# 支付方式校验
		if pay_method not in OrderInfo.PAY_METHODS.keys():
			return JsonResponse({'res': 2, 'errmsg': '支付方式不存在'})
		# 校验地址
		try:
			addr = Address.objects.get(id=addr_id)
		except Address.DoesNotExist:
			return JsonResponse({'res': 7, 'errmsg': '地址不存在'})

		# todo: 其余df_order_info 订单数据库字段获取
		# 订单id: 20171122181630 + 用户id
		order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
		# 运费写死
		transit_price = 10
		# 数量和价格小计先设置为0 后面再获取
		total_count = 0
		total_price = 0

		# todo: 设置事务保存点
		save_id = transaction.savepoint()
		try:
			# 业务处理
			# todo: 添加到订单表
			order = OrderInfo.objects.create(order_id=order_id,
			                                 user=user,
			                                 addr=addr,
			                                 pay_method=pay_method,
			                                 total_count=total_count,
			                                 total_price=total_price,
			                                 transit_price=transit_price
			                                 )
			# todo: 用户的订单中有几个商品，需要向df_order_goods表中加入几条记录
			conn = get_redis_connection('default')
			cart_key = 'cart_%s' % user.id

			sku_ids = sku_ids.split(',')
			# 判断sku_ids字段
			for sku_id in sku_ids:
				for i in range(3):
					try:
						# select * from df_goods_sku where id=sku_id for update;
						# 加悲观锁查询
						sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
					except GoodsSKU.DoesNotExist:
						# 商品不存在,事务回滚
						transaction.savepoint_rollback(save_id)
						return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

					# redis数据库获取count
					count = conn.hget(cart_key, sku_id)
					count = int(count)
					price = sku.price

					# 判断库存
					if count > sku.stock:
						# 事务回滚
						transaction.savepoint_rollback(save_id)
						JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

					# todo:  库存以及销量改变 判断插入时的库存是否与之前查询一致
					# 乐观锁
					origin_stock = sku.stock
					new_sales = count + sku.sales
					new_stock = origin_stock - count
					# return:修改成功条数, 成功 1 失败 0
					res = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(sales=new_sales, stock=new_stock)

					if res == 0:
						if i == 2:
							# 第三次失败, 事务回滚
							transaction.savepoint_rollback(save_id)
						# 循环3次
						continue

					# todo: 向df_order_goods表中添加一条记录
					OrderGoods.objects.create(order=order,
					                          sku=sku,
					                          count=count,
					                          price=price
					                          )

					# todo: 累加计算订单商品的总数量和总价格
					amount = price * count
					total_count += count
					total_price += amount

					# 添加数据成功退循环
					break

			# todo: 更新订单信息表中的商品的总数量和总价格
			order.total_count = total_count
			order.total_price = total_price
			order.save()
		except Exception as e:
			# 事务回滚
			transaction.savepoint_rollback(save_id)
			print(e)
			return JsonResponse({'res': 4, 'errmsg': '下单失败'})

		# 提交事务
		transaction.savepoint_commit(save_id)
		# todo: 删除购物车 解包：*sku_ids -> 1,4,3
		conn.hdel(cart_key, *sku_ids)
		return JsonResponse({'res': 5, 'message': '成功下单'})


# ajax post
# 前端传递的参数:订单id(order_id)
# /order/pay
class OrderPayView(View):
	'''订单支付'''

	def post(self, request):
		'''订单支付'''
		# 用户是否登录
		user = request.user
		if not user.is_authenticated:
			return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

		# 接收参数
		order_id = request.POST.get('order_id')

		# 校验参数
		if not order_id:
			return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

		try:
			order = OrderInfo.objects.get(order_id=order_id,
			                              user=user,
			                              pay_method=3,
			                              order_status=1)
		except OrderInfo.DoesNotExist:
			return JsonResponse({'res': 2, 'errmsg': '订单错误'})

		# 业务处理:使用python sdk调用支付宝的支付接口
		# 初始化
		alipay = AliPay(
			appid=settings.ALIPAY_APP_ID,  # 应用id
			app_notify_url=None,  # 默认回调url
			app_private_key_path=settings.APP_PRIVATE_KEY_PATH,
			alipay_public_key_path=settings.ALIPAY_PUBLIC_KEY_PATH,  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
			sign_type="RSA2",  # RSA 或者 RSA2
			debug=True  # 默认False
		)

		# 调用支付接口
		# 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
		total_pay = order.total_price + order.transit_price  # Decimal
		order_string = alipay.api_alipay_trade_page_pay(
			out_trade_no=order_id,  # 订单id
			total_amount=str(total_pay),  # 支付总金额
			subject='生鲜商城%s' % order_id,
			return_url=None,
			notify_url=None  # 可选, 不填则使用默认notify url
		)

		# 返回应答
		pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
		return JsonResponse({'res': 3, 'pay_url': pay_url})


# ajax post
# 前端传递的参数:订单id(order_id)
# /order/check
class CheckPayView(View):
	'''查看订单支付的结果'''

	def post(self, request):
		'''查询支付结果'''
		# 用户是否登录
		user = request.user
		if not user.is_authenticated:
			return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

		# 接收参数
		order_id = request.POST.get('order_id')

		# 校验参数
		if not order_id:
			return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

		try:
			order = OrderInfo.objects.get(order_id=order_id,
			                              user=user,
			                              pay_method=3,
			                              order_status=1)
		except OrderInfo.DoesNotExist:
			return JsonResponse({'res': 2, 'errmsg': '订单错误'})

		# 业务处理:使用python sdk调用支付宝的支付接口
		# 初始化
		alipay = AliPay(
			appid=settings.ALIPAY_APP_ID,  # 应用id
			app_notify_url=None,  # 默认回调url
			app_private_key_path=settings.APP_PRIVATE_KEY_PATH,
			alipay_public_key_path=settings.ALIPAY_PUBLIC_KEY_PATH,
			# 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
			sign_type="RSA2",  # RSA 或者 RSA2
			debug=True  # 默认False
		)

		# 调用支付宝的交易查询接口
		while True:
			response = alipay.api_alipay_trade_query(order_id)
			"""
			response = {
			        "trade_no": "2017032121001004070200176844", # 支付宝交易号
			        "code": "10000", # 接口调用是否成功
			        "invoice_amount": "20.00",
			        "open_id": "20880072506750308812798160715407",
			        "fund_bill_list": [
			            {
			                "amount": "20.00",
			                "fund_channel": "ALIPAYACCOUNT"
			            }
			        ],
			        "buyer_logon_id": "csq***@sandbox.com",
			        "send_pay_date": "2017-03-21 13:29:17",
			        "receipt_amount": "20.00",
			        "out_trade_no": "out_trade_no15",
			        "buyer_pay_amount": "20.00",
			        "buyer_user_id": "2088102169481075",
			        "msg": "Success",
			        "point_amount": "0.00",
			        "trade_status": "TRADE_SUCCESS", # 支付结果
			        "total_amount": "20.00"
			}
			"""
			code = response.get('code')
			trade_status = response.get('trade_status')
			if code == '10000' and trade_status == 'TRADE_SUCCESS':
				# 支付成功
				# 获取支付宝交易号
				trade_no = response.get('trade_no')
				# 更新订单状态
				order.trade_no = trade_no
				order.order_status = 4  # 待评价
				order.save()
				# 返回结果
				return JsonResponse({'res': 3, 'message': '支付成功'})
			elif code == '40004' or (code == '10000' and trade_status == 'WAIT_BUYER_PAY'):
				# 等待买家付款
				# 业务处理失败，可能一会就会成功
				import time
				time.sleep(3)
				continue
			else:
				# 支付出错
				print(code)
				return JsonResponse({'res': 4, 'errmsg': '支付失败'})


# /order/comment
class OrderCommentView(View):
	'''
	商品评论
	'''

	def get(self, request, order_id):
		'''获取评论页面'''
		# 用户是否登录
		user = request.user
		if not user.is_authenticated:
			return redirect(reverse('user:order'))

		if not order_id:
			return redirect(reverse('user:order'))
		# 获取数据
		# 获取订单
		try:
			order = OrderInfo.objects.get(order_id=order_id, user=user)
		except OrderInfo.DoesNotExist:
			return redirect(reverse('user:order'))

		# 根据订单的状态获取订单的状态标题
		order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
		order_skus = OrderGoods.objects.filter(order_id=order_id)
		for order_sku in order_skus:
			price = order_sku.price
			count = order_sku.count
			amount = price * int(count)
			# 获取商品小计
			order_sku.amount = amount

		# 动态给order增加属性order_skus, 保存订单商品信息
		order.order_skus = order_skus
		print(order_skus)
		return render(request, 'order_comment.html', {'order': order})

	def post(self, request, order_id):
		'''提交评论'''
		# 用户是否登录
		user = request.user
		if not user.is_authenticated:
			return redirect(reverse('user:order'))

		# 校验数据
		if not order_id:
			return redirect(reverse('user:order'))
		try:
			order = OrderInfo.objects.get(order_id=order_id, user=user)
		except OrderInfo.DoesNotExist:
			return redirect(reverse("user:order"))
		# 获取评论条数
		total_count = request.POST.get('total_count')
		total_count = int(total_count)
		# 循环获取订单中商品的评论内容
		for i in range(0, total_count + 1):
			sku_id = request.POST.get('sku_%s' % i)
			# 若无评论则置空
			comment = request.POST.get('content_%s' % i, '')
			try:
				order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
			except OrderGoods.DoesNotExist:
				continue
			# 添加评论
			order_goods.comment = comment
			order_goods.save()

		# 更新订单状态
		order.order_status = 5  # 已完成
		order.save()

		return redirect(reverse("user:order", kwargs={"page": 1}))
