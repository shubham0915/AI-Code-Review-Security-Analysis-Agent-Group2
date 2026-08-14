import os
import re
from datetime import datetime, timedelta

files_to_update = [
    "docs/generate_agile_template.py",
    "docs/generate_defect_tracker.py",
    "docs/generate_test_plan.py"
]

old_start = datetime.strptime("2025-01-06", "%Y-%m-%d")
old_end = datetime.strptime("2025-03-07", "%Y-%m-%d")
new_start = datetime.strptime("2026-07-01", "%Y-%m-%d")
new_end = datetime.strptime("2026-08-12", "%Y-%m-%d")

old_duration = (old_end - old_start).days
new_duration = (new_end - new_start).days

def map_date(match):
    date_str = match.group(0)
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        if not (datetime(2025, 1, 1) <= d <= datetime(2025, 3, 31)):
            return date_str
        
        offset = (d - old_start).days
        scaled_offset = int(round(offset * (new_duration / old_duration)))
        new_date = new_start + timedelta(days=scaled_offset)
        
        # Ensure it doesn't go past new_end
        if new_date > new_end:
            new_date = new_end
            
        return new_date.strftime("%Y-%m-%d")
    except ValueError:
        return date_str

for filepath in files_to_update:
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue
        
    with open(filepath, "r") as f:
        content = f.read()
        
    new_content = re.sub(r"2025-\d{2}-\d{2}", map_date, content)
    
    with open(filepath, "w") as f:
        f.write(new_content)
        
    print(f"Updated dates in {filepath}")
