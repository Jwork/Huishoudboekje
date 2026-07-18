from flask import Blueprint, redirect, url_for
from extensions import db

bp = Blueprint('main', __name__)

@bp.route('/')
def home():
    """Redirect home to dashboard overview"""
    return redirect(url_for('dashboard.overview'))
