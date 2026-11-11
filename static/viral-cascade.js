/* Shared weekly and quarterly cascade view; exports the displayed report snapshot. */
function renderViralCascade(report,box){
 const columns=[['txcurr','TxCurr'],['eligible','VL eligible'],['sample_collected','Sample collected'],['result','VL result'],['vl_suppression','Suppressed'],['undetectable','Undetectable'],['llv','LLV'],['unsuppressed','Unsuppressed'],['sample_collection_rate','Collection rate (%)'],['coverage','VL coverage (%)'],['suppression_rate','Suppression rate (%)'],['undetectable_rate','Undetectable rate (%)'],['llv_rate','LLV rate (%)']];
 const section=reportEl('section');section.append(reportEl('h2','Viral load cascade by state and facility'));
 section.append(reportEl('p',report.source.file+' · '+(report.source.period||'Unassigned period')+' · VL window '+report.start_date+' to '+report.end_date));
 section.append(reportEl('p','Counts use the selected snapshot. VL eligibility requires Active status and at least 180 days on ART. N/A means the rate denominator is zero. Facility codes distinguish facilities with the same name.'));
 const stateFilter=reportEl('select');stateFilter.setAttribute('aria-label','Cascade state filter');const all=reportEl('option','All states');all.value='';stateFilter.append(all);
 for(const state of Object.keys(report.states)){const option=reportEl('option',state);option.value=state;stateFilter.append(option);}
 const label=reportEl('label','Filter cascade by state');label.append(stateFilter);section.append(label);
 const tables=reportEl('div');section.append(tables);box.append(section);
 const format=(key,value)=>value===null||value===undefined?'N/A':key.endsWith('rate')||key==='coverage'?Number(value).toFixed(1):String(value);
 const draw=()=>{
  tables.replaceChildren();
  const selected=stateFilter.value;
  const stateRows=Object.entries(report.states).filter(([name])=>!selected||name===selected).map(([state,values])=>({state,...values}));
  const facilityRows=(report.facilities||[]).filter(row=>!selected||row.state===selected);
  for(const [kind,rows,identity] of [['state',stateRows,[['state','State']]],['facility',facilityRows,[['state','State'],['facility','Facility'],['datim_code','DATIM code']]]]){
   const panel=reportEl('div');panel.append(reportEl('h3',kind==='state'?'State cascade':'Facility cascade'));
   const fields=[...identity,...columns],matrix=rows.map(row=>fields.map(([key])=>identity.some(([id])=>id===key)?String(row[key]||''):format(key,row[key])));
   const download=reportEl('button','Download '+kind+' cascade (CSV)');download.type='button';download.disabled=!rows.length;
   download.onclick=()=>{
    const escape=value=>{let text=String(value);if(/^[=+@\-\t\r]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';};
    const context=[['Workflow',treatmentApiPrefix?'Quarterly':'Weekly'],['Source',report.source.file],['Period',report.source.period||'Unassigned'],['Worksheet',report.source.sheet],['VL start',report.start_date],['VL end',report.end_date],['State filter',selected||'All states'],[]];
    const csv='\uFEFF'+[...context,fields.map(([,label])=>label),...matrix].map(row=>row.map(escape).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=reportEl('a');a.href=url;a.download=(treatmentApiPrefix?'quarterly':'weekly')+'_vl_cascade_by_'+kind+'_'+report.end_date+'.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
   };
   panel.append(download);const scroll=reportEl('div');scroll.className='scroll';const table=reportEl('table');table.setAttribute('aria-label',kind+' viral load cascade');const head=reportEl('thead'),heading=reportEl('tr');for(const [,label] of fields){const cell=reportEl('th',label);cell.scope='col';heading.append(cell);}head.append(heading);table.append(head);const body=reportEl('tbody');for(const row of matrix){const tr=reportEl('tr');for(const value of row)tr.append(reportEl('td',value));body.append(tr);}table.append(body);scroll.append(table);panel.append(scroll);if(!rows.length)panel.append(reportEl('p','No records for this selection.'));tables.append(panel);
  }
 };
 stateFilter.onchange=draw;draw();
}
