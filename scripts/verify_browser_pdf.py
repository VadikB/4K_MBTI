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
assert normalize(value['cycle_id']) not in text, 'technical cycle id'
for skill in value['skills']:
    assert normalize(skill['skill_name']) in text
for summary in value['descriptive'].get('summary', []):
    assert normalize(summary) in text, 'descriptive summary'
for claim in value['descriptive'].get('claims', []):
    assert normalize(claim['text']) in text, 'descriptive claim'
assert 'Недопустимоеисторическоепроявление' not in text
print('PDF content matches saved C-67; pages:',len(PdfReader(pdf).pages))
