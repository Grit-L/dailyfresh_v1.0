from datetime import datetime

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
