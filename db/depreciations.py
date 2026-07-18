"""Depreciation repository - tracks depreciating assets"""
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from .connection import ConnectionManager


class DepreciationRepository(ConnectionManager):
    """Repository for depreciation/asset tracking"""

    def add_depreciation(self, name, purchase_date, purchase_amount,
                         useful_life_months, residual_value=0,
                         category_id=None, notes=None):
        """Add a new depreciation asset"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO depreciations
                (name, purchase_date, purchase_amount, useful_life_months,
                 residual_value, category_id, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, purchase_date, purchase_amount, useful_life_months,
              residual_value, category_id, notes))
        result = cursor.fetchone()
        conn.commit()
        return result['id']

    def update_depreciation(self, depreciation_id, **kwargs):
        """Update depreciation asset fields"""
        if not kwargs:
            return
        conn = self.connect()
        cursor = conn.cursor()
        set_parts = []
        params = []
        for key, value in kwargs.items():
            set_parts.append(f'{key} = %s')
            params.append(value)
        params.append(depreciation_id)
        cursor.execute(
            f"UPDATE depreciations SET {', '.join(set_parts)} WHERE id = %s",
            params
        )
        conn.commit()

    def delete_depreciation(self, depreciation_id):
        """Delete a depreciation asset"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM depreciations WHERE id = %s', (depreciation_id,))
        conn.commit()

    def get_depreciations(self, active_only=True):
        """Get all depreciation assets, optionally filtered to active ones"""
        conn = self.connect()
        cursor = conn.cursor()
        where = 'WHERE d.is_active = TRUE' if active_only else ''
        cursor.execute(f"""
            SELECT d.*, c.name AS category_name
            FROM depreciations d
            LEFT JOIN categories c ON d.category_id = c.id
            {where}
            ORDER BY d.purchase_date DESC
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows] if rows else []

    def get_depreciation(self, depreciation_id):
        """Get a single depreciation asset by ID"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.*, c.name AS category_name
            FROM depreciations d
            LEFT JOIN categories c ON d.category_id = c.id
            WHERE d.id = %s
        """, (depreciation_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def calculate_depreciation(self, depreciation_id, as_of_date=None):
        """Calculate depreciation values for an asset as of a given date.

        Uses straight-line depreciation:
            monthly = (purchase_amount - residual_value) / useful_life_months
            accumulated = monthly * months_elapsed
            book_value = purchase_amount - accumulated (floored at residual_value)
        """
        asset = self.get_depreciation(depreciation_id)
        if not asset:
            return None

        if as_of_date is None:
            as_of_date = date.today()
        elif isinstance(as_of_date, str):
            as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()

        purchase_date = asset['purchase_date']
        if isinstance(purchase_date, str):
            purchase_date = datetime.strptime(purchase_date, '%Y-%m-%d').date()

        purchase_amount = float(asset['purchase_amount'])
        residual_value = float(asset.get('residual_value', 0) or 0)
        useful_life_months = int(asset['useful_life_months'])

        depreciable = purchase_amount - residual_value
        monthly_depr = depreciable / useful_life_months if useful_life_months > 0 else 0

        # Calculate months elapsed
        rd = relativedelta(as_of_date, purchase_date)
        months_elapsed = rd.years * 12 + rd.months
        if as_of_date.day >= purchase_date.day:
            pass  # full month counted
        else:
            months_elapsed = max(0, months_elapsed)

        months_elapsed = max(0, min(months_elapsed, useful_life_months))

        accumulated = monthly_depr * months_elapsed
        book_value = max(purchase_amount - accumulated, residual_value)

        end_date = purchase_date + relativedelta(months=useful_life_months)
        is_fully_depreciated = as_of_date >= end_date

        return {
            'id': asset['id'],
            'name': asset['name'],
            'purchase_date': str(purchase_date),
            'purchase_amount': purchase_amount,
            'residual_value': residual_value,
            'useful_life_months': useful_life_months,
            'monthly_depreciation': round(monthly_depr, 2),
            'months_elapsed': months_elapsed,
            'accumulated_depreciation': round(accumulated, 2),
            'book_value': round(book_value, 2),
            'end_date': str(end_date),
            'is_fully_depreciated': is_fully_depreciated,
            'percentage_depreciated': round(
                (accumulated / depreciable * 100) if depreciable > 0 else 100, 1
            )
        }

    def get_depreciation_summary(self, as_of_date=None):
        """Get summary of all active depreciations"""
        assets = self.get_depreciations(active_only=True)
        summary = []
        totals = {
            'total_purchase': 0.0,
            'total_accumulated': 0.0,
            'total_book_value': 0.0,
            'total_monthly': 0.0
        }
        for asset in assets:
            calc = self.calculate_depreciation(asset['id'], as_of_date)
            if calc:
                summary.append(calc)
                totals['total_purchase'] += calc['purchase_amount']
                totals['total_accumulated'] += calc['accumulated_depreciation']
                totals['total_book_value'] += calc['book_value']
                totals['total_monthly'] += calc['monthly_depreciation']

        return {'assets': summary, 'totals': totals}

    def get_monthly_depreciation_schedule(self, depreciation_id):
        """Get month-by-month depreciation schedule for an asset"""
        asset = self.get_depreciation(depreciation_id)
        if not asset:
            return []

        purchase_date = asset['purchase_date']
        if isinstance(purchase_date, str):
            purchase_date = datetime.strptime(purchase_date, '%Y-%m-%d').date()

        purchase_amount = float(asset['purchase_amount'])
        residual_value = float(asset.get('residual_value', 0) or 0)
        useful_life_months = int(asset['useful_life_months'])

        depreciable = purchase_amount - residual_value
        monthly_depr = depreciable / useful_life_months if useful_life_months > 0 else 0

        schedule = []
        for m in range(useful_life_months):
            month_date = purchase_date + relativedelta(months=m + 1)
            accumulated = monthly_depr * (m + 1)
            book_value = max(purchase_amount - accumulated, residual_value)
            schedule.append({
                'month': m + 1,
                'date': str(month_date),
                'depreciation': round(monthly_depr, 2),
                'accumulated': round(accumulated, 2),
                'book_value': round(book_value, 2)
            })
        return schedule

    def get_year_depreciation_expense(self, year=None):
        """Get total depreciation expense for a given year"""
        if year is None:
            year = date.today().year

        assets = self.get_depreciations(active_only=True)
        total = 0.0

        for asset in assets:
            purchase_date = asset['purchase_date']
            if isinstance(purchase_date, str):
                purchase_date = datetime.strptime(purchase_date, '%Y-%m-%d').date()

            purchase_amount = float(asset['purchase_amount'])
            residual_value = float(asset.get('residual_value', 0) or 0)
            useful_life_months = int(asset['useful_life_months'])
            end_date = purchase_date + relativedelta(months=useful_life_months)

            if end_date.year < year or purchase_date.year > year:
                continue

            depreciable = purchase_amount - residual_value
            monthly_depr = depreciable / useful_life_months if useful_life_months > 0 else 0

            # Count months in this year that fall within the asset's life
            start_month = max(purchase_date.replace(day=1),
                              date(year, 1, 1))
            end_month = min(end_date, date(year, 12, 31))

            if start_month > end_month:
                continue

            rd = relativedelta(end_month, start_month)
            months_in_year = rd.years * 12 + rd.months + 1
            total += monthly_depr * months_in_year

        return round(total, 2)
