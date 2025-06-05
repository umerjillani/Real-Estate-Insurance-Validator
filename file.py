from dateutil import parser
from datetime import date, datetime
import re

def normalize_date_str(date_str):
    digits_only = re.sub(r'\D', '', date_str)

    if len(digits_only) != 8:
        raise ValueError("Invalid date format. Expected MMDDYYYY after cleanup.")

    try:
        dt = datetime.strptime(digits_only, "%m%d%Y")
    except ValueError:
        raise ValueError("Date string could not be parsed as MMDDYYYY.")

    return dt

print(normalize_date_str("09/29/1972"))