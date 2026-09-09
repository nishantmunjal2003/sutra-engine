from sutra.utils.persistence import ProjectPersistenceManager

db = ProjectPersistenceManager('build')
p = db.load_project('b2bfe28342a04497938ab80964f6e0f4')
for i, b in enumerate(p['blocks']):
    if b['type'] == 'table':
        print(f"=== TABLE AT BLOCK {i}: ID {b['id']} ===")
        t = b['content']
        print("Caption:", "".join(r.get("text", "") for r in t.get("caption", [])))
        print("Header rows:", t.get("header_rows"))
        print("Total rows:", len(t.get("rows", [])))
        for r_i, r in enumerate(t.get("rows", [])):
            cells_summary = []
            row_items = r if isinstance(r, list) else r.get("cells", [])
            for c in row_items:
                if isinstance(c, dict):
                    txt = "".join(run.get("text", "") for run in c.get("content", [])) if isinstance(c.get("content"), list) else str(c.get("content", ""))
                    cells_summary.append(f"[{txt.strip()[:25]}] (cs={c.get('colspan', 1)}, hdr={c.get('is_header')})")
                else:
                    cells_summary.append(str(c)[:25])
            print(f"  Row {r_i}: {' | '.join(cells_summary)}")
