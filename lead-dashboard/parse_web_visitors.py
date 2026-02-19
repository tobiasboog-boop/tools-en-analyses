"""Parse Web Visitors Excel export en creeer activiteitsscore."""
import pandas as pd
import re
from datetime import datetime, timedelta

# Read Excel
excel_path = r"C:\Users\tobia\Downloads\lijst.xlsx"
df = pd.read_excel(excel_path)

# Data is in 1 kolom, pattern is:
# Row 0 (header): First company name
# Row 1: Location/industry of first company
# Row 2: Time since last visit
# Row 3: Second company name
# Row 4: Location/industry
# Row 5: Time
# etc.

visitors = []

# First company is in the column name
first_company = df.columns[0]
visitors_data = df.iloc[:, 0].tolist()

# Process in groups of 3: company name, location, time
i = 0
current_company = first_company

while i < len(visitors_data):
    # Current entry should be location/industry
    location_info = str(visitors_data[i]).strip() if i < len(visitors_data) else ""

    # Next entry should be time
    time_info = str(visitors_data[i + 1]).strip() if (i + 1) < len(visitors_data) else ""

    # Parse tijd naar score
    days_ago = 999  # default = oud

    if 'geleden' in time_info.lower():
        if 'vandaag' in time_info.lower():
            days_ago = 0
        elif 'minu' in time_info.lower():
            days_ago = 0  # Minuten geleden = vandaag
        elif 'uur' in time_info.lower():
            match = re.search(r'(\d+)\s*uur', time_info)
            if match:
                days_ago = 0  # Uren geleden = vandaag
            else:
                days_ago = 0
        elif 'dag' in time_info.lower():
            match = re.search(r'(\d+)\s*dag', time_info)
            if match:
                days_ago = int(match.group(1))
        elif 'week' in time_info.lower():
            match = re.search(r'(\d+)\s*week', time_info)
            if match:
                days_ago = int(match.group(1)) * 7
        elif 'maand' in time_info.lower():
            match = re.search(r'(\d+)\s*maand', time_info)
            if match:
                days_ago = int(match.group(1)) * 30

        # Bereken engagement score gebaseerd op recentheid
        # Groen (zeer recent, 0-7 dagen): 8-10 punten
        # Oranje (recent, 8-21 dagen): 4-6 punten
        # Rood (minder recent, 22-30 dagen): 2-3 punten
        # Oud (>30 dagen): 1 punt

        if days_ago <= 2:
            score = 10
            level = 'GROEN'
        elif days_ago <= 7:
            score = 8
            level = 'GROEN'
        elif days_ago <= 14:
            score = 6
            level = 'ORANJE'
        elif days_ago <= 21:
            score = 4
            level = 'ORANJE'
        elif days_ago <= 30:
            score = 3
            level = 'ROOD'
        else:
            score = 1
            level = 'ROOD'

        visitors.append({
            'company_name': current_company,
            'location_info': location_info,
            'last_visit': time_info,
            'days_ago': days_ago,
            'website_visits_score': score,
            'activity_level': level
        })

    # Next company name (if exists)
    if (i + 2) < len(visitors_data):
        current_company = str(visitors_data[i + 2]).strip()
        i += 3
    else:
        break

# Create DataFrame
visitors_df = pd.DataFrame(visitors)

print(f"\nGeparsed: {len(visitors_df)} web visitors\n")
print("=" * 100)
print("ACTIVITEIT SCORES:")
print("=" * 100)
print(visitors_df[['company_name', 'last_visit', 'days_ago', 'website_visits_score', 'activity_level']].head(20).to_string(index=False))

# Verdeling per level
print("\n" + "=" * 100)
print("VERDELING:")
print("=" * 100)
for level in ['GROEN', 'ORANJE', 'ROOD']:
    count = len(visitors_df[visitors_df['activity_level'] == level])
    pct = (count / len(visitors_df) * 100) if len(visitors_df) > 0 else 0
    print(f"  {level:10} {count:4} bedrijven ({pct:.1f}%)")

# Save for dashboard integration
csv_path = r"C:\projects\tools_en_analyses\lead-dashboard\web_visitors_scored.csv"
visitors_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f"\nOpgeslagen: {csv_path}")

# Also create simplified mapping: company -> score
mapping_df = visitors_df[['company_name', 'website_visits_score', 'activity_level']].copy()

mapping_path = r"C:\projects\tools_en_analyses\lead-dashboard\web_visitors_mapping.csv"
mapping_df.to_csv(mapping_path, index=False, encoding='utf-8-sig')
print(f"Mapping opgeslagen: {mapping_path}")
