"""Green Word summary for the processed HTS TXNEW monitoring dataset."""
from io import BytesIO
from math import ceil
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

DARK='145C43';MID='287D59';PALE='EAF5EC'
def rate(value):return 'N/A' if value is None else f'{value:.1f}%'
def shade(cell,color):
 props=cell._tc.get_or_add_tcPr();fill=OxmlElement('w:shd');fill.set(qn('w:fill'),color);props.append(fill)
 margins=OxmlElement('w:tcMar')
 for edge in ('top','left','bottom','right'):
  node=OxmlElement('w:'+edge);node.set(qn('w:w'),'110');node.set(qn('w:type'),'dxa');margins.append(node)
 props.append(margins)
def unique_rankings(rows,best=True):
    eligible=[r for r in rows if r['hts_pos']>0 and r['unique_linkage'] is not None]
    return sorted(eligible,key=lambda r:((-r['unique_linkage'] if best else r['unique_linkage']),-r['hts_pos'],r['facility'].casefold(),r['lga'].casefold()))[:5]

def performance_paragraphs(g,name):
    share=lambda numerator,denominator:rate(100*numerator/denominator if denominator else None)
    return [
      f"During the uploaded reporting period, {name} identified {g['hts_pos']:,} HTS_POS clients and reported {g['txnew']:,} clients linked to treatment (TX_NEW), representing {share(g['txnew'],g['hts_pos'])} total linkage. Of these, {g['unique']:,} were reported as unique TX_NEW, equivalent to {share(g['unique'],g['hts_pos'])} unique linkage against HTS_POS.",
      f"Among the {g['txnew']:,} newly initiated clients reported, {g['prints']:,} have Print capture ({share(g['prints'],g['txnew'])} of total TX_NEW), while {g['no_prints']:,} have No Print ({share(g['no_prints'],g['txnew'])} of total TX_NEW). The dataset also reports {g['non_unique']:,} non-unique TX_NEW records, equivalent to {share(g['non_unique'],g['txnew'])} of total TX_NEW and {share(g['non_unique'],g['prints'])} relative to Print capture. These figures highlight the need to review capture completion and uniqueness alongside linkage."
    ]

