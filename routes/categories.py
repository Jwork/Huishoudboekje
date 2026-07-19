from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import pandas as pd
from extensions import db

bp = Blueprint('categories', __name__)

# Dutch category structure (3-level: Main Category → Group → Items)
# Note: Category names must be unique globally in the database
DUTCH_CATEGORIES = [
    {
        "id": "Inkomsten",
        "name": "Inkomsten",
        "groups": [
            {
                "name": "Inkomsten Algemeen",
                "items": [
                    "Salaris / Loon",
                    "Uitkeringen",
                    "Toeslagen",
                    "Belastingteruggave",
                    "Overige inkomsten"
                ]
            }
        ]
    },
    {
        "id": "Vaste Lasten",
        "name": "Vaste Lasten",
        "groups": [
            {
                "name": "Wonen",
                "items": [
                    "Huur of Hypotheek",
                    "VvE-bijdrage",
                    "Energie (Gas & Elektriciteit)",
                    "Water",
                    "Gemeentelijke belastingen"
                ]
            },
            {
                "name": "Verzekeringen",
                "items": [
                    "Zorgverzekering",
                    "Woonverzekeringen (Inboedel, Opstal, WA)",
                    "Levensverzekering",
                    "Uitvaartverzekering"
                ]
            },
            {
                "name": "Abonnementen & Telecom",
                "items": [
                    "Internet, TV & Bellen",
                    "Mobiele telefonie",
                    "Streamingdiensten",
                    "Lidmaatschappen",
                    "Goede doelen / Loterijen"
                ]
            },
            {
                "name": "Schulden",
                "items": [
                    "Studielening (DUO)",
                    "Persoonlijke lening",
                    "Creditcard aflossing",
                    "Roodstand aanzuivering"
                ]
            }
        ]
    },
    {
        "id": "Huishoudelijke Uitgaven",
        "name": "Huishoudelijke Uitgaven (Variabel)",
        "groups": [
            {
                "name": "Dagelijkse Boodschappen",
                "items": [
                    "Supermarkt",
                    "Drogisterij & Verzorging",
                    "Huisdieren",
                    "Huis & Tuin"
                ]
            },
            {
                "name": "Vervoer",
                "items": [
                    "Auto (Vaste lasten)",
                    "Auto (Brandstof / Onderhoud)",
                    "Openbaar Vervoer",
                    "Fiets / Scooter",
                    "Parkeren & Taxi"
                ]
            }
        ]
    },
    {
        "id": "Persoonlijk & Vrije Tijd",
        "name": "Persoonlijk & Vrije Tijd",
        "groups": [
            {
                "name": "Gezin & Persoonlijk",
                "items": [
                    "Kinderen",
                    "Kleding & Schoenen",
                    "Uiterlijke verzorging",
                    "Zorgkosten (Eigen risico)",
                    "Educatie"
                ]
            },
            {
                "name": "Luxe & Ontspanning",
                "items": [
                    "Horeca & Uit eten",
                    "Uitjes & Cultuur",
                    "Vakantie",
                    "Cadeaus",
                    "Hobby's"
                ]
            }
        ]
    },
    {
        "id": "Sparen & Reserveren",
        "name": "Sparen & Reserveren",
        "groups": [
            {
                "name": "Sparen",
                "items": [
                    "Bufferopbouw",
                    "Spaardoelen",
                    "Beleggen",
                    "Pensioensparen"
                ]
            }
        ]
    }
]


def build_category_tree_recursive(cat_df, parent_id=None, path=""):
    """Recursively build category tree for unlimited depth"""
    if parent_id is None:
        children = cat_df[cat_df['parent_id'].isna()]
    else:
        children = cat_df[cat_df['parent_id'] == parent_id]
    
    result = []
    for _, row in children.iterrows():
        cat_id = int(row['id'])
        cat_name = str(row['name'])
        
        # content: Handle icon safely (avoid NaN)
        cat_icon = row.get('icon')
        if pd.isna(cat_icon) or str(cat_icon).lower() == 'nan':
            cat_icon = None
            
        full_path = f"{path} → {cat_name}" if path else cat_name
        
        node = {
            'id': cat_id,
            'name': cat_name,
            'icon': cat_icon,
            'path': full_path,
            'children': build_category_tree_recursive(cat_df, cat_id, full_path)
        }
        result.append(node)
    
    return result


