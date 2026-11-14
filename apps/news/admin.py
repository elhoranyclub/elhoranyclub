from django.contrib import admin

from .models import NewsArticle, NewsCategory, NewsImage, Tag


class NewsImageInline(admin.TabularInline):
    model = NewsImage
    extra = 1
    fields = ("image", "caption", "order")


@admin.register(NewsCategory)
class NewsCategoryAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "slug")
    prepopulated_fields = {"slug": ("name_en",)}
    search_fields = ("name_ar", "name_en")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "is_featured", "published_at", "author")
    list_filter = ("status", "category", "is_featured")
    search_fields = ("title", "title_en", "summary")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("tags",)
    inlines = [NewsImageInline]
    actions = ["publish_selected"]

    @admin.action(description="نشر المحدد")
    def publish_selected(self, request, queryset):
        from django.utils import timezone

        queryset.update(status=NewsArticle.Status.PUBLISHED, published_at=timezone.now())


@admin.register(NewsImage)
class NewsImageAdmin(admin.ModelAdmin):
    list_display = ("article", "caption", "order")