def build(report,source):
 doc=Document();section=doc.sections[0];section.page_width=Inches(8.5);section.page_height=Inches(11);section.top_margin=section.bottom_margin=Inches(.65);section.left_margin=section.right_margin=Inches(.65)
 
 for style in doc.styles:
  for border in list(style.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
 normal=doc.styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(11);normal.paragraph_format.space_after=Pt(8)
 for style in ('Heading 1','Heading 2'):
  doc.styles[style].font.color.rgb=RGBColor.from_string(DARK)
  doc.styles[style].font.size=Pt(17 if style=='Heading 1' else 13)
 doc.styles['Title'].font.color.rgb=RGBColor(0,0,0);doc.styles['Title'].font.size=Pt(26)
 section.header.paragraphs[0].text='ECEWS  /  SPEED                                     PROGRAMME PERFORMANCE'
 section.header.paragraphs[0].runs[0].font.size=Pt(9);section.header.paragraphs[0].runs[0].font.color.rgb=RGBColor.from_string(MID)
 t=report['total'];states=report['states'];facilities=report['facilities']
 doc.add_paragraph('HTS TXNEW Monitoring Report','Title')
 p=doc.add_paragraph('ECEWS overall achievement and state performance');p.runs[0].font.color.rgb=RGBColor.from_string(MID)
 doc.add_paragraph('Source: '+source)
 doc.add_paragraph(f"The processed dataset covers {len(facilities):,} facilities across {len(states)} states. Overall TX_NEW linkage is {rate(t['linkage'])}, while unique linkage is {rate(t['unique_linkage'])}, against the 98% monitoring target.")
 doc.add_heading('ECEWS overall achievement',1)
 cards=doc.add_table(rows=5,cols=5);cards.autofit=False
 for column,width in zip(cards.columns,[2.26,.21,2.26,.21,2.26]):column.width=Inches(width)
 for index,row in enumerate(cards.rows):
  for cell,width in zip(row.cells,[2.26,.21,2.26,.21,2.26]):
   cell.width=Inches(width)
   if index%2 or width<1:
    p=cell.paragraphs[0];p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0);p.paragraph_format.line_spacing=Pt(1);p.add_run(' ').font.size=Pt(1)
  if index%2:row.height=Inches(.1)
 items=[('HTS positive',f"{t['hts_pos']:,}"),('Total TX_NEW',f"{t['txnew']:,}"),('Unique TX_NEW',f"{t['unique']:,}"),('TX_NEW linkage',rate(t['linkage'])),('Unique linkage',rate(t['unique_linkage'])),('Non unique TX_NEW',f"{t['non_unique']:,}"),('Print capture',f"{t['prints']:,}"),('No Print',f"{t['no_prints']:,}"),('Facilities reporting',f"{len(facilities):,}")]
 for i,(label,value) in enumerate(items):
  cell=cards.cell((i//3)*2,(i%3)*2);shade(cell,'FFFFFF')
  borders=OxmlElement('w:tcBorders')
  for edge in ('top','left','bottom','right'):
   border=OxmlElement('w:'+edge);border.set(qn('w:val'),'single');border.set(qn('w:sz'),'22' if edge=='top' else '5');border.set(qn('w:color'),'238C80' if edge=='top' else 'DCE6E8');borders.append(border)
  cell._tc.get_or_add_tcPr().append(borders)
  p=cell.paragraphs[0];p.paragraph_format.space_after=Pt(5);r=p.add_run(label);r.font.size=Pt(10);r.font.color.rgb=RGBColor.from_string(MID)
  p=cell.add_paragraph();p.paragraph_format.space_after=Pt(4);r=p.add_run(value);r.bold=True;r.font.size=Pt(24);r.font.color.rgb=RGBColor.from_string(DARK)
  p=cell.add_paragraph('Denominator: HTS positive' if 'linkage' in label.lower() else 'Across all states');p.paragraph_format.space_after=Pt(2);p.runs[0].font.size=Pt(8);p.runs[0].font.color.rgb=RGBColor.from_string(MID)
 doc.add_heading('State level summary',1)
 table=doc.add_table(rows=1,cols=9);table.autofit=False
 headers=['State','HTS positive','Total TX_NEW','Unique TX_NEW','Total linkage','Unique linkage','Print capture','No Print','Non unique TX_NEW']
 for cell,label in zip(table.rows[0].cells,headers):
  shade(cell,DARK);r=cell.paragraphs[0].add_run(label);r.bold=True;r.font.size=Pt(9);r.font.color.rgb=RGBColor(255,255,255)
 repeat=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(repeat)
 for i,g in enumerate([*states,dict(state='ECEWS total',**t)]):
  cells=table.add_row().cells
  values=[g['state'],str(g['hts_pos']),str(g['txnew']),str(g['unique']),rate(g['linkage']),rate(g['unique_linkage']),str(g['prints']),str(g['no_prints']),str(g['non_unique'])]
  for j,(cell,value) in enumerate(zip(cells,values)):
   shade(cell,'D4EBD8' if i==len(states) else PALE if i%2==0 else 'FFFFFF');r=cell.paragraphs[0].add_run(value);r.font.size=Pt(9);r.bold=i==len(states)
   if j>=4:r.font.color.rgb=RGBColor.from_string(DARK)
 doc.add_paragraph('Rates use summed counts, not averages of facility rates. N/A indicates zero HTS positives. Rates are not capped at 100%.').runs[0].font.size=Pt(9)
 doc.add_heading('FY27 HTS Linkage and PBS Performance Update',1).paragraph_format.page_break_before=True
 doc.add_paragraph('Reporting scope: '+source+'. Figures describe the uploaded dataset only. FY27 to date or quarterly achievement can be stated only when that full period is included in the source.').runs[0].font.size=Pt(10)
 doc.add_heading('ECEWS programme summary',2)
 for text in performance_paragraphs(t,'ECEWS'):doc.add_paragraph(text)
 doc.add_heading('Key Observation and Action Required',2)
 doc.add_paragraph('Beyond achieving HTS to treatment linkage, emphasis should be placed on ensuring that every newly identified and linked client has a valid and unique PBS record. State teams should strengthen PBS capture at the point of treatment initiation, review non unique records, and ensure that identified clients are appropriately captured and deduplicated.')
 doc.add_paragraph(f"Programme follow up should address the {t['no_prints']:,} reported No Print records and review the {t['non_unique']:,} reported non unique records. The categories may overlap and must not be added together as a count of distinct clients. Validate and reconcile records before assigning causes or confirming individual linkage gaps.")
 doc.add_heading('Calculation notes',2)
 doc.add_paragraph('Total linkage = total TX_NEW / HTS_POS × 100. Unique linkage = unique TX_NEW / HTS_POS × 100. Print capture and No Print shares use total TX_NEW. Non unique shares use the denominator stated in the text. The comparison with captured prints is an aggregate ratio; the file does not establish matched records or prove that all non unique records are a subset of captured prints. N/A indicates a zero denominator. Values are not capped at 100%; investigate mismatched periods or counts when ratios exceed 100%. The linkage target is 98%.').runs[0].font.size=Pt(9)
 doc.add_heading('State level performance summaries',1).paragraph_format.page_break_before=True
 for state in states:
  doc.add_heading(state['state'],2)
  for text in performance_paragraphs(state,state['state']):doc.add_paragraph(text)
  action=('Sustain linkage performance and complete record validation.' if state['unique_linkage'] is not None and state['unique_linkage']>=98 else 'Prioritise linkage follow up and reconcile HTS and treatment records against the 98% target.' if state['unique_linkage'] is not None else 'Verify HTS positive reporting before assessing linkage performance.')
  doc.add_paragraph(f"Action required: {action} Review {state['no_prints']:,} No Print records for capture completion and {state['non_unique']:,} non unique records for validation and deduplication.")
 doc.add_heading('Conclusive remark',1)
 doc.add_paragraph(f"ECEWS achieved {rate(t['linkage'])} total linkage and {rate(t['unique_linkage'])} unique linkage in the uploaded reporting period. State teams should close confirmed linkage gaps, complete missing Print capture, and resolve non unique records through validation and deduplication. This will strengthen client identification, data integrity and the reliability of programme reporting. Subsequent reviews should verify completion against this dataset rather than infer improvement without comparable evidence.")
 for state in states:
  doc.add_heading(state['state']+' facility uniqueness rankings',1).paragraph_format.page_break_before=True
  rows=[g for g in facilities if g['state']==state['state']]
  eligible=sum(g['hts_pos']>0 for g in rows)
  doc.add_paragraph(f"Ranked by unique linkage: unique TX_NEW / HTS positive × 100. {eligible} facilities have a positive denominator. Facilities with zero HTS positives are excluded. Ties use higher HTS positive volume, then facility and LGA names. Lists may overlap when few facilities qualify.").runs[0].font.size=Pt(10)
  for best,title in [(True,'Top 5 best facilities'),(False,'Top 5 worst facilities')]:
   doc.add_heading(title,2);ranked=unique_rankings(rows,best)
   if not ranked:
    doc.add_paragraph('No facilities with HTS positives are available for ranking.');continue
   tab=doc.add_table(rows=1,cols=6);tab.autofit=False
   widths=[.42,2.62,1.28,.8,.95,1.13]
   for column,width in zip(tab.columns,widths):column.width=Inches(width)
   for cell,width,label in zip(tab.rows[0].cells,widths,['Rank','Facility','LGA','HTS positive','Unique TX_NEW','Unique linkage']):
    cell.width=Inches(width);shade(cell,DARK);run=cell.paragraphs[0].add_run(label);run.bold=True;run.font.size=Pt(9);run.font.color.rgb=RGBColor(255,255,255)
   repeat=OxmlElement('w:tblHeader');tab.rows[0]._tr.get_or_add_trPr().append(repeat)
   for index,g in enumerate(ranked,1):
    cells=tab.add_row().cells
    no_split=OxmlElement('w:cantSplit');cells[0]._tc.getparent().get_or_add_trPr().append(no_split)
    for j,(cell,width,value) in enumerate(zip(cells,widths,[str(index),g['facility'],g['lga'],str(g['hts_pos']),str(g['unique']),rate(g['unique_linkage'])])):
     cell.width=Inches(width);shade(cell,PALE if index%2 else 'FFFFFF');run=cell.paragraphs[0].add_run(value);run.font.size=Pt(9)
     if j==5:run.bold=True;run.font.color.rgb=RGBColor.from_string(DARK if g['unique_linkage']>=98 else 'A22E2E')
   doc.add_paragraph('Green linkage meets 98%; red linkage is below 98%.').runs[0].font.size=Pt(9)
 section.footer.paragraphs[0].text='ECEWS  |  HTS TXNEW monitoring  |  Source based management summary'
 section.footer.paragraphs[0].runs[0].font.size=Pt(9)
 out=BytesIO();doc.save(out);return out.getvalue()
