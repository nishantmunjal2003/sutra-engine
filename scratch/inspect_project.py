from sutra.utils.persistence import ProjectPersistenceManager
from sutra.parser.docx import DocxParser, document_to_blocks
import tempfile

db = ProjectPersistenceManager('build')
docx_bytes = db.load_docx('b2bfe28342a04497938ab80964f6e0f4')
with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
    f.write(docx_bytes)
    tpath = f.name

parser = DocxParser(tpath)
doc = parser.parse()
blocks = document_to_blocks(doc)
print('Initial parsed blocks count:', len(blocks))
for i, b in enumerate(blocks):
    b_type = b.get('type')
    content = b.get('content')
    if b_type == 'paragraph':
        txt = ''.join(r.get('text', '') for r in content)
        if not txt.strip() or 'Empty' in txt or i in (24, 25, 26):
            print(f"Block {i}: id={b.get('id')}, len={len(txt)}, txt={repr(txt)}")
    elif b_type in ('table', 'figure'):
        print(f"Block {i}: id={b.get('id')}, type={b_type}")
