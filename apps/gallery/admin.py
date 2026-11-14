from django.contrib import admin

from .models import GalleryAlbum, MediaItem


class MediaItemInline(admin.TabularInline):
    model = MediaItem
    extra = 1
    fields = ("image", "youtube_url", "caption", "order")


@admin.register(GalleryAlbum)
class GalleryAlbumAdmin(admin.ModelAdmin):
    list_display = ("title_ar", "event", "order", "created_at")
    search_fields = ("title_ar", "title_en")
    prepopulated_fields = {"slug": ("title_en",)}
    inlines = [MediaItemInline]


@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ("album", "caption", "is_video", "order")
    list_filter = ("album",)
