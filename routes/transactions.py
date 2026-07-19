from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
import pandas as pd
import os
import shutil
from datetime import datetime
from extensions import db
from utils import get_active_account_filter

bp = Blueprint('transactions', __name__)


def build_category_list():
    """Build category list with parent names for display"""
    categories = db.get_categories()
    cat_list = []
    for _, row in categories.iterrows():
        display_name = str(row['name'])
        parent = row.get('parent_name')
        # Check for both standard NA/None and the string 'nan'
        if pd.notna(parent) and str(parent).lower() != 'nan':
            display_name = f"{parent} → {display_name}"
        cat_list.append({'id': int(row['id']), 'name': display_name})
    return cat_list


def build_category_tree():
    """Build recursive hierarchical category tree for picker (unlimited depth)"""
    cat_df = db.get_categories()
    
    def build_tree(parent_id=None, path=""):
        if parent_id is None:
            children = cat_df[cat_df['parent_id'].isna()]
        else:
            children = cat_df[cat_df['parent_id'] == parent_id]
        
        result = []
        for _, row in children.iterrows():
            cat_id = int(row['id'])
            cat_name = str(row['name'])
            full_path = f"{path} → {cat_name}" if path else cat_name
            
            node = {
                'id': cat_id,
                'name': cat_name,
                'fullPath': full_path,
                'children': build_tree(cat_id, full_path)
            }
            result.append(node)
        
        return result
    
    return build_tree()


ALLOWED_PARAMS = {'search', 'page', 'merchant', 'sort', 'dir', 'start_date', 'end_date',
                   'category_id', 'type', 'min_amount', 'max_amount', 'is_transfer', 'is_incidental'}


def _parse_common_filters(request_args, base_filters=None):
    """Parse filter and sort params from request args. Returns (filters, sort_by, sort_dir, page, filter_values)."""
    filters = base_filters or {}
    filter_values = {}  # For pre-filling form inputs in templates

    # Text search
    search_query = request_args.get('search', '')
    if search_query:
        filters['search'] = search_query
    filter_values['search'] = search_query

    # Merchant exact match
    merchant = request_args.get('merchant', '')
    if merchant:
        filters['merchant'] = merchant
    filter_values['merchant'] = merchant

    # Date range
    start_date = request_args.get('start_date', '')
    if start_date:
        filters['start_date'] = start_date
    filter_values['start_date'] = start_date

    end_date = request_args.get('end_date', '')
    if end_date:
        filters['end_date'] = end_date
    filter_values['end_date'] = end_date

    # Category
    category_id = request_args.get('category_id', '')
    if category_id:
        filters['category_id'] = category_id
    filter_values['category_id'] = category_id

    # Type (Af/Bij)
    type_filter = request_args.get('type', '')
    if type_filter:
        filters['type'] = type_filter
    filter_values['type'] = type_filter

    # Amount range
    min_amount = request_args.get('min_amount', '')
    if min_amount:
        filters['min_amount'] = min_amount
    filter_values['min_amount'] = min_amount

    max_amount = request_args.get('max_amount', '')
    if max_amount:
        filters['max_amount'] = max_amount
    filter_values['max_amount'] = max_amount

    # Flags
    is_transfer = request_args.get('is_transfer', '')
    if is_transfer != '':
        filters['is_transfer'] = is_transfer
    filter_values['is_transfer'] = is_transfer

    is_incidental = request_args.get('is_incidental', '')
    if is_incidental != '':
        filters['is_incidental'] = is_incidental
    filter_values['is_incidental'] = is_incidental

    # Sorting
    sort_by = request_args.get('sort', 'date')
    sort_dir = request_args.get('dir', 'desc')
    filter_values['sort'] = sort_by
    filter_values['dir'] = sort_dir

    # Pagination
    page = request_args.get('page', 1, type=int)

    return filters, sort_by, sort_dir, page, filter_values


