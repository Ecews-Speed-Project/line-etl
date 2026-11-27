(function(root){
function rankFacilities(rows,metric,direction){
 if(!['unique_linkage','linkage'].includes(metric))throw Error('Invalid ranking metric');
 const eligible=rows.filter(r=>r.hts_pos>0&&Number.isFinite(r[metric]));
 return [...eligible].sort((a,b)=>(direction==='best'?b[metric]-a[metric]:a[metric]-b[metric])||b.hts_pos-a.hts_pos||a.facility.localeCompare(b.facility)||a.lga.localeCompare(b.lga)).slice(0,10).map((row,index)=>({...row,rank:index+1}));
}
if(typeof module!=='undefined'&&module.exports)module.exports=rankFacilities;else root.rankFacilities=rankFacilities;
})(globalThis);
