from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import pandas as pd
from extensions import db

bp = Blueprint('rules', __name__)


def _build_category_tree(cat_df):
    """Build recursive hierarchical category tree for picker modal"""
    if cat_df.empty:
        return []

    def build(parent_id=None, path=""):
        if parent_id is None:
            children = cat_df[cat_df['parent_id'].isna()]
        else:
            children = cat_df[cat_df['parent_id'] == parent_id]
        result = []
        for _, row in children.iterrows():
            cat_id = int(row['id'])
            cat_name = str(row['name'])
            full_path = f"{path} → {cat_name}" if path else cat_name
            result.append({
                'id': cat_id,
                'name': cat_name,
                'fullPath': full_path,
                'children': build(cat_id, full_path)
            })
        return result

    return build()


@bp.route('/rules')
def index():
    try:
        rules_df = db.get_categorization_rules(active_only=False)
    except Exception as e:
        print(f"ERROR getting categorization rules: {e}")
        import traceback
        traceback.print_exc()
        rules_df = pd.DataFrame()
    
    # Get match counts for all rules
    try:
        match_counts = db.get_rule_match_counts()
    except Exception:
        match_counts = {}
    
    # Get categories for dropdown
    cat_df = db.get_categories()
    categories = []
    if not cat_df.empty:
        for _, row in cat_df.iterrows():
            display_name = str(row['name'])
            if pd.notna(row.get('parent_name')):
                display_name = f"{row['parent_name']} → {row['name']}"
            categories.append({'id': int(row['id']), 'name': display_name})
    
    categories.sort(key=lambda x: x['name'])
    
    # Build category tree for picker modal
    category_tree = _build_category_tree(cat_df)
    
    merchants = db.get_unique_merchants()
    counter_accounts = db.get_unique_counter_accounts()
    
    # Convert rules DataFrame to list of dicts for template
    rules = []
    if not rules_df.empty:        
        for _, row in rules_df.iterrows():
            rule = row.to_dict()
            try:
                rule['id'] = int(rule['id'])
                rule['category_id'] = int(rule['category_id'])
                rule['active'] = int(rule['active'])
                rule['priority'] = int(rule.get('priority', 0))
                # Clean NaN/Decimal values for template rendering
                rule['min_amount'] = float(rule['min_amount']) if pd.notna(rule.get('min_amount')) and float(rule['min_amount']) != 0 else None
                rule['max_amount'] = float(rule['max_amount']) if pd.notna(rule.get('max_amount')) and float(rule['max_amount']) != 0 else None
                rule['pattern'] = str(rule['pattern']) if pd.notna(rule.get('pattern')) else None
                rule['counter_account'] = str(rule['counter_account']) if pd.notna(rule.get('counter_account')) else None
                rule['transaction_type'] = str(rule['transaction_type']) if pd.notna(rule.get('transaction_type')) else ''
                # Match counts
                counts = match_counts.get(rule['id'], {})
                rule['match_total'] = counts.get('total', 0)
                rule['match_uncategorized'] = counts.get('uncategorized', 0)
                # Counter account display name
                if rule.get('counter_account'):
                    ca_match = next((ca for ca in counter_accounts if ca['iban'] == rule['counter_account']), None)
                    rule['counter_account_name'] = ca_match['name'] if ca_match else rule['counter_account']
                else:
                    rule['counter_account_name'] = None
                rules.append(rule)
            except ValueError as e:
                print(f"ERROR converting rule to int: {e}")
                continue
    
    # Prefill data from query params (for "create rule" from uncategorized page)
    prefill = {
        'pattern': request.args.get('pattern', ''),
        'counter_account': request.args.get('counter_account', ''),
        'transaction_type': request.args.get('transaction_type', ''),
    }
            
    return render_template('rules.html', rules=rules, categories=categories,
                           category_tree=category_tree,
                           merchants=merchants, counter_accounts=counter_accounts,
                           prefill=prefill)

@bp.route('/rules/add', methods=['GET'])
def add_get():
    """Handle GET requests to /rules/add - redirect to main rules page"""
    flash('Use the form on the rules page to add a new rule', 'info')
    return redirect(url_for('rules.index'))

@bp.route('/rules/add', methods=['POST'])
def add():
    pattern = request.form.get('pattern', '').strip()
    category_id = request.form.get('category_id')
    counter_account = request.form.get('counter_account', '').strip()
    transaction_type = request.form.get('transaction_type', '').strip()
    min_amount = request.form.get('min_amount', '').strip()
    max_amount = request.form.get('max_amount', '').strip()
    
    if not pattern and not counter_account:
        flash('At least a Merchant pattern or Counter Account is required', 'error')
        return redirect(url_for('rules.index'))
    if not category_id:
        flash('Category is required', 'error')
        return redirect(url_for('rules.index'))
    
    try:
        min_amt = float(min_amount) if min_amount else None
        max_amt = float(max_amount) if max_amount else None
        # Treat 0 as "no filter" for amount ranges
        if min_amt == 0: min_amt = None
        if max_amt == 0: max_amt = None
        trans_type = transaction_type if transaction_type else None
        ca = counter_account if counter_account else None
        pat = pattern if pattern else None
            
        db.add_categorization_rule(pat, category_id, 'description', min_amount=min_amt, 
                                   max_amount=max_amt, transaction_type=trans_type,
                                   counter_account=ca)
        flash('Rule added successfully', 'success')
        return redirect(url_for('rules.index'))
    except Exception as e:
        print(f"ERROR adding rule: {e}")
        flash(f'Error adding rule: {str(e)}', 'error')
        return redirect(url_for('rules.index'))