@bp.route('/transactions')
def transactions():
    # Clean up URL parameters (fix for browser extension loop)
    if any(k not in ALLOWED_PARAMS for k in request.args):
        clean_args = {k: v for k, v in request.args.items() if k in ALLOWED_PARAMS}
        return redirect(url_for('transactions.transactions', **clean_args))

    base_filters = get_active_account_filter()
    filters, sort_by, sort_dir, page, filter_values = _parse_common_filters(request.args, base_filters)
    per_page = 100
    
    # Get transactions with server-side sort and pagination
    df = db.get_transactions(filters, page=page, per_page=per_page, sort_by=sort_by, sort_dir=sort_dir)
    
    # Get total count for pagination
    total_items = db.get_transaction_count(filters)
    total_pages = (total_items + per_page - 1) // per_page
    
    trans_list = []
    if len(df) > 0:
        for _, row in df.iterrows():
            display_type = str(row['direction']) if pd.notna(row.get('direction')) else ''
            
            trans_list.append({
                'id': int(row['id']),
                'date': str(row['date'])[:10] if pd.notna(row['date']) else '',
                'merchant': str(row['description'])[:40] if pd.notna(row['description']) else '',
                'description': str(row['notes'])[:60] if pd.notna(row['notes']) else '',
                'notes': str(row['notes']) if pd.notna(row['notes']) else '',
                'category': str(row['category_name']) if pd.notna(row['category_name']) else 'Uncategorized',
                'category_id': int(row['category_id']) if pd.notna(row['category_id']) else None,
                'direction': display_type,
                'is_transfer': bool(row['is_transfer']) if pd.notna(row.get('is_transfer')) else False,
                'is_incidental': bool(row['is_incidental']) if pd.notna(row.get('is_incidental')) else False,
                'amount': float(row['amount']) if pd.notna(row['amount']) else 0.0,
                'account': str(row['account']) if pd.notna(row['account']) else '',
                'counter_account': str(row['counter_account']) if pd.notna(row['counter_account']) else ''
            })
    
    # Get categories for dropdown (with parent names for context)
    cat_list = build_category_list()
    
    # Get category tree for picker modal
    cat_tree = build_category_tree()
    
    # Get unique merchants/descriptions for bulk categorization (filtered by active account)
    merchants = db.get_unique_merchants(filters)

    # Check if any filters are active (for UI display)
    has_active_filters = any(filter_values.get(k) for k in 
        ['search', 'merchant', 'start_date', 'end_date', 'category_id', 'type', 'min_amount', 'max_amount', 'is_transfer', 'is_incidental'])
    
    return render_template('transactions.html', 
                          transactions=trans_list, 
                          categories=cat_list,
                          category_tree=cat_tree,
                          merchants=merchants,
                          page=page,
                          total_pages=total_pages,
                          total_items=total_items,
                          filters=filter_values,
                          has_active_filters=has_active_filters,
                          selected_merchant=filter_values.get('merchant', ''))


@bp.route('/uncategorized')
def uncategorized():
    """Show only uncategorized transactions for quick categorization"""
    # Clean up URL parameters
    if any(k not in ALLOWED_PARAMS for k in request.args):
        clean_args = {k: v for k, v in request.args.items() if k in ALLOWED_PARAMS}
        return redirect(url_for('transactions.uncategorized', **clean_args))

    base_filters = get_active_account_filter()
    base_filters['uncategorized'] = True
    filters, sort_by, sort_dir, page, filter_values = _parse_common_filters(request.args, base_filters)
    per_page = 100
    
    # Get transactions for current page
    df = db.get_transactions(filters, page=page, per_page=per_page, sort_by=sort_by, sort_dir=sort_dir)
    
    # Get total count for pagination
    total_items = db.get_transaction_count(filters)
    total_pages = (total_items + per_page - 1) // per_page
    
    trans_list = []
    if len(df) > 0:
        for _, row in df.iterrows():
            trans_list.append({
                'id': int(row['id']),
                'date': str(row['date'])[:10] if pd.notna(row['date']) else '',
                'merchant': str(row['description']) if pd.notna(row['description']) else '',
                'description': str(row['notes']) if pd.notna(row['notes']) else '',
                'direction': str(row['direction']) if pd.notna(row.get('direction')) else '',
                'amount': float(row['amount']) if pd.notna(row['amount']) else 0.0,
                'account': str(row['account']) if pd.notna(row['account']) else ''
            })
    
    # Get flat category list for simple dropdowns
    cat_list = build_category_list()
    
    # Get hierarchical category tree for advanced picker
    cat_tree = build_category_tree()
    
    # Get unique uncategorized merchants for bulk categorization (filtered by active account)
    merchants = db.get_unique_merchants(filters)
    merchants = [m for m in merchants if m['uncategorized'] > 0]

    has_active_filters = any(filter_values.get(k) for k in 
        ['search', 'merchant', 'start_date', 'end_date', 'type', 'min_amount', 'max_amount'])
    
    return render_template('uncategorized.html', 
                          transactions=trans_list, 
                          categories=cat_list, 
                          category_tree=cat_tree,
                          merchants=merchants,
                          page=page,
                          total_pages=total_pages,
                          total_items=total_items,
                          filters=filter_values,
                          has_active_filters=has_active_filters)

