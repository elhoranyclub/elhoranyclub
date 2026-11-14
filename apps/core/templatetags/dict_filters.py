from django import template

register = template.Library()


@register.filter
def dict_get(value, key):
    """dict[key] آمن — للقواميس المبنية في الـ view."""
    try:
        return value.get(key)
    except AttributeError:
        return None
