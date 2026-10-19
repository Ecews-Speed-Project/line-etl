const treatmentApiPrefix=document.body.dataset.apiPrefix||'';
const reportSelector=document.getElementById('report-snapshot'),reportStatus=document.getElementById('treatment-status');
const reportEl=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
window.populateTreatmentSnapshots=items=>{
 reportSelector.replaceChildren();const first=reportEl('option','Choose one linelist');first.value='';reportSelector.append(first);
 for(const item of items){const option=reportEl('option',(item.period||'Unassigned period')+' · '+item.file+' · '+item.sheet+' · '+Number(item.rows).toLocaleString()+' rows');option.value=JSON.stringify({id:item.id,sheet:item.sheet,period:item.period,period_end:item.period_end});reportSelector.append(option);}
 reportSelector.disabled=false;document.getElementById('calculate-treatment').disabled=false;document.getElementById('download-treatment').disabled=false;document.getElementById('treatment-results').replaceChildren();
};
function briefTable(model){
 const wrap=reportEl('div');wrap.className='brief-table-wrap';const table=reportEl('table');table.className='brief-table '+model.kind;table.setAttribute('aria-label',model.title||model.kind+' summary');
 const count=model.headers.length;
 if(model.title){const row=reportEl('tr'),cell=reportEl('th',model.title);cell.colSpan=count;row.className='brief-band';row.append(cell);table.append(row);}
 const add=(cells,kind)=>{const row=reportEl('tr');row.className='brief-row-'+kind;cells.forEach((text,i)=>{const cell=reportEl(kind==='header'?'th':'td',text);if(kind==='header')cell.scope='col';if(i===count-1)cell.classList.add('last-column');row.append(cell);});table.append(row);};
 if(model.structured_rows)model.structured_rows.forEach(r=>add(r.cells,r.kind));else{add(model.headers,'header');model.rows.forEach(r=>add(r,'data'));}
 wrap.append(table);return wrap;
}
function renderBrief(report,box){
 box.replaceChildren();if(report.activity){const panel=reportEl('div');panel.className='scroll';panel.append(reportEl('h3','Treatment activity · '+report.activity.start_date+' to '+report.activity.end_date));panel.append(reportEl('p','IIT period: '+report.activity.iit_start_date+' to '+report.activity.iit_end_date));const table=reportEl('table'),head=reportEl('tr');['Indicator','All clients','0–19 years','20+ years','Unknown age'].forEach(t=>head.append(reportEl('th',t)));table.append(head);for(const [key,label] of Object.entries({txnew:'TxNew',transferred_in:'Transferred in',death:'Death',rtt:'RTT',stopped:'Stopped',transferred_out:'Transferred out',iit:'IIT'})){const tr=reportEl('tr');tr.append(reportEl('td',label));for(const name of ['all','paediatrics','adults','unknown_age']){const value=report.activity.groups[name][key];tr.append(reportEl('td',value===null?'N/A':Number(value).toLocaleString()));}table.append(tr);}panel.append(table);box.append(panel);}const wrapper=reportEl('div');wrapper.className='brief-scroll';const paper=reportEl('article');paper.className='brief-document';
 const p1=reportEl('div'),p2=reportEl('div');p1.className=p2.className='brief-page';const heading=reportEl('div',report.brief.header);heading.className='brief-running-header';p1.append(heading);
 const paragraphs=new Map(report.brief.paragraphs.map(p=>[p.index,p]));
 const add=(page,index)=>{const source=paragraphs.get(index);if(!source)return;const p=reportEl('p');p.className='brief-p brief-p-'+index+(source.bullet?' brief-bullet':'');for(const r of source.runs){const span=reportEl(r.superscript?'sup':'span',r.text);if(r.bold)span.style.fontWeight='700';if(/^[0-9a-fA-F]{6}$/.test(r.color))span.style.color='#'+r.color;p.append(span);}page.append(p);};
 [0,1,3,5,6,7,8,9,10,12,13,14,15,16].forEach(i=>add(p1,i));p1.append(briefTable(report.brief.tables[0]),briefTable(report.brief.tables[1]));[20,21,22].forEach(i=>add(p1,i));
 add(p2,23);p2.append(briefTable(report.brief.tables[2]),briefTable(report.brief.tables[3]));paper.append(p1,p2);wrapper.append(paper);box.append(wrapper);
 const details=reportEl('details');details.className='brief-methods';details.append(reportEl('summary','Source, definitions and data quality'));details.append(reportEl('p',report.source.file+' · Period '+(report.source.period||'Unassigned')+' · Window '+report.start_date+' to '+report.end_date));
 if(report.activity)details.append(reportEl('p','IIT rows excluded for invalid/missing pickup or refill inputs: '+report.activity.quality.iit_missing_or_invalid_inputs+'. RTT data quality: '+report.activity.quality.rtt_unmatched_active+' unmatched Active rows; '+report.activity.quality.rtt_ambiguous_active+' ambiguous Active rows excluded. Invalid dates: ART '+report.activity.quality.invalid_art_dates+', transfer '+report.activity.quality.invalid_transfer_dates+', outcome '+report.activity.quality.invalid_outcome_dates+'.'));
 if(report.comparison)details.append(reportEl('p','Quarter comparison: '+report.comparison.source.period+' · '+report.comparison.source.file+' · '+report.comparison.source.sheet));
 details.append(reportEl('p','N/A means treatment definitions or comparison data are unavailable. Status and ages reflect the selected snapshot. The date filter does not reconstruct historical status.'));
 for(const text of report.definitions)details.append(reportEl('p',text));details.append(reportEl('p','Active records with unknown age: '+report.quality.active_unknown_age+'. Eligible records with missing or invalid VL: '+report.quality.eligible_missing_or_invalid_vl+'.'));box.append(details);
}
async function calculateTreatment(word){
 const form=document.getElementById('dashboard-form');if(!form.reportValidity())return;
 if(!reportSelector.value){reportStatus.textContent='Choose one uploaded linelist first.';return;}
 const end=document.getElementById('report-end');if(!end.reportValidity())return;const activityStart=document.getElementById('activity-start'),activityEnd=document.getElementById('activity-end');if(!activityStart.reportValidity()||!activityEnd.reportValidity())return;if(activityStart.value>activityEnd.value){reportStatus.textContent='Activity start date must be on or before its end date.';return;}
 const iitStart=document.getElementById('iit-start'),iitEnd=document.getElementById('iit-end');if(!iitStart.reportValidity()||!iitEnd.reportValidity())return;if(iitStart.value>iitEnd.value){reportStatus.textContent='IIT start date must be on or before its end date.';return;}
 const buttons=[document.getElementById('calculate-treatment'),document.getElementById('download-treatment')];buttons.forEach(b=>b.disabled=true);let tracker,success=false;
 try{
  const selected=JSON.parse(reportSelector.value),data=new FormData(form);data.set('snapshot_id',selected.id);data.set('sheet',selected.sheet);data.set('end_date',end.value);data.set('word',String(word));data.set('activity_start_date',activityStart.value);data.set('activity_end_date',activityEnd.value);data.set('iit_start_date',iitStart.value);data.set('iit_end_date',iitEnd.value);if(!treatmentApiPrefix&&comparisonSelector.value){const comparison=JSON.parse(comparisonSelector.value);data.set('comparison_snapshot_id',comparison.id);data.set('comparison_sheet',comparison.sheet);}tracker=await DatabaseProgress.start('report',reportStatus);data.set('progress_id',tracker.id);reportStatus.textContent=word?'Preparing Word report…':'Calculating indicators…';
  const response=await fetch(treatmentApiPrefix+'/api/treatment-report',{method:'POST',body:data});if(!response.ok){const body=await response.json();throw new Error(typeof body.detail==='string'?body.detail:'Check the reporting fields.');}
  if(word){const url=URL.createObjectURL(await response.blob()),link=reportEl('a');link.href=url;link.download=(treatmentApiPrefix?'quarterly_':'')+'treatment_report_'+end.value+'.docx';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);reportStatus.textContent='Word report downloaded.';}
  else{renderBrief(await response.json(),document.getElementById('treatment-results'));reportStatus.textContent='Report ready. Word export follows the supplied brief template.';}
  success=true;
 }catch(error){reportStatus.textContent=error.message;}finally{if(tracker)await tracker.finish(success);buttons.forEach(b=>b.disabled=false);}
}
document.getElementById('calculate-treatment').onclick=()=>calculateTreatment(false);document.getElementById('download-treatment').onclick=()=>calculateTreatment(true);

