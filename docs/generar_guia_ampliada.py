"""Convierte la explicación ampliada del laboratorio en un DOCX editable."""
from pathlib import Path
import re
import json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/GUIA_EXPLICADA.md'
OUTPUT = ROOT / 'output/documentos/Guia_exposicion_Umbral_ampliada.docx'
record = json.loads((ROOT / 'evidencias/ejecucion-final/result.json').read_text(encoding='utf-8'))
assert len(record['results']) == 12
doc = Document()
s = doc.sections[0]
s.page_width, s.page_height = Inches(8.5), Inches(11)
s.top_margin, s.bottom_margin = Inches(.7), Inches(.68)
s.left_margin = s.right_margin = Inches(.75)
s.header_distance = s.footer_distance = Inches(.28)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','List Bullet','List Number']:
    st = doc.styles[name]
    st.font.name = 'Calibri'; st.font.color.rgb = RGBColor(0,0,0)
    st.paragraph_format.space_after = Pt(6)
doc.styles['Normal'].font.size = Pt(11)
doc.styles['Normal'].paragraph_format.line_spacing = 1.05
for name, size in [('Title',27),('Subtitle',14),('Heading 1',18),('Heading 2',12),('Heading 3',11)]:
    doc.styles[name].font.size = Pt(size)
for name in ['Heading 1','Heading 2','Heading 3']:
    doc.styles[name].paragraph_format.keep_with_next = True
    doc.styles[name].paragraph_format.space_before = Pt(9)
for style in doc.styles:
    if style.element.pPr is not None:
        for border in list(style.element.pPr.findall(qn('w:pBdr'))): style.element.pPr.remove(border)
head = s.header.paragraphs[0]; head.text = 'UMBRAL   ·   Guía explicada del laboratorio de seguridad'
for run in head.runs: run.font.size = Pt(9)
foot = s.footer.paragraphs[0]; foot.alignment = WD_ALIGN_PARAGRAPH.RIGHT
foot.add_run('Versión ampliada   ·   ')
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); foot._p.append(field)
for run in foot.runs: run.font.size = Pt(9)
doc.core_properties.title = 'Guía explicada del laboratorio de seguridad Umbral'
doc.core_properties.author = 'Equipo del trabajo práctico'
doc.core_properties.subject = 'Implementación peticiones demostraciones y correcciones de seis vulnerabilidades'

def text_runs(para, value):
    for i, part in enumerate(re.split(r'(\*\*.*?\*\*|`[^`]+`)', value)):
        if not part: continue
        if part.startswith('**') and part.endswith('**'):
            run = para.add_run(part[2:-2]); run.bold = True
        elif part.startswith('`') and part.endswith('`'):
            run = para.add_run(part[1:-1]); run.font.name = 'Consolas'; run.font.size = Pt(10)
        else: para.add_run(part)

def numbering(start_value=1):
    root = doc.part.numbering_part.element
    ids = [int(e.get(qn('w:numId'))) for e in root.findall(qn('w:num'))]
    n = max(ids, default=0)+1
    num = OxmlElement('w:num'); num.set(qn('w:numId'),str(n))
    abstract = OxmlElement('w:abstractNumId'); abstract.set(qn('w:val'),'7'); num.append(abstract)
    override = OxmlElement('w:lvlOverride'); override.set(qn('w:ilvl'),'0')
    start = OxmlElement('w:startOverride'); start.set(qn('w:val'),str(start_value)); override.append(start); num.append(override)
    root.append(num); return n

