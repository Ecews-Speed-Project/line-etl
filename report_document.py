"""Populate the user's retained Word package without rebuilding its layout."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree
from PIL import Image,ImageDraw,ImageFont
from report_template import TEMPLATE,template_xml,table_models,NS,W


def font(size,bold=False,italic=False):
    candidates=[Path('C:/Windows/Fonts')/('calibriz.ttf' if bold and italic else 'calibrib.ttf' if bold else 'calibrii.ttf' if italic else 'calibri.ttf'),
      Path('/usr/share/fonts/truetype/crosextra')/('Carlito-Bold.ttf' if bold else 'Carlito-Regular.ttf'),
      Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
    for candidate in candidates:
        if candidate.exists():return ImageFont.truetype(str(candidate),size)
    return ImageFont.load_default(size=size)


def render_table(model,ratio):
    width=2600;kind=model['kind'];cols=len(model['headers'])
    if kind=='paediatric':rows=model['structured_rows'];weights=[200]+[145 if r['kind']=='header' else 45 for r in rows]
    else:
        rows=[{'kind':'header','cells':model['headers']}]+[{'kind':'data','cells':r} for r in model['rows']]
        weights=([50] if model.get('title') else [])+[210 if kind=='viral' else 115]+[160 if kind=='viral' and i==0 else 54 for i in range(len(model['rows']))]
    height=round(width*ratio);image=Image.new('RGB',(width,height),'white');draw=ImageDraw.Draw(image);scale=height/sum(weights);pos=0
    def centered(text,rect,bold=False,italic=False):
        x0,y0,x1,y1=rect;size=31 if kind=='paediatric' else 32
        f=font(size,bold,italic);words=str(text).replace('TxCurr-FY','TxCurr- FY').split();lines=[];line=''
        for word in words:
            trial=(line+' '+word).strip()
            if draw.textlength(trial,font=f)>x1-x0-12 and line:lines.append(line);line=word
            else:line=trial
        lines.append(line);line_height=size*1.1
        while (len(lines)*line_height>y1-y0-4 or max(draw.textlength(t,font=f) for t in lines)>x1-x0-8) and size>17:
            size-=1;f=font(size,bold,italic);line_height=size*1.1
        top=y0+(y1-y0-len(lines)*line_height)/2
        for line in lines:
            draw.text(((x0+x1-draw.textlength(line,font=f))/2,top),line,font=f,fill='black');top+=line_height
    weight_index=0
    if model.get('title'):
        h=weights[0]*scale;draw.rectangle((0,0,width-1,h),fill='#dceaf5' if kind=='viral' else '#a6c9eb',outline='black',width=2)
        centered(model['title'],(0,h-50 if kind=='paediatric' else 0,width,h));pos=h;weight_index=1
    for i,row in enumerate(rows):
        h=weights[i+weight_index]*scale;y1=pos+h
        for j,text in enumerate(row['cells']):
            x0=round(j*width/cols);x1=round((j+1)*width/cols)
            fill='white'
            if kind=='viral':fill='#b6e3a3' if j==cols-1 else '#efceed' if row['kind']=='header' else 'white'
            if kind=='paediatric':fill='#92d050' if row['kind']=='header' else '#a6c9eb' if row['kind']=='total' else 'white'
            if kind=='treatment' and j>=7:fill='#a6c9eb' if j<10 else '#e0f0d4'
            if kind=='paediatric-treatment' and j>=7:fill='#fce4d6' if j<10 else '#efceed'
            draw.rectangle((x0,pos,min(x1,width-1),min(y1,height-1)),fill=fill,outline='black',width=2)
            centered(text,(x0,pos,x1,y1),row['kind']=='total',kind=='viral' and row['kind']=='header')
        pos=y1
    out=BytesIO();image.save(out,format='PNG');return out.getvalue()


def build(report):
    root=template_xml(report);models=table_models(report)
    with ZipFile(TEMPLATE) as original:
        relationships=etree.fromstring(original.read('word/_rels/document.xml.rels'));types=etree.fromstring(original.read('[Content_Types].xml'))
        changes={};removed=set()
        if report.get('workflow')=='quarterly':
            changes['word/header1.xml']=original.read('word/header1.xml').replace(b'Weekly',b'Quarterly')
        ratios=[1391166/5943600,768256/5943600,3661934/5943600,768256/5943600]
        for i,model in enumerate(models,1):
            if model['kind']=='paediatric':
                natural=200+sum(145 if r['kind']=='header' else 45 for r in model['structured_rows']);baseline=1490
            else:
                natural=(260 if model['kind']=='viral' else 115)+sum(160 if model['kind']=='viral' and j==0 else 54 for j in range(len(model['rows'])))
                baseline=582 if model['kind']=='viral' else 331
            ratio=ratios[i-1]*max(1,natural/baseline)
            if ratio!=ratios[i-1]:
                paragraph=root.find('w:body',NS)[[17,18,24,25][i-1]]
                for ext in paragraph.xpath('.//wp:extent | .//a:xfrm/a:ext',namespaces={'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}):
                    ext.set('cy',str(round(5943600*ratio)))
            name=f'word/media/image{i}.png';changes[name]=render_table(model,ratio)
            for rel in relationships:
                if rel.get('Target')==f'media/image{i}.emf':removed.add('word/'+rel.get('Target'));rel.set('Target',f'media/image{i}.png')
        if not any(e.get('Extension')=='png' for e in types):
            e=etree.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Default');e.set('Extension','png');e.set('ContentType','image/png')
        body=root.find('w:body',NS);p=etree.Element(W+'p');body.insert(len(body)-1,p);run=etree.SubElement(p,W+'r');props=etree.SubElement(run,W+'rPr');size=etree.SubElement(props,W+'sz');size.set(W+'val','15');text=etree.SubElement(run,W+'t')
        source=report['source'];text.text=f"Source: {source['file']} | Period: {source['period'] or 'Unassigned'}. Window: {report['start_date']} to {report['end_date']}. Status and ages use the selected snapshot. N/A: unavailable treatment definitions or comparison data."
        if report.get('comparison'):
            source=report['comparison']['source'];text.text+=' Quarter comparison: '+source['period']+' | '+source['file']+' | '+source['sheet']+'.'
            text.text+=' NetNew = weekly TxCurr - quarter TxCurr. CoT/retention = weekly TxCurr / quarter TxCurr x 100 (snapshot ratio, not client-cohort retention; zero baseline is N/A).'
        if report.get('activity'):
            a=report['activity'];text.text+=' Activity window: '+a['start_date']+' to '+a['end_date']+'. TxNew excludes TI=NO. Stopped uses Discontinued care; transferred out uses Transferred out. RTT excludes blank, unmatched and ambiguous previous statuses.'
        for path,xml in [('word/document.xml',root),('word/_rels/document.xml.rels',relationships),('[Content_Types].xml',types)]:changes[path]=etree.tostring(xml,xml_declaration=True,encoding='UTF-8',standalone=True)
        out=BytesIO()
        with ZipFile(out,'w',ZIP_DEFLATED) as result:
            for item in original.infolist():
                if item.filename not in removed:result.writestr(item,changes.pop(item.filename,original.read(item.filename)))
            for name,data in changes.items():result.writestr(name,data)
    return out.getvalue()
