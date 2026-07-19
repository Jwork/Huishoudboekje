from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db

bp = Blueprint('accounts', __name__)

@bp.route('/accounts')
def accounts_page():
    """Manage account names"""
    # Show only owned accounts by default, optionally show all (including counter accounts)
    show_all = request.args.get('show_all', 'false') == 'true'
    accounts = db.get_accounts(include_counter_accounts=show_all)
    transfer_accounts = db.get_transfer_accounts()
    transfer_patterns = db.get_transfer_patterns()
    
    # Get all unique counter accounts for the dropdown
    counter_accounts = db.get_accounts(include_counter_accounts=True)
    
    # Get all unique merchants for pattern dropdown
    merchants = db.get_unique_merchants()
    
    # Get linked transfer pairs and unlinked potential pairs
    linked_pairs = db.get_linked_transfers()
    unlinked_pairs = db.find_unlinked_transfer_pairs()
    
    return render_template('accounts.html', 
                          accounts=accounts, 
                          show_all=show_all,
                          transfer_accounts=transfer_accounts,
                          transfer_patterns=transfer_patterns,
                          counter_accounts=counter_accounts,
                          merchants=merchants,
                          linked_pairs=linked_pairs,
                          unlinked_pairs=unlinked_pairs)


@bp.route('/set-account-name', methods=['POST'])
def set_account_name():
    """Set a friendly name for an account"""
    account_number = request.form.get('account_number')
    name = request.form.get('name')
    
    if account_number and name:
        db.set_account_name(account_number, name.strip())
        flash(f'Rekening naam ingesteld op "{name}"', 'success')
    
    return redirect(request.referrer or url_for('accounts.accounts_page'))


@bp.route('/toggle-transfer-account', methods=['POST'])
def toggle_transfer_account():
    """Toggle whether an account is a transfer/savings account"""
    account_number = request.form.get('account_number')
    is_transfer = request.form.get('is_transfer') == '1'
    
    if account_number:
        db.toggle_transfer_account(account_number, is_transfer)
        
        if is_transfer:
            # Mark existing transactions as transfers
            count = db.mark_transfer_account_transactions(account_number)
            flash(f'Gemarkeerd als overboeking rekening ({count} mutaties bijgewerkt)', 'success')
        else:
            flash('Overboeking rekening markering verwijderd', 'success')
    
    return redirect(url_for('accounts.accounts_page'))


@bp.route('/add-transfer-account', methods=['POST'])
def add_transfer_account():
    """Mark an account as a transfer/savings account"""
    account_number = request.form.get('account_number')
    name = request.form.get('name', '').strip()
    mark_existing = request.form.get('mark_existing') == 'on'
    
    if account_number:
        db.add_transfer_account(account_number, name or None)
        msg = f'"{name or account_number}" toegevoegd als overboeking rekening'
        
        if mark_existing:
            count = db.mark_transfer_account_transactions(account_number)
            msg += f' en {count} bestaande mutaties gemarkeerd als Overboeking'
        
        flash(msg, 'success')
    
    return redirect(url_for('accounts.accounts_page'))


@bp.route('/remove-transfer-account/<int:account_id>', methods=['POST'])
def remove_transfer_account(account_id):
    """Remove a transfer account"""
    db.remove_transfer_account(account_id)
    flash('Overboeking rekening verwijderd', 'success')
    return redirect(url_for('accounts.accounts_page'))


@bp.route('/add-transfer-pattern', methods=['POST'])
def add_transfer_pattern():
    """Add a merchant pattern to mark as transfer"""
    pattern = request.form.get('pattern', '').strip()
    name = request.form.get('name', '').strip()
    mark_existing = request.form.get('mark_existing') == 'on'
    
    if pattern:
        db.add_transfer_pattern(pattern, name or None)
        msg = f'Patroon "{pattern}" toegevoegd'
        
        if mark_existing:
            count = db.mark_transfer_pattern_transactions(pattern)
            msg += f' en {count} bestaande mutaties gemarkeerd als Overboeking'
        
        flash(msg, 'success')
    
    return redirect(url_for('accounts.accounts_page'))


@bp.route('/remove-transfer-pattern/<int:pattern_id>', methods=['POST'])
def remove_transfer_pattern(pattern_id):
    """Remove a transfer pattern"""
    db.remove_transfer_pattern(pattern_id)
    flash('Overboeking patroon verwijderd', 'success')
    return redirect(url_for('accounts.accounts_page'))


@bp.route('/set-active-account', methods=['POST'])
def set_active_account():
    """Set the active account for filtering"""
    account = request.form.get('account', '')
    if account:
        session['active_account'] = account
    else:
        session.pop('active_account', None)
    
    # Redirect back to the page they were on
    return redirect(request.referrer or url_for('main.dashboard'))


# Transfer pairing routes
@bp.route('/link-transfer-pair', methods=['POST'])
def link_transfer_pair():
    """Link two transactions as a transfer pair"""
    id1 = request.form.get('id1', type=int)
    id2 = request.form.get('id2', type=int)
    
    if id1 and id2:
        db.link_transfer_pair(id1, id2)
        flash('Overboeking paar gekoppeld!', 'success')
    
    return redirect(url_for('accounts.accounts_page'))


@bp.route('/unlink-transfer-pair/<int:transaction_id>', methods=['POST'])
def unlink_transfer_pair(transaction_id):
    """Unlink a transfer pair"""
    db.unlink_transfer_pair(transaction_id)
    flash('Overboeking paar ontkoppeld', 'success')
    return redirect(url_for('accounts.accounts_page'))


@bp.route('/auto-link-transfers', methods=['POST'])
def auto_link_transfers():
    """Automatically link all matching transfer pairs"""
    count = db.auto_link_transfer_pairs()
    if count > 0:
        flash(f'{count} overboeking paar(en) gekoppeld!', 'success')
    else:
        flash('Geen overeenkomende overboeking paren gevonden', 'info')
    return redirect(url_for('accounts.accounts_page'))
