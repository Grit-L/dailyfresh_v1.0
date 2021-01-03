from django.contrib import admin
from django.core.cache import cache
from goods.models import GoodsType, IndexGoodsBanner, \
    IndexTypeGoodsBanner, IndexPromotionBanner, GoodsSKU, \
	Goods, GoodsImage
# Register your models here.


# 创建基础模型
class BaseAdminManager(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from celery_tasks.tasks import generic_static_index_html
        generic_static_index_html.delay()
        # 删除页面数据缓存
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        from celery_tasks.tasks import generic_static_index_html
        generic_static_index_html.delay()
        # 删除页面数据缓存
        cache.delete('index_page_data')


@admin.register(GoodsType)
class GoodsTypeAdmin(BaseAdminManager):
    pass


@admin.register(IndexGoodsBanner)
class IndexGoodsBannerAdmin(BaseAdminManager):
    pass


@admin.register(IndexTypeGoodsBanner)
class IndexTypeGoodsBannerAdmin(BaseAdminManager):
    pass


@admin.register(IndexPromotionBanner)
class IndexPromotionBannerAdmin(BaseAdminManager):
    pass


admin.site.register(GoodsSKU)
admin.site.register(Goods)
admin.site.register(GoodsImage)