@bp.route('/transactions/<int:trans_id>/categorize', methods=['POST'])
def categorize_transaction(trans_id):
    category_id = request.form.get('category_id')
    create_rule = request.form.get('create_rule') == 'on'
    redirect_to = request.form.get('redirect_to', 'transactions.transactions')
    merchant_filter = request.form.get('merchant_filter', '')
    
    if category_id:
        db.update_transaction_category(trans_id, int(category_id))
        
        # Optionally create a rule for future auto-categorization
        if create_rule:
            # Get the transaction description to create a rule
            transaction = db.get_transaction(trans_id)
            
            if transaction and transaction.get('description'):
                # Create rule from first few words of description
                pattern = transaction['description'].split()[0].lower() if transaction['description'] else ''
                if pattern and len(pattern) > 2:
                    db.add_categorization_rule(pattern, int(category_id))
                    flash(f'Gecategoriseerd en regel aangemaakt voor "{pattern}"', 'success')
                else:
                    flash('Succesvol gecategoriseerd', 'success')
            else:
                flash('Succesvol gecategoriseerd', 'success')
        else:
            flash('Succesvol gecategoriseerd', 'success')
    
    # Preserve merchant filter in redirect
    if merchant_filter:
        return redirect(url_for(redirect_to, merchant=merchant_filter))
    return redirect(url_for(redirect_to))


@bp.route('/transactions/<int:trans_id>/notes', methods=['POST'])
def update_notes(trans_id):
    """Update transaction notes via AJAX"""
    notes = request.form.get('notes', '')
    db.update_transaction_notes(trans_id, notes)
    return jsonify({'success': True, 'notes': notes})


@bp.route('/transactions/<int:trans_id>/type', methods=['POST'])
def update_type(trans_id):
    """Update transaction direction via AJAX (debit/credit)"""
    data = request.get_json()
    new_type = data.get('type', 'debit')
    
    # Validate direction
    if new_type not in ['debit', 'credit']:
        return jsonify({'success': False, 'error': 'Ongeldige richting'})
    
    db.update_transaction_type(trans_id, new_type)
    return jsonify({'success': True, 'type': new_type})


@bp.route('/transactions/<int:trans_id>/toggle-transfer', methods=['POST'])
def toggle_transfer(trans_id):
    """Toggle transfer status via AJAX"""
    data = request.get_json(silent=True)
    if data and 'is_transfer' in data:
        new_is_transfer = bool(data['is_transfer'])
    else:
        # Fallback: server-side toggle
        trans = db.get_transaction_by_id(trans_id)
        if not trans:
            return jsonify({'success': False, 'error': 'Mutatie niet gevonden'})
        new_is_transfer = not bool(trans['is_transfer'])

    db.update_transaction_transfer_status(trans_id, new_is_transfer)
    return jsonify({'success': True, 'is_transfer': new_is_transfer})


