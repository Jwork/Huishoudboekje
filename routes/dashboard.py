"""Dashboard routes - overview and category analysis pages with JSON APIs"""
from datetime import date, timedelta
from flask import Blueprint, render_template, request, jsonify, session
from extensions import db

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


def _resolve_date_range():
    """Resolve date range from query params: preset, month/year picker, or explicit dates."""
    preset = request.args.get('preset', 'last6m')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    sel_month = request.args.get('month', type=int)
    sel_year = request.args.get('year', type=int)

    today = date.today()

    # Explicit dates take precedence
    if start_date and end_date:
        return start_date, end_date, 'custom'

    # Month picker
    if sel_month and sel_year:
        from calendar import monthrange
        _, last_day = monthrange(sel_year, sel_month)
        return (
            date(sel_year, sel_month, 1).isoformat(),
            date(sel_year, sel_month, last_day).isoformat(),
            'month'
        )

    # Presets
    presets = {
        'thismonth': (today.replace(day=1), today),
        'last3m': (today - timedelta(days=90), today),
        'last6m': (today - timedelta(days=182), today),
        'last12m': (today - timedelta(days=365), today),
        'ytd': (date(today.year, 1, 1), today),
        'all': (None, None),
    }

    if preset in presets:
        s, e = presets[preset]
        return (
            s.isoformat() if s else None,
            e.isoformat() if e else None,
            preset
        )

    # Default: last 6 months
    s, e = presets['last6m']
    return s.isoformat(), e.isoformat(), 'last6m'


def _get_account_filter():
    """Get account filter from session."""
    return session.get('active_account')


# ========== Page Routes ==========

@bp.route('/')
def overview():
    """Dashboard overview page"""
    return render_template('dashboard_overview.html')


@bp.route('/categories')
def categories():
    """Category analysis page"""
    return render_template('dashboard_categories.html')


@bp.route('/budget')
def budget():
    """Budget overview page - spreadsheet-style income/expense breakdown"""
    return render_template('dashboard_budget.html')


# ========== JSON API Routes ==========

@bp.route('/api/overview')
def api_overview():
    """JSON endpoint: KPI stats + monthly trend + savings flow"""
    start_date, end_date, preset = _resolve_date_range()
    account = _get_account_filter()

    filters = {}
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
    if account:
        filters['account'] = account

    stats = db.get_dashboard_stats(filters)
    trend = db.get_monthly_trend(start_date, end_date, account)
    savings = db.get_savings_flow(start_date, end_date, account)
    savings_total = db.get_savings_flow_total(start_date, end_date, account)

    return jsonify({
        'stats': stats,
        'trend': trend,
        'savings': savings,
        'savings_total': savings_total,
        'preset': preset,
        'start_date': start_date,
        'end_date': end_date,
    })


@bp.route('/api/category-breakdown')
def api_category_breakdown():
    """JSON endpoint: spending/income by parent category"""
    start_date, end_date, preset = _resolve_date_range()
    account = _get_account_filter()
    direction = request.args.get('direction', 'debit')

    breakdown = db.get_category_breakdown(start_date, end_date, direction, account)

    return jsonify({
        'breakdown': breakdown,
        'direction': direction,
        'preset': preset,
    })


@bp.route('/api/subcategory-breakdown/<int:parent_id>')
def api_subcategory_breakdown(parent_id):
    """JSON endpoint: subcategory drilldown within a parent"""
    start_date, end_date, preset = _resolve_date_range()
    account = _get_account_filter()
    direction = request.args.get('direction', 'debit')

    breakdown = db.get_subcategory_breakdown(parent_id, start_date, end_date, direction, account)

    return jsonify({
        'breakdown': breakdown,
        'parent_id': parent_id,
        'direction': direction,
    })


@bp.route('/api/category-trend/<int:category_id>')
def api_category_trend(category_id):
    """JSON endpoint: monthly trend for a specific category"""
    start_date, end_date, preset = _resolve_date_range()
    account = _get_account_filter()

    trend = db.get_category_trend(category_id, start_date, end_date, account)

    return jsonify({
        'trend': trend,
        'category_id': category_id,
    })


@bp.route('/api/budget-overview')
def api_budget_overview():
    """JSON endpoint: structured budget overview with category tree"""
    start_date, end_date, preset = _resolve_date_range()
    account = _get_account_filter()

    overview = db.get_budget_overview(start_date, end_date, account)
    savings = db.get_savings_flow_total(start_date, end_date, account)
    savings_accounts = db.get_savings_per_account(start_date, end_date, account)

    month_count = overview.get('month_count', 1)
    overview['savings'] = {
        'savings_in': savings['savings_in'],
        'savings_out': savings['savings_out'],
        'net_savings': savings['net_savings'],
        'savings_in_monthly': savings['savings_in'] / month_count,
        'savings_out_monthly': savings['savings_out'] / month_count,
        'net_savings_monthly': savings['net_savings'] / month_count,
        'accounts': [{
            'name': a['name'],
            'savings_in': a['savings_in'],
            'savings_out': a['savings_out'],
            'net': a['net'],
            'savings_in_monthly': a['savings_in'] / month_count,
            'savings_out_monthly': a['savings_out'] / month_count,
            'net_monthly': a['net'] / month_count,
        } for a in savings_accounts],
    }

    return jsonify({
        'overview': overview,
        'preset': preset,
        'start_date': start_date,
        'end_date': end_date,
    })
