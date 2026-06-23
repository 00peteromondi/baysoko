# storefront/utils/__init__.py
import json
import decimal

def dumps_with_decimals(obj):
    """
    JSON encoder that handles Decimal objects.
    """
    def decimal_default(obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    return json.dumps(obj, default=decimal_default)

# Remove the circular import line
# from . import dumps_with_decimals  # DELETE THIS LINE