@bp.route('/bulk-categorize', methods=['POST'])
def bulk_categorize():
    merchant = request.form.get('merchant')
    category_id = request.form.get('category_id')
    create_rule = request.form.get('create_rule') == 'on'
    redirect_to = request.form.get('redirect_to', 'transactions.transactions')
    
    if merchant and category_id:
        count = db.bulk_categorize_by_merchant(merchant, int(category_id))
        
        if create_rule:
            # Create rule for future transactions
            pattern = merchant.split()[0].lower()
            if pattern and len(pattern) > 2:
                db.add_categorization_rule(pattern, int(category_id))
                flash(f'{count} mutaties gecategoriseerd en regel aangemaakt voor "{pattern}"', 'success')
            else:
                flash(f'{count} mutaties gecategoriseerd', 'success')
        else:
            flash(f'{count} mutaties gecategoriseerd', 'success')
    
    return redirect(url_for(redirect_to))


@bp.route('/bulk-categorize-selected', methods=['POST'])
def bulk_categorize_selected():
    """Bulk categorize selected transactions by IDs (AJAX)"""
    data = request.get_json()
    transaction_ids = data.get('transaction_ids', [])
    category_id = data.get('category_id')
    create_rules = data.get('create_rule', False)  # JS sends create_rule
    
    if not transaction_ids or not category_id:
        return jsonify({'success': False, 'error': 'Ontbrekende mutatie ID\'s of categorie'})
    
    try:
        merchants_for_rules = set()
        
        # Collect merchants for rule creation before updating
        if create_rules:
            for trans_id in transaction_ids:
                transaction = db.get_transaction(trans_id)
                if transaction and transaction.get('description'):
                    first_word = transaction['description'].split()[0].lower() if transaction['description'] else ''
                    if first_word and len(first_word) > 2:
                        merchants_for_rules.add((first_word, int(category_id)))
        
        # Bulk update categories using repository method
        count = db.bulk_update_category(transaction_ids, int(category_id))
        
        # Create rules for unique merchants
        if create_rules:
            for pattern, cat_id in merchants_for_rules:
                db.add_categorization_rule(pattern, cat_id)
        
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/transactions/<int:transaction_id>/toggle_incidental', methods=['POST'])
def toggle_incidental(transaction_id):
    try:
        data = request.get_json()
        is_incidental = data.get('is_incidental', 0)
        db.update_transaction_incidental_status(transaction_id, is_incidental)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@bp.route('/import', methods=['GET', 'POST'])
