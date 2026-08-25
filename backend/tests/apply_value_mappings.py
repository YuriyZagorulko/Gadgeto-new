import sys, psycopg2, re, json
sys.path.insert(0, '/app')
from app.core.db_connect import DB

# Load the attribute mapping
with open('/tmp/attr_map.json', 'r', encoding='utf-8') as f:
    ATTR_MAP = json.load(f)

conn = psycopg2.connect(DB)
conn.autocommit = True
cur = conn.cursor()

# Load internal attributes by slug
cur.execute("SELECT id, name, slug FROM attributes ORDER BY id")
internal_attrs = {}
for r in cur.fetchall():
    internal_attrs[r[2].lower().strip()] = (r[0], r[1])

# Load existing supplier_attributes
cur.execute("SELECT id, supplier_name FROM supplier_attributes")
existing_sa = {}
for r in cur.fetchall():
    existing_sa[r[1]] = r[0]

# Load internal values
cur.execute("SELECT id, attribute_id, value FROM attribute_values")
internal_vals = {}
for r in cur.fetchall():
    internal_vals[(r[1], r[2].lower().strip())] = r[0]

# Read report
with open('/tmp/import-report-57-2026-08-25.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = None
for i, line in enumerate(lines):
    if 'Невідображені значення атрибутів' in line:
        start_idx = i + 1
        break

report_attrs = {}
for line in lines[start_idx:]:
    line = line.strip()
    if not line:
        continue
    m = re.match(r'^(.*?) = (.*?) \u2014 (\d+) \u0442\u043e\u0432\u0430\u0440', line)
    if not m:
        m = re.match(r'^(.*?) = (.*?) \u2014 (\d+) товар', line)
    if not m:
        m = re.match(r'^(.*?) = (.*?) \u2014 (\d+)', line)
    if m:
        attr_name = m.group(1).strip()
        value = m.group(2).strip()
        report_attrs.setdefault(attr_name, []).append(value)

print(f'Processing {len(report_attrs)} attributes, {sum(len(v) for v in report_attrs.values())} values')

stats = {'sa_created': 0, 'am_created': 0, 'vals_created': 0, 'vals_existing': 0, 'vm_created': 0, 'no_match': 0}

for attr_name, vals in sorted(report_attrs.items()):
    int_slug = ATTR_MAP.get(attr_name, attr_name.lower().strip().replace(' ', '-'))
    internal_attr = internal_attrs.get(int_slug)
    if not internal_attr:
        for k, v in internal_attrs.items():
            if attr_name.lower() in k or k in attr_name.lower():
                if len(attr_name) > 3 and len(k) > 3:
                    internal_attr = v
                    break
    if not internal_attr:
        print(f'  NO MATCH: {attr_name}')
        stats['no_match'] += 1
        continue
    aid = internal_attr[0]

    sa_id = existing_sa.get(attr_name)
    if not sa_id:
        cur.execute('INSERT INTO supplier_attributes (supplier_id, supplier_name, is_removed, created_at, updated_at) VALUES (2, %s, FALSE, NOW(), NOW()) RETURNING id', (attr_name,))
        sa_id = cur.fetchone()[0]
        existing_sa[attr_name] = sa_id
        stats['sa_created'] += 1
        cur.execute('INSERT INTO attribute_mappings (supplier_attribute_id, attribute_id, is_active, created_at, updated_at) VALUES (%s, %s, TRUE, NOW(), NOW()) ON CONFLICT DO NOTHING', (sa_id, aid))
        stats['am_created'] += 1

    for value in vals:
        vkey = (aid, value.lower().strip())
        iv_id = internal_vals.get(vkey)
        if not iv_id:
            norm = value.lower().strip()
            if norm in ['немає даних', 'немає', '-', '\u2014']:
                norm = 'немає'
                iv_id = internal_vals.get((aid, norm))
        if not iv_id:
            slug = re.sub(r'[^a-z0-9\u0430-\u044f\u0456\u0457\u0454\u0491\s-]', '', value.lower().strip())[:100]
            slug = re.sub(r'\s+', '-', slug.strip('-'))[:100]
            cur.execute('INSERT INTO attribute_values (attribute_id, value, slug, sort, is_active, created_at, updated_at) VALUES (%s, %s, %s, 0, TRUE, NOW(), NOW()) RETURNING id', (aid, value, slug))
            iv_id = cur.fetchone()[0]
            internal_vals[vkey] = iv_id
            stats['vals_created'] += 1
        else:
            stats['vals_existing'] += 1

        cur.execute('SELECT id FROM supplier_attribute_values WHERE supplier_attribute_id = %s AND supplier_value = %s', (sa_id, value))
        sav = cur.fetchone()
        if not sav:
            cur.execute('INSERT INTO supplier_attribute_values (supplier_attribute_id, supplier_value, is_removed, created_at, updated_at) VALUES (%s, %s, FALSE, NOW(), NOW()) RETURNING id', (sa_id, value))
            sav_id = cur.fetchone()[0]
        else:
            sav_id = sav[0]

        cur.execute('INSERT INTO attribute_value_mappings (supplier_attribute_value_id, attribute_value_id, is_active, created_at, updated_at) VALUES (%s, %s, TRUE, NOW(), NOW()) ON CONFLICT DO NOTHING', (sav_id, iv_id))
        if cur.rowcount > 0:
            stats['vm_created'] += 1

print()
print('=== RESULTS ===')
for k, v in stats.items():
    print(f'  {k}: {v}')

conn.close()
print('Done!')
