from django import template

register = template.Library()


@register.filter(name='abs')
def abs_value(value):
    """Return the absolute value for numbers in templates."""
    try:
        return abs(value)
    except Exception:
        try:
            return abs(float(value))
        except Exception:
            return value
