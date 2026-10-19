"""Shared presentation contract derived from the retained user-supplied brief."""
from datetime import date
from pathlib import Path
from zipfile import ZipFile
from comparison_metrics import compare_group,rate_text
from activity_indicators import activity_group
from lxml import etree

TEMPLATE=Path(__file__).parent/'templates'/'brief_treatment.docx'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'

def replace_text(p,old,new):
    nodes=p.findall('.//w:t',NS);text=''.join(n.text or '' for n in nodes)
    start=text.index(old);replace_range(p,start,start+len(old),new)

def replace_range(p,start,end,new):
    nodes=p.findall('.//w:t',NS);offset=0;inserted=False
    for n in nodes:
        t=n.text or '';right=offset+len(t)
        if right>start and offset<end:
            lo=max(0,start-offset);hi=min(len(t),end-offset)
            n.text=t[:lo]+(str(new) if not inserted else '')+t[hi:];inserted=True
            n.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
        offset=right

def formatted(v,rate=False):
    return 'N/A' if v is None else f'{v:.0f}%' if rate else f'{v:,}'

def template_xml(report):
    with ZipFile(TEMPLATE) as z:root=etree.fromstring(z.read('word/document.xml'))
    body=root.find('w:body',NS);a=report['groups']['all'];c=report['groups']['paediatrics'];end=date.fromisoformat(report['end_date'])
    fy=end.year+(end.month>=10);q=((end.month+2)%12)//3+1
    overall_comparison=compare_group(report);paediatric_comparison=compare_group(report,paediatric=True)
    overall_activity=activity_group(report);child_activity=activity_group(report,paediatric=True)
    suffix='TH' if 10<end.day%100<14 else {1:'ST',2:'ND',3:'RD'}.get(end.day%10,'TH')
    replacements={0:[('@19','@'+str(end.day)),('TH',suffix),('September',end.strftime('%B')),('2026',str(end.year))],
      6:[('76',formatted(child_activity['txnew']))],7:[('3192',formatted(c['txcurr']))],
      8:[('FY26-Q4',f'FY{str(fy)[-2:]}-Q{q}'),('97.8%',rate_text(paediatric_comparison['retention_rate'])),('-45',formatted(paediatric_comparison['netnew']))],
      9:[('FY26Q4',f'FY{str(fy)[-2:]}Q{q}'),('September',end.strftime('%B')),('73','N/A'),('2.2','N/A')],
      10:[('94%',formatted(c['coverage'],True)),('90%',formatted(c['suppression_rate'],True))],
      13:[('1085',formatted(overall_activity['txnew'])),('FY26 Q4',f'FY{str(fy)[-2:]} Q{q}')],
      15:[('99%',rate_text(overall_comparison['retention_rate'])),('a positive','a reported'),('-22',formatted(overall_comparison['netnew']))],
      16:[('FY26',f'FY{str(fy)[-2:]}'),('1,386','N/A'),('FY26Q4',f'FY{str(fy)[-2:]}Q{q}'),('1.52','N/A')],
      21:[('83,225',formatted(a['result'])),('81,119',formatted(a['vl_suppression'])),('95%',formatted(a['coverage'],True)),('98%',formatted(a['suppression_rate'],True))],
      22:[('90%',formatted(a['undetectable_rate'],True)),('75,105',formatted(a['undetectable']))],
      23:[('2,026',formatted(a['unsuppressed'])),('6,094',formatted(a['llv']))]}
    activity_end=date.fromisoformat(report.get('activity',{}).get('end_date',report['end_date']))
    activity_fy=activity_end.year+(activity_end.month>=10);activity_q=((activity_end.month+2)%12)//3+1
    if report.get('activity'):
        replacements[6]=[('so far this quarter','for the selected activity period'),('76',formatted(child_activity['txnew']))]
        replacements[8][0]=('FY26-Q4',f'FY{str(activity_fy)[-2:]}-Q{activity_q}')
        replacements[9][0]=('FY26Q4',f'FY{str(activity_fy)[-2:]}Q{activity_q}')
        replacements[9][1]=('September',activity_end.strftime('%B'))
        replacements[13][1]=('FY26 Q4',f'FY{str(activity_fy)[-2:]} Q{activity_q}')
    # Replace year/quarter phrases before standalone fiscal-year tokens.
    replacements[16]=[(f'FY26Q4',f'FY{str(fy)[-2:]}Q{q}'),('In summary for FY26',f'In summary for FY{str(fy)[-2:]}'),('1,386','N/A'),('1.52','N/A')]
    for index,pairs in replacements.items():
        original=''.join(body[index].xpath('.//w:t/text()',namespaces=NS))
        edits=[(original.index(old),original.index(old)+len(old),new) for old,new in pairs]
        for start,stop,new in sorted(edits,reverse=True):replace_range(body[index],start,stop,new)
    p=body[14];nodes=p.findall('.//w:t',NS)
    for node in nodes:node.text=''
    nodes[0].text=f"Tx Curr as at last week is {formatted(a['txcurr'])}. Prior-week comparison is N/A."
    if report.get('workflow')=='quarterly':
        for paragraph in body.findall('w:p',NS):
            for node in paragraph.findall('.//w:t',NS):
                if node.text:node.text=node.text.replace('last week', 'the selected quarter').replace('Prior-week comparison', 'Prior-quarter comparison')
    return root

