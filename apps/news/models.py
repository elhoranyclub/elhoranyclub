"""News — مقالات، تصنيفات، وسوم، صور معرض (بدون Article content حر)."""
from __future__ import annotations

import re

import nh3
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

ALLOWED_TAGS = {
    "p", "br", "hr", "strong", "b", "em", "i", "u",
    "h2", "h3", "h4", "ul", "ol", "li", "a", "blockquote", "code", "pre",
}
ALLOWED_ATTRS = {"a": {"href", "title", "target"}}


def sanitize_html(html: str) -> str:
    """تنظيف HTML المُدخَل — السماح بوسوم آمنة فقط."""
    return nh3.clean(html or "", tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, url_schemes={"https", "http", "mailto", "tel"})


class Tag(TimeStampedModel):
    name = models.CharField(_("الوسم"), max_length=80, unique=True)
    slug = models.SlugField(_("الرابط"), max_length=100, unique=True, allow_unicode=True)

    class Meta:
        verbose_name = _("وسم")
        verbose_name_plural = _("الوسوم")

    def __str__(self) -> str:
        return self.name


class NewsCategory(TimeStampedModel):
    name_ar = models.CharField(_("التصنيف (عربي)"), max_length=80)
    name_en = models.CharField(_("التصنيف (إنجليزي)"), max_length=80, blank=True)
    slug = models.SlugField(_("الرابط"), max_length=100, unique=True, allow_unicode=True)

    class Meta:
        verbose_name = _("تصنيف الأخبار")
        verbose_name_plural = _("تصنيفات الأخبار")
        ordering = ["name_ar"]

    def __str__(self) -> str:
        return self.name_ar


class NewsArticle(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("مسودة")
        PUBLISHED = "published", _("منشور")
        SCHEDULED = "scheduled", _("مجدول")

    title = models.CharField(_("العنوان"), max_length=200)
    title_en = models.CharField(_("العنوان (إنجليزي)"), max_length=200, blank=True)
    slug = models.SlugField(_("الرابط"), max_length=220, unique=True, allow_unicode=True, blank=True)
    summary = models.CharField(_("الملخص"), max_length=320, blank=True)
    content = models.TextField(_("المحتوى"), blank=True)

    cover = models.ImageField(_("صورة الغلاف"), upload_to="news/", blank=True, null=True)
    category = models.ForeignKey(NewsCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="articles", verbose_name=_("التصنيف"))
    tags = models.ManyToManyField(Tag, blank=True, related_name="articles", verbose_name=_("الوسوم"))
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="news_articles", verbose_name=_("الكاتب"))

    status = models.CharField(_("الحالة"), max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(_("تاريخ النشر"), null=True, blank=True, db_index=True)
    is_featured = models.BooleanField(_("خبر مميز (تظهر في الرئيسية)"), default=False)

    class Meta:
        verbose_name = _("خبر")
        verbose_name_plural = _("الأخبار")
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["status", "published_at"])]

    def save(self, *args, **kwargs):
        self.content = sanitize_html(self.content)
        if not self.slug:
            base = re.sub(r"[^\w\u0600-\u06FF-]+", "-", self.title.strip()).strip("-") or "article"
            slug, i = base, 2
            while NewsArticle.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("news:detail", kwargs={"slug": self.slug})

    @property
    def is_live(self) -> bool:
        if self.status == self.Status.PUBLISHED:
            return True
        if self.status == self.Status.SCHEDULED and self.published_at:
            return self.published_at <= timezone.now()
        return False

    def __str__(self) -> str:
        return self.title


class NewsImage(TimeStampedModel):
    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name="images", verbose_name=_("الخبر"))
    image = models.ImageField(_("الصورة"), upload_to="news/gallery/")
    caption = models.CharField(_("التعليق"), max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("صورة خبر")
        verbose_name_plural = _("صور الأخبار")
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.caption or str(self.image)
