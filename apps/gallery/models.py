"""Gallery — ألبومات صور وفيديوهات مرتبطة بفعاليات المركز."""
from __future__ import annotations

import re

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class GalleryAlbum(TimeStampedModel):
    title_ar = models.CharField(_("اسم الألبوم (عربي)"), max_length=150)
    title_en = models.CharField(_("اسم الألبوم (إنجليزي)"), max_length=150, blank=True)
    slug = models.SlugField(_("الرابط"), max_length=200, unique=True, allow_unicode=True, blank=True)
    description = models.CharField(_("الوصف"), max_length=300, blank=True)
    cover = models.ImageField(_("الغلاف"), upload_to="gallery/covers/", blank=True, null=True)
    event = models.ForeignKey("events.Event", on_delete=models.SET_NULL, null=True, blank=True, related_name="albums", verbose_name=_("مرتبط بفعالية"))
    order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("ألبوم")
        verbose_name_plural = _("الألبومات")
        ordering = ["order", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = re.sub(r"[^\w\u0600-\u06FF-]+", "-", self.title_ar.strip()).strip("-") or "album"
            slug, i = base, 2
            while GalleryAlbum.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("gallery:detail", kwargs={"slug": self.slug})

    def __str__(self) -> str:
        return self.title_ar


class MediaItem(TimeStampedModel):
    album = models.ForeignKey(GalleryAlbum, on_delete=models.CASCADE, related_name="items", verbose_name=_("الألبوم"))
    image = models.ImageField(_("صورة"), upload_to="gallery/", blank=True, null=True)
    youtube_url = models.URLField(_("رابط يوتيوب"), blank=True)
    caption = models.CharField(_("التعليق"), max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("عنصر معرض")
        verbose_name_plural = _("عناصر المعرض")
        ordering = ["order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(image__isnull=False) | models.Q(youtube_url__gt=""),
                name="mediaitem_image_or_youtube_required",
            ),
        ]

    @property
    def is_video(self) -> bool:
        return bool(self.youtube_url)

    @property
    def youtube_embed_url(self) -> str:
        m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([\w-]{6,})", self.youtube_url or "")
        return f"https://www.youtube.com/embed/{m.group(1)}" if m else ""

    @property
    def youtube_thumb(self) -> str:
        m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([\w-]{6,})", self.youtube_url or "")
        return f"https://img.youtube.com/vi/{m.group(1)}/hqdefault.jpg" if m else ""

    def __str__(self) -> str:
        return self.caption or (self.youtube_url if self.is_video else str(self.image))