def table_models(report):
    end=date.fromisoformat(report['end_date']);fy=end.year+(end.month>=10);q=((end.month+2)%12)//3+1
    keys=['txcurr','eligible','sample_collected','result','vl_suppression','undetectable','llv','coverage','suppression_rate','undetectable_rate','llv_rate','unsuppressed']
    names=['State','TxCurr','Eligible','Sample','Result','Suppression','Undetectable','LLV','Coverage','Suppression Rate','Undetectable Rate','LLV Rate','Unsuppressed']
    row=lambda name,g:[name]+[formatted(g[k],k.endswith('_rate') or k=='coverage') for k in keys]
    main={'kind':'viral','title':f'Viral Load Cascade - FY{str(fy)[-2:]}Q{q} as @ {end.day}{"th" if 10<end.day%100<14 else {1:"st",2:"nd",3:"rd"}.get(end.day%10,"th")} {end:%B %Y}',
          'headers':names,'rows':[row(n,g) for n,g in report.get('states',{}).items()]+[row('ECEWS',report['groups']['all'])]}
    comparison=report.get('comparison')
    comparison_label=('TxCurr-'+comparison['source']['period']) if comparison else f'TxCurr-Q{4 if q==1 else q-1}'
    treatment_headers=['State',comparison_label,f'TxCurr-Q{q}','Txnew','TransIn','RTT','IIT','IIT Rate','COT/Retention rate','NetNew','Dead','Stopped','TransOut']
    def treatment(states,total,kind):
        def baseline(name):
            if not comparison:return 'N/A'
            pediatric=kind=='paediatric-treatment'
            if name=='ECEWS':group=comparison['groups']['paediatrics' if pediatric else 'all']
            elif pediatric:group=comparison.get('paediatric_states',{}).get(name,{}).get('total')
            else:group=comparison.get('states',{}).get(name)
            return formatted(group['txcurr']) if group is not None else 'N/A'
        rows=[]
        for n,g in [*states,('ECEWS',total)]:
            metrics=compare_group(report,n,paediatric=kind=='paediatric-treatment')
            events=activity_group(report,n,paediatric=kind=='paediatric-treatment')
            rows.append([n,baseline(n),formatted(g['txcurr']),formatted(events['txnew']),formatted(events['transferred_in']),formatted(events['rtt']),'N/A','N/A',rate_text(metrics['retention_rate']),formatted(metrics['netnew']),formatted(events['death']),formatted(events['stopped']),formatted(events['transferred_out'])])
        return {'kind':kind,'headers':treatment_headers,'rows':rows}
    pediatric=report.get('paediatric_states',{})
    pk=['txcurr','eligible','sample_collected','sample_collection_rate','result','vl_suppression','undetectable','llv','coverage','suppression_rate','llv_rate','undetectable_rate']
    ph=['State','Age_Band','TxCurr','Eligible','Sample Collected','Sample collection Rate','VL Result','Suppression','Undetectable','LLV','Coverage','Suppression Rate','LLV Rate','Undetectable rate']
    pr=[]
    for state,g in pediatric.items():
        pr.append({'kind':'header','cells':ph})
        for band,v in g['bands'].items():pr.append({'kind':'data','cells':[state,band]+[formatted(v[k],k.endswith('_rate') or k=='coverage') for k in pk]})
        pr.append({'kind':'subtotal','cells':['Sub-Total','']+[formatted(g['total'][k],k.endswith('_rate') or k=='coverage') for k in pk]})
    g=report['groups']['paediatrics'];pr.append({'kind':'total','cells':['ECEWS-Total','']+[formatted(g[k],k.endswith('_rate') or k=='coverage') for k in pk]})
    return [main,treatment(list(report.get('states',{}).items()),report['groups']['all'],'treatment'),
            {'kind':'paediatric','title':'Paediatric Viral load Cascade by State','headers':ph,'structured_rows':pr},
            treatment([(n,g['total']) for n,g in pediatric.items()],g,'paediatric-treatment')]

def brief_view(report):
    root=template_xml(report);paras=[]
    for i,p in enumerate(root.find('w:body',NS)):
        if not p.findall('.//w:t',NS):continue
        runs=[]
        for run in p.findall('w:r',NS):
            text=''.join(run.xpath('.//w:t/text()',namespaces=NS))
            if not text:continue
            color=run.find('w:rPr/w:color',NS);sup=run.find('w:rPr/w:vertAlign',NS)
            runs.append({'text':text,'bold':run.find('w:rPr/w:b',NS) is not None,'color':color.get(W+'val') if color is not None else '002060','superscript':sup is not None and sup.get(W+'val')=='superscript'})
        paras.append({'index':i,'runs':runs,'bullet':i in [6,7,8,9,10,13,14,15,16,21,22,23]})
    return {'header':('Quarterly' if report.get('workflow')=='quarterly' else 'Weekly')+' Treatment Program Situation Analysis','paragraphs':paras,'tables':table_models(report)}
