# -*- coding: utf-8 -*-
"""فلاتر القوالب — منظّمة SEO."""
import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(name="ld_json")
def ld_json(data):
    """يرسم بيانات JSON-LD (schema.org) بالنوع الصحيح application/ld+json."""
    if not data:
        return ""
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    # أمان: نمنع أي وسم </script> من قفل السكربت
    raw = raw.replace("</", "<\\/")
    return mark_safe(f'<script type="application/ld+json">{raw}</script>')
