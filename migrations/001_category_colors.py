"""Assign distinct colors to parent and mid-level categories."""

def up(conn):
    cursor = conn.cursor()
    cursor.execute("SET search_path TO private, public")

    # Color palette for parent/mid-level categories
    # Format: (category_name, color)
    colors = [
        # Top-level
        ('Uitgaven',                '#ef4444'),  # red
        ('Inkomsten',               '#22c55e'),  # green
        ('Mutaties',                '#8b5cf6'),  # purple

        # Expense sub-groups
        ('Uitgaven vast',           '#f97316'),  # orange
        ('Variabele uitgaven',      '#3b82f6'),  # blue
        ('Luxe uitgaven',           '#ec4899'),  # pink

        # Fixed expenses
        ('Hypotheek',               '#b91c1c'),  # dark red
        ('Energie & Water',         '#f59e0b'),  # amber
        ('Verzekeringen',           '#6366f1'),  # indigo
        ('Internet, TV & Bellen',   '#06b6d4'),  # cyan
        ('Belastingen',             '#64748b'),  # slate
        ('Onderwijs & Kind',        '#a855f7'),  # violet
        ('Abonnementen & Diensten', '#14b8a6'),  # teal
        ('Vaste Donaties',          '#f43f5e'),  # rose
        ('Auto & Lease',            '#78716c'),  # stone

        # Variable expenses
        ('Boodschappen',            '#22d3ee'),  # cyan-light
        ('Gezondheid',              '#4ade80'),  # green-light
        ('Kleding',                 '#c084fc'),  # purple-light
        ('Huisraad (vervanging)',    '#fb923c'),  # orange-light
        ('Klussen en onderhoud',    '#a3a3a3'),  # neutral
        ('Tuin en aankleding',      '#84cc16'),  # lime
        ('Uiterlijk',               '#f472b6'),  # pink-light
        ('Vervoer, brandstof en onderhoud', '#0ea5e9'),  # sky

        # Luxury
        ('Uit eten',                '#e11d48'),  # rose-dark
        ('Dagjes uit',              '#7c3aed'),  # violet-dark
        ('Cadeaus',                 '#d946ef'),  # fuchsia
        ('Concerten en Feesten',    '#f59e0b'),  # amber
        ('Vakantie',                '#0891b2'),  # cyan-dark
        ('Digitale luxe',           '#6366f1'),  # indigo
        ('Gadgets',                 '#475569'),  # slate-dark
        ('Interieur & Sfeer',       '#ea580c'),  # orange-dark
        ('Sieraden',                '#db2777'),  # pink-dark

        # Income sub-groups
        ('Actieve inkomsten (vast)',       '#16a34a'),  # green-dark
        ('Passieve inkomsten (variabel)',  '#65a30d'),  # lime-dark
        ('Overige inkomsten',              '#059669'),  # emerald
        ('Salaris',                        '#15803d'),  # green-darker
        ('Toeslagen',                      '#4ade80'),  # green-light
        ('Vakantiegeld',                   '#86efac'),  # green-lighter

        # Uncategorized catch-all
        ('Niet-gecategoriseerd',    '#9ca3af'),  # gray
        ('Overige',                 '#a1a1aa'),  # zinc
        ('Overig',                  '#a1a1aa'),  # zinc
    ]

    for name, color in colors:
        cursor.execute(
            "UPDATE categories SET color = %s WHERE name = %s AND color = '#808080'",
            (color, name)
        )

    conn.commit()
    cursor.close()