if(treatmentApiPrefix)reportSelector.addEventListener('change',()=>{if(reportSelector.value){const period=JSON.parse(reportSelector.value).period_end;if(period)document.getElementById('report-end').value=period;}});

const comparisonSelector=document.getElementById('report-comparison'),comparisonStatus=document.getElementById('comparison-status');
if(treatmentApiPrefix)document.getElementById('quarter-comparison-controls').hidden=true;
window.loadQuarterlyComparisons=async form=>{
 if(treatmentApiPrefix)return;
 comparisonSelector.disabled=true;comparisonSelector.replaceChildren(reportEl('option','No quarterly comparison'));
 try{
  const data=new FormData(form);data.set('schema','quarterly');data.set('source_table','linelist_records');data.delete('period');
  const response=await fetch('/quarterly/api/dashboard',{method:'POST',body:data});if(!response.ok)throw new Error('Could not load quarterly linelists. Check the quarterly dashboard.');
  const result=await response.json();comparisonSelector.options[0].value='';
  for(const item of result.linelists){const option=reportEl('option',(item.period||'Unassigned')+' · '+item.file+' · '+item.sheet);option.value=JSON.stringify({id:item.id,sheet:item.sheet});comparisonSelector.append(option);}
  comparisonStatus.textContent=result.linelists.length?'Select the baseline quarter. NetNew = weekly TxCurr − quarter TxCurr; CoT/retention = weekly TxCurr ÷ quarter TxCurr × 100 (snapshot ratio).':'No quarterly uploads yet. Upload a quarterly linelist, then refresh this dashboard.';
  comparisonSelector.disabled=false;
 }catch(error){comparisonSelector.options[0].value='';comparisonStatus.textContent=error.message;}
};
