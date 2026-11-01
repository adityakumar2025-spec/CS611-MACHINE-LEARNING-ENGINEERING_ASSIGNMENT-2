from pathlib import Path
import pymupdf
root=Path(__file__).resolve().parents[1]
doc=pymupdf.open(root/'inputs/Assignment 2.pdf')
for i,page in enumerate(doc):
    page.get_pixmap(matrix=pymupdf.Matrix(1,1)).save(root/f'evidence/assignment_page_{i+1}.png')
print('Rendered',len(doc),'assignment pages')
