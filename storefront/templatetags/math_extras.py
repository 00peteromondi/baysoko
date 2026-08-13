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
        
@register.filter(name='div')
def div(value, arg):
    """Divide value by arg."""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return value
    
@register.filter(name='mul')
def mul(value, arg):
    """Multiply value by arg."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value