def add_table(lines):
    rows = [[c.strip() for c in line.strip().strip('|').split('|')] for line in lines]
    rows = [r for r in rows if not all(re.fullmatch(r'[:\- ]+',c) for c in r)]
    t = doc.add_table(rows=0, cols=len(rows[0])); t.autofit=False; t.alignment=WD_TABLE_ALIGNMENT.CENTER
    widths = [7/len(rows[0])] * len(rows[0])
    if len(rows[0]) == 3 and rows[0][0] == 'Caso': widths = [1.1,3.1,2.8]
    if len(rows[0]) == 3 and rows[0][0] == 'Observación conservada': widths = [2.8,2.1,2.1]
    for col,width in zip(t.columns,widths): col.width=Inches(width)
    for ri, values in enumerate(rows):
        row=t.add_row(); pr=row._tr.get_or_add_trPr()
        pr.append(OxmlElement('w:cantSplit'))
        if ri==0: pr.append(OxmlElement('w:tblHeader'))
        for cell,value,width in zip(row.cells,values,widths):
            cell.width=Inches(width); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            text_runs(cell.paragraphs[0],value)
            props=cell._tc.get_or_add_tcPr(); borders=OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                e=OxmlElement('w:'+edge); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:color'),'D9D9D9'); borders.append(e)
            props.append(borders); margins=OxmlElement('w:tcMar')
            for edge in ['top','left','bottom','right']:
                e=OxmlElement('w:'+edge); e.set(qn('w:w'),'85'); e.set(qn('w:type'),'dxa'); margins.append(e)
            props.append(margins)
            fill=OxmlElement('w:shd'); fill.set(qn('w:fill'),'E7E7E7' if ri==0 else ('F7F7F7' if ri%2==0 else 'FFFFFF')); props.append(fill)
            for para in cell.paragraphs:
                para.paragraph_format.space_after=Pt(2); para.paragraph_format.line_spacing=1.02
                for run in para.runs: run.font.size=Pt(10); run.bold=ri==0
    doc.add_paragraph('').paragraph_format.space_after=Pt(0)

lines=SOURCE.read_text(encoding='utf-8').splitlines(); i=0; page_break=False; list_id=None
while i<len(lines):
    line=lines[i]; i+=1
    if not line.strip(): list_id=None; continue
    if line=='<!-- PAGE -->': page_break=True; list_id=None; continue
    if line.startswith('```'):
        code=[]
        while i<len(lines) and not lines[i].startswith('```'):
            code.append(lines[i]); i+=1
        i+=1
        para=doc.add_paragraph(); para.paragraph_format.left_indent=Inches(.1)
        para.paragraph_format.space_before=Pt(3); para.paragraph_format.space_after=Pt(7)
        # Conservar bloques breves; permitir dividir los largos entre páginas.
        para.paragraph_format.keep_together=len(code)<=15
        run=para.add_run('\n'.join(code)); run.font.name='Consolas'; run.font.size=Pt(9)
        list_id=None; continue
    if line.startswith('|'):
        group=[line]
        while i<len(lines) and lines[i].startswith('|'): group.append(lines[i]); i+=1
        add_table(group); list_id=None; continue
    if line.startswith('# '):
        para=doc.add_paragraph(line[2:],'Title')
    elif line.startswith('## '):
        para=doc.add_heading(line[3:],level=1)
    elif line.startswith('### '):
        para=doc.add_heading(line[4:],level=2)
    elif line.startswith('- '):
        para=doc.add_paragraph(style='List Bullet'); text_runs(para,line[2:])
    elif re.match(r'^\d+\. ',line):
        if list_id is None: list_id=numbering(int(line.split('.',1)[0]))
        para=doc.add_paragraph(style='List Number'); text_runs(para,re.sub(r'^\d+\. ','',line))
        np=OxmlElement('w:numPr'); il=OxmlElement('w:ilvl'); il.set(qn('w:val'),'0'); np.append(il)
        ni=OxmlElement('w:numId'); ni.set(qn('w:val'),str(list_id)); np.append(ni); para._p.get_or_add_pPr().append(np)
    else:
        para=doc.add_paragraph(); text_runs(para,line)
    if page_break:
        para.paragraph_format.page_break_before=True; page_break=False
OUTPUT.parent.mkdir(parents=True,exist_ok=True); doc.save(OUTPUT)
print(OUTPUT)
print('Bloques de lectura:',SOURCE.read_text(encoding='utf-8').count('<!-- PAGE -->')+1)
