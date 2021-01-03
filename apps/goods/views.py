from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic.base import View
from django_redis import get_redis_connection

from goods.models import GoodsType, IndexGoodsBanner, \
	IndexTypeGoodsBanner, IndexPromotionBanner, GoodsSKU
from order.models import OrderGoods


# /index
class IndexView(View):
	def get(self, request):
		# 先获取缓存数据
		context = cache.get('index_page_data')
		if context is None:
			# 获取商品种类信息
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

			context = {
				'types': types,
				'goods_banners': goods_banners,
				'promotion_banners': promotion_banners
			}
			# 设置缓存数据 cache.set(key, value, timeout)
			cache.set('index_page_data', context, 3600)

		# 获取购物车记录
		cart_count = 0
		# 1.获取当前用户信息
		user = request.user
		# 2.判断是否登录
		if user.is_authenticated:
			conn = get_redis_connection('default')
			car_id = 'cart_%s' % user.id
			cart_count = conn.hlen(car_id)

		# 更新数据
		context.update(cart_count=cart_count)
		return render(request, 'index.html', context)


# goods/goods_id
class GoodsDetailView(View):
	def get(self, request, goods_id):
		# 获取商品信息
		try:
			sku = GoodsSKU.objects.get(id=goods_id)
		# 商品不存在
		except GoodsSKU.DoesNotExist:
			return redirect(reverse('goods:index'))
		# 获取商品分类
		types = GoodsType.objects.all()
		# 获取同一种的不同规格商品
		same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)
		# 获取商品的评论信息
		comment = OrderGoods.objects.filter(sku=sku).exclude(comment='')
		# 获取新品信息
		new_goods = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

		# 获取购物车记录
		cart_count = 0
		# 1.获取当前用户信息
		user = request.user
		# 2.判断是否登录
		if user.is_authenticated:
			conn = get_redis_connection('default')
			car_id = 'cart_%s' % user.id
			cart_count = conn.hlen(car_id)

			# 添加历史浏览记录
			history_key = 'history_%d' % user.id
			# 删除已存在的浏览记录
			conn.lrem(history_key, 0, goods_id)
			conn.lpush(history_key, goods_id)
			# 保存前五条浏览记录
			conn.ltrim(history_key, 0, 4)

		context = {
			'sku': sku,
			'types': types,
			'same_spu_skus': same_spu_skus,
			'sku_orders': comment,
			'new_skus': new_goods,
			'cart_count': cart_count
		}
		return render(request, 'detail.html', context)


# 种类id 页码 排序方式
# restful api -> 请求一种资源
# /list?type_id=种类id&page=页码&sort=排序方式
# /list/种类id/页码/排序方式
# /list/种类id/页码?sort=排序方式
# /goods/list
class GoodsListView(View):
	def get(self, request, type_id, page):
		# 获取商品分类
		types = GoodsType.objects.all()
		# 获取同类商品
		# 1)如果获取的type_id不存在
		try:
			goods_type = GoodsType.objects.get(id=type_id)
		except GoodsType.DoesNotExist:
			return redirect(reverse('goods:index'))
		# 获取新品信息
		new_goods = GoodsSKU.objects.filter(type=goods_type).order_by('-create_time')[:2]
		# 根据不同方式来获取商品的排列
		sort = request.GET.get('sort')
		if sort == 'price':
			skus = GoodsSKU.objects.filter(type=goods_type).order_by('price')
		elif sort == 'hot':
			skus = GoodsSKU.objects.filter(type=goods_type).order_by('-sales')
		else:
			sort = 'default'
			skus = GoodsSKU.objects.filter(type=goods_type).order_by('-id')
		# 获取分页信息
		# 1) 生成paginator对象
		# 属性：num_pages(总页数) page_range(页数列表 [1, 2, 3, 4])
		paginator = Paginator(skus, 3)
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
		skus_page = paginator.page(page)

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

		# 获取购物车信息
		cart_count = 0
		# 1.获取当前用户信息
		user = request.user
		# 2.判断是否登录
		if user.is_authenticated:
			conn = get_redis_connection('default')
			car_id = 'cart_%s' % user.id
			cart_count = conn.hlen(car_id)

		context = {
			'type': goods_type,
			'new_skus': new_goods,
			'skus_page': skus_page,
			'sort': sort,
			'pages': pages,
			'types': types,
			'cart_count': cart_count
		}
		return render(request, 'list.html', context)
