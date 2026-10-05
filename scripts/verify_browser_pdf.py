"""Read-only comparison of a downloaded PDF with its saved synthetic C-67."""
import json
import sys
from pathlib import Path
from pypdf import PdfReader
pdf,report=map(Path,sys.argv[1:3])
value=json.loads(report.read_text())['c67']
normalize=lambda text: ''.join(text.split()).replace('\u00ad','')
pages=[]
for number,page in enumerate(PdfReader(pdf).pages,1):
    lines=page.extract_text().splitlines()
    if lines and lines[-1].strip()==str(number):lines.pop()  # page footer, not report content
    pages.append('\n'.join(lines))
text=normalize('\n'.join(pages))
assert normalize(value['cycle_id']) in text
for skill in value['skills']:
    assert normalize(skill['skill_name']) in text
for recommendation in value['recommendations']:
    for key in ('goal','practice','progress_signal','application_context'):
        assert normalize(recommendation[key]) in text, key
    for limit in recommendation['limitations']:
        assert normalize(limit) in text, 'limitation'
    for basis in recommendation['basis_refs']:
        for excerpt in basis['material_excerpts']:
            assert normalize(excerpt['quote']) in text, 'material quote'
assert 'Недопустимоеисторическоепроявление' not in text
print('PDF content matches saved C-67; pages:',len(PdfReader(pdf).pages))