@bp.route('/rules/edit/<int:rule_id>', methods=['POST'])
def edit(rule_id):
    pattern = request.form.get('pattern', '').strip()
    category_id = request.form.get('category_id')
    counter_account = request.form.get('counter_account', '').strip()
    active = request.form.get('active')
    transaction_type = request.form.get('transaction_type', '').strip()
    min_amount = request.form.get('min_amount', '').strip()
    max_amount = request.form.get('max_amount', '').strip()
    
    active_val = True if active else False
    min_amt = float(min_amount) if min_amount else None
    max_amt = float(max_amount) if max_amount else None
    # Treat 0 as "no filter" for amount ranges
    if min_amt == 0: min_amt = None
    if max_amt == 0: max_amt = None
    trans_type = transaction_type if transaction_type else None
    ca = counter_account if counter_account else None
    pat = pattern if pattern else None
    
    db.update_categorization_rule(rule_id, pattern=pat, category_id=category_id, 
                                 active=active_val, 
                                 min_amount=min_amt, max_amount=max_amt, 
                                 transaction_type=trans_type,
                                 counter_account=ca)
    flash('Rule updated successfully', 'success')
    return redirect(url_for('rules.index'))

@bp.route('/rules/delete/<int:rule_id>', methods=['POST'])
def delete(rule_id):
    db.delete_categorization_rule(rule_id)
    flash('Rule deleted successfully', 'success')
    return redirect(url_for('rules.index'))

@bp.route('/rules/apply', methods=['POST'])
def apply_all():
    """Apply all rules to existing transactions"""
    count = db.auto_categorize_transactions()
    if count > 0:
        flash(f'Successfully applied rules to {count} transactions', 'success')
    else:
        flash('Rules applied, but no new transactions were categorized', 'info')
    return redirect(url_for('rules.index'))


# ============ API Endpoints ============

@bp.route('/api/rules/test', methods=['POST'])
def api_test_rule():
    """Preview how many transactions a rule would match."""
    data = request.get_json(force=True)
    pattern = data.get('pattern', '').strip() or None
    counter_account = data.get('counter_account', '').strip() or None
    transaction_type = data.get('transaction_type', '').strip() or None
    min_amount = data.get('min_amount')
    max_amount = data.get('max_amount')
    
    if min_amount is not None and min_amount != '':
        min_amount = float(min_amount)
    else:
        min_amount = None
    if max_amount is not None and max_amount != '':
        max_amount = float(max_amount)
    else:
        max_amount = None
    if min_amount == 0: min_amount = None
    if max_amount == 0: max_amount = None
    
    result = db.test_rule(
        pattern=pattern, counter_account=counter_account,
        transaction_type=transaction_type,
        min_amount=min_amount, max_amount=max_amount
    )
    return jsonify(result)


@bp.route('/api/rules/conflicts', methods=['POST'])
def api_check_conflicts():
    """Check for conflicting rules before creating/editing."""
    data = request.get_json(force=True)
    pattern = data.get('pattern', '').strip() or None
    counter_account = data.get('counter_account', '').strip() or None
    transaction_type = data.get('transaction_type', '').strip() or None
    min_amount = data.get('min_amount')
    max_amount = data.get('max_amount')
    exclude_rule_id = data.get('exclude_rule_id')
    
    if min_amount is not None and min_amount != '':
        min_amount = float(min_amount)
    else:
        min_amount = None
    if max_amount is not None and max_amount != '':
        max_amount = float(max_amount)
    else:
        max_amount = None
    
    conflicts = db.find_conflicting_rules(
        pattern=pattern, counter_account=counter_account,
        transaction_type=transaction_type,
        min_amount=min_amount, max_amount=max_amount,
        exclude_rule_id=exclude_rule_id
    )
    return jsonify({'conflicts': conflicts})


@bp.route('/api/rules/reorder', methods=['POST'])
def api_reorder_rules():
    """Reorder rule priorities via drag-and-drop."""
    data = request.get_json(force=True)
    rule_ids = data.get('rule_ids', [])
    
    if not rule_ids:
        return jsonify({'success': False, 'error': 'No rule IDs provided'}), 400
    
    try:
        db.reorder_rule_priorities([int(rid) for rid in rule_ids])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
