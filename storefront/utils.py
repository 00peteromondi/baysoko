import json
import decimal
from datetime import date, datetime

class ExtendedJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal and date/datetime objects."""
    
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

def dumps_with_decimals(obj):
    """Convert any Decimals to floats in a dictionary before converting to JSON."""
    return json.dumps(obj, cls=ExtendedJSONEncoder)