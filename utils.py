from datetime import datetime, timedelta
from flask import session

def get_period_filters(period):
    """Convert period string to date filters"""
    today = datetime.now()
    filters = {}
    
    if period == "this_month":
        filters['start_date'] = today.replace(day=1).strftime('%Y-%m-%d')
        filters['end_date'] = today.strftime('%Y-%m-%d')
    elif period == "last_month":
        first_of_month = today.replace(day=1)
        last_month = first_of_month - timedelta(days=1)
        filters['start_date'] = last_month.replace(day=1).strftime('%Y-%m-%d')
        filters['end_date'] = last_month.strftime('%Y-%m-%d')
    elif period == "last_3_months":
        filters['start_date'] = (today - timedelta(days=90)).strftime('%Y-%m-%d')
        filters['end_date'] = today.strftime('%Y-%m-%d')
    elif period == "this_year":
        filters['start_date'] = today.replace(month=1, day=1).strftime('%Y-%m-%d')
        filters['end_date'] = today.strftime('%Y-%m-%d')
    
    return filters


def get_active_account_filter():
    """Get filter dict for active account"""
    active = session.get('active_account')
    if active:
        return {'account': active}
    return {}