def import_csv():
    from importers import get_all_importers
    current_app.logger.info("Import process started")
    
    if request.method == 'GET':
        import_batches = db.get_import_batches()
        return render_template('import.html', importers=get_all_importers(), import_batches=import_batches)
        
    if 'csv_file' not in request.files:
        current_app.logger.warning("Import failed: No file part in request")
        flash('Geen bestand geselecteerd', 'error')
        return redirect(url_for('transactions.import_csv'))
    
    file = request.files['csv_file']
    
    if file.filename == '':
        current_app.logger.warning("Import failed: No selected file")
        flash('Geen bestand geselecteerd', 'error')
        return redirect(url_for('transactions.import_csv'))
    
    if file and file.filename.endswith('.csv'):
        # Save uploaded file temporarily
        temp_path = os.path.join('uploads', file.filename)
        os.makedirs('uploads', exist_ok=True)
        file.save(temp_path)
        current_app.logger.debug(f"File saved to temporary path: {temp_path}")
        
        # Get format selection (empty string or 'auto' means auto-detect)
        format_id = request.form.get('format_id', '')
        if format_id in ('', 'auto'):
            format_id = None
        
        try:
            # Retain the uploaded file with timestamp prefix
            retained_dir = os.path.join('uploads', 'retained')
            os.makedirs(retained_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            retained_name = f"{timestamp}_{file.filename}"
            retained_path = os.path.join(retained_dir, retained_name)
            shutil.copy2(temp_path, retained_path)
            current_app.logger.info(f"Retained file: {retained_path}")

            imported, duplicates, errors = db.import_csv(
                temp_path, filename=file.filename, format_id=format_id,
                retained_file=retained_path
            )
            current_app.logger.info(f"Import results - Imported: {imported}, Duplicates: {duplicates}, Errors: {errors}")
            
            # Auto-mark transfers after import; guard against None for safety
            transfer_count = db.auto_mark_transfer_transactions() or 0
            if transfer_count > 0:
                current_app.logger.info(f"Auto-marked {transfer_count} transactions as transfers")
            
            # Auto-link transfer pairs
            link_count = db.auto_link_transfer_pairs() or 0
            if link_count > 0:
                current_app.logger.info(f"Auto-linked {link_count} transfer pairs")
            
            msg = f'Geïmporteerd: {imported}, Duplicaten: {duplicates}, Fouten: {errors}'
            if transfer_count > 0:
                msg += f', Overboekingen gemarkeerd: {transfer_count}'
            if link_count > 0:
                msg += f', Overboeking paren gekoppeld: {link_count}'
            flash(msg, 'success')
            return redirect(url_for('transactions.transactions'))
        except Exception as e:
            current_app.logger.error(f"Import error: {str(e)}", exc_info=True)
            flash(f'Fout: {str(e)}', 'error')
            return redirect(url_for('transactions.import_csv'))
        finally:
            # Clean up temp file (retained copy is kept)
            if os.path.exists(temp_path):
                os.remove(temp_path)
                current_app.logger.debug(f"Temporary file removed: {temp_path}")
    else:
        current_app.logger.warning(f"Import failed: Invalid file type ({file.filename})")
        flash('Selecteer alstublieft een CSV bestand', 'error')
        return redirect(url_for('transactions.import_csv'))


@bp.route('/import/detect', methods=['POST'])
def detect_csv_format():
    """AJAX endpoint: peek at CSV header and return the detected format."""
    from importers import detect_format

    if 'csv_file' not in request.files:
        return jsonify({'format_id': None, 'format_name': None})

    file = request.files['csv_file']
    if not file or not file.filename.endswith('.csv'):
        return jsonify({'format_id': None, 'format_name': None})

    temp_path = os.path.join('uploads', f'_detect_{file.filename}')
    os.makedirs('uploads', exist_ok=True)
    file.save(temp_path)

    try:
        importer = detect_format(temp_path)
        if importer:
            return jsonify({'format_id': importer.id, 'format_name': importer.name})
        return jsonify({'format_id': None, 'format_name': None})
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@bp.route('/import/rebuild', methods=['POST'])
def rebuild_from_files():
    """Rebuild the transaction database from retained CSV files.

    Truncates transactions / transactions_raw / import_batches and
    re-imports every retained file using its stored format_id.
    Categories, rules, and other config tables are preserved.
    """
    try:
        result = db.rebuild_from_files()
        total_imported = result.get('imported', 0)
        total_errors = result.get('errors', 0)
        files_processed = result.get('files_processed', 0)

        # Re-apply transfer marking after rebuild
        transfer_count = db.auto_mark_transfer_transactions() or 0

        # Re-apply transfer pair linking
        link_count = db.auto_link_transfer_pairs() or 0

        # Re-apply auto-categorization
        cat_count = db.auto_categorize_transactions() or 0

        msg = (f'Herstel voltooid: {files_processed} bestanden, '
               f'{total_imported} mutaties geïmporteerd, '
               f'{total_errors} fouten')
        if transfer_count > 0:
            msg += f', {transfer_count} overboekingen gemarkeerd'
        if link_count > 0:
            msg += f', {link_count} overboeking paren gekoppeld'
        if cat_count > 0:
            msg += f', {cat_count} automatisch gecategoriseerd'
        flash(msg, 'success')
    except Exception as e:
        current_app.logger.error(f"Rebuild error: {str(e)}", exc_info=True)
        flash(f'Herstel mislukt: {str(e)}', 'error')

    return redirect(url_for('transactions.import_csv'))