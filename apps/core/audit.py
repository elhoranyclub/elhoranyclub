"""تدقيق — من فعل ماذا ومتى (عمليات مالية وحساسة)."""
from __future__ import annotations

import logging

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

logger = logging.getLogger(__name__)


class AuditLog(TimeStampedModel):
    """سجل تدقيق عام — الكتابة آمنة: أي خطأ فيها لا يوقف العملية الأصلية."""

    actor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events", verbose_name=_("من"))
    action = models.CharField(_("الإجراء"), max_length=80, db_index=True)
    target = models.CharField(_("الهدف"), max_length=255, blank=True)
    detail = models.TextField(_("التفاصيل"), blank=True)

    class Meta:
        verbose_name = _("سجل تدقيق")
        verbose_name_plural = _("سجلات التدقيق")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} — {self.actor}"


def record(actor, action: str, target: str = "", detail: str = "") -> None:
    """يسجل حدثًا دون رمي أي استثناء."""
    try:
        AuditLog.objects.create(actor=actor, action=action, target=target[:255], detail=detail)
    except Exception as exc:
        logger.warning("audit record failed (%s): %s", action, exc)