def flatten_categories_for_dropdown(cat_df, parent_id=None, depth=0, path=""):
    """Flatten categories with depth info for dropdown display"""
    if parent_id is None:
        children = cat_df[cat_df['parent_id'].isna()]
    else:
        children = cat_df[cat_df['parent_id'] == parent_id]
    
    result = []
    for _, row in children.iterrows():
        cat_id = int(row['id'])
        cat_name = str(row['name'])
        if pd.isna(row['name']) or cat_name.lower() == 'nan':
            cat_name = "(Unnamed)"
            
        full_path = f"{path} → {cat_name}" if path else cat_name
        
        result.append({
            'id': cat_id,
            'name': cat_name,
            'path': full_path,
            'depth': depth
        })
        # Recursively add children
        result.extend(flatten_categories_for_dropdown(cat_df, cat_id, depth + 1, full_path))
    
    return result


@bp.route('/categories')
def categories():
    cat_df = db.get_categories()
    
    # Handle empty categories case
    if cat_df.empty:
        return render_template('categories.html', categories=[], flat_categories=[])
    
    # Build recursive tree structure (unlimited depth)
    cat_tree = build_category_tree_recursive(cat_df)
    
    # Flatten for dropdown with depth indicators
    flat_categories = flatten_categories_for_dropdown(cat_df)
    
    return render_template('categories.html', categories=cat_tree, flat_categories=flat_categories)


@bp.route('/categories/add', methods=['POST'])
def add_category():
    name = request.form.get('name')
    parent_id = request.form.get('parent_id')
    icon = request.form.get('icon')
    parent_id = int(parent_id) if parent_id else None
    
    result = db.add_category(name, parent_id, icon=icon)
    if result:
        flash('Categorie toegevoegd!', 'success')
    else:
        flash('Categorie bestaat al', 'error')
    
    return redirect(url_for('categories.categories'))


@bp.route('/categories/<int:category_id>/delete', methods=['GET', 'POST'])
def delete_category(category_id):
    if request.method == 'GET':
        return redirect(url_for('categories.categories'))
    success, message = db.delete_category(category_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('categories.categories'))


@bp.route('/api/categories', methods=['POST'])
def api_add_category():
    """API endpoint to add a category (for AJAX calls)"""
    data = request.get_json()
    name = data.get('name', '').strip()
    parent_id = data.get('parent_id')
    icon = data.get('icon')
    parent_name = None
    
    if not name:
        return jsonify({'success': False, 'error': 'Categorie naam is verplicht'}), 400
    
    if parent_id:
        parent_id = int(parent_id)
        # Get parent name for display
        cat_df = db.get_categories()
        parent_row = cat_df[cat_df['id'] == parent_id]
        if len(parent_row) > 0:
            parent_name = str(parent_row.iloc[0]['name'])
    
    result = db.add_category(name, parent_id, icon=icon)
    if result:
        display_name = f"{parent_name} → {name}" if parent_name else name
        return jsonify({
            'success': True, 
            'category': {'id': result, 'name': display_name, 'icon': icon}
        })
    else:
        return jsonify({'success': False, 'error': 'Categorie bestaat al'}), 400


@bp.route('/api/categories', methods=['GET'])
def api_get_categories():
    """API endpoint to get all categories with parent names"""
    cat_df = db.get_categories()
    categories = []
    for _, row in cat_df.iterrows():
        display_name = str(row['name'])
        parent = row.get('parent_name')
        if pd.notna(parent) and str(parent).lower() != 'nan':
            display_name = f"{parent} → {row['name']}"
        categories.append({'id': int(row['id']), 'name': display_name})
    return jsonify({'categories': categories})


@bp.route('/api/categories/<int:category_id>/rename', methods=['POST'])
def api_rename_category(category_id):
    """Rename a category via AJAX"""
    data = request.get_json()
    new_name = data.get('name', '').strip() if data else ''
    
    if not new_name:
        return jsonify({'success': False, 'error': 'Naam kan niet leeg zijn'}), 400
    
    try:
        db.update_category(category_id, new_name)
        return jsonify({'success': True, 'name': new_name})
    except Exception as e:
        error_msg = str(e)
        if 'unique' in error_msg.lower() or 'duplicate' in error_msg.lower():
            return jsonify({'success': False, 'error': 'Een categorie met die naam bestaat al'}), 400
        return jsonify({'success': False, 'error': error_msg}), 400
