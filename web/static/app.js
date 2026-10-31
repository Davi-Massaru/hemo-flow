/* Shared chart renderer: local Apache ECharts, no framework or external assets. */
'use strict';
(async () => {
  const root=document.querySelector('[data-analytics-url]');
  let strings;
  try { const response=await fetch(document.body.dataset.localeUrl,{credentials:'same-origin'}); if(!response.ok)throw Error(); strings=await response.json(); }
  catch { if(root)root.querySelector('.chart-status').textContent=document.body.dataset.loadError || 'Unable to load language resources.'; return; }
  const t=key=>strings[key] || key;
  document.querySelectorAll('input,select').forEach(input=>{
    input.addEventListener('invalid',()=>{input.setCustomValidity(''); if(!input.validity.valid) input.setCustomValidity(t(input.validity.valueMissing?'validation_required':input.validity.rangeOverflow||input.validity.rangeUnderflow||input.validity.badInput?'validation_number':'validation_invalid'));});
    input.addEventListener('input',()=>input.setCustomValidity(''));
  });
  if(!root)return;
  const css=getComputedStyle(document.documentElement), token=name=>css.getPropertyValue('--'+name).trim();
  const palette=['primary','forecast','chart-3','chart-4','chart-5'].map(token);
  const instances=[]; const grid=root.querySelector('.charts-grid'), status=root.querySelector('.chart-status'), form=root.querySelector('form');
  const selected=new URLSearchParams(location.search).get('center') || root.dataset.defaultCenter;
  if([...form.elements.center.options].some(o=>o.value===selected))form.elements.center.value=selected;
  const group=new URLSearchParams(location.search).get('blood_type');
  if([...form.elements.blood_type.options].some(o=>o.value===group))form.elements.blood_type.value=group;
  const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
  const formatted=value=>value===null||value===undefined?t('unknown'):typeof value==='number'?new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(value):value;
  const utc=value=>value&&Number.isFinite(new Date(value).getTime())?new Date(value).toLocaleString('en-GB',{timeZone:'UTC',hour12:false})+' UTC':t('unknown');
  const observer=new ResizeObserver(()=>instances.forEach(chart=>chart.resize())); observer.observe(grid);
  function rows(spec){return spec.kind==='timeline'?(spec.points||[]).map(p=>[p.name,p.status,utc(p.at)]):(spec.categories||[]).flatMap((cat,index)=>(spec.series||[]).map(s=>[cat,s.name,formatted(s.data[index])]));}
  function option(spec){
    const base={color:palette,backgroundColor:token('background'),animation:!matchMedia('(prefers-reduced-motion: reduce)').matches,
      textStyle:{fontFamily:css.getPropertyValue('--font'),color:token('text')},
      aria:{enabled:true,label:{description:spec.title+'. '+spec.note},decal:{show:true}},
      tooltip:{trigger:'axis',renderMode:'richText',confine:true},legend:{type:'scroll',bottom:0,textStyle:{color:token('muted'),fontSize:11}},
      grid:{left:15,right:20,top:25,bottom:65,containLabel:true}};
    const axis={axisLine:{lineStyle:{color:token('line')}},axisTick:{show:false},axisLabel:{color:token('muted'),fontSize:10},splitLine:{lineStyle:{color:token('line')}}};
    if(spec.kind==='donut'||spec.kind==='funnel'){
      const data=spec.categories.map((name,i)=>({name,value:spec.series[0]?.data[i]})).filter(r=>Number.isFinite(r.value));
      return {...base,tooltip:{trigger:'item',renderMode:'richText',confine:true},series:[{type:spec.kind==='donut'?'pie':'funnel',
        radius:['45%','70%'],center:['50%','43%'],top:15,bottom:70,left:'16%',width:'66%',sort:'none',minSize:'10%',
        label:{show:true,fontSize:10,color:token('text')},data}]};
    }
    if(spec.kind==='heatmap'){
      const data=spec.series.flatMap((s,y)=>s.data.map((value,x)=>[x,y,value])).filter(r=>Number.isFinite(r[2]));
      return {...base,tooltip:{position:'top',renderMode:'richText',confine:true},legend:{show:false},
        xAxis:{...axis,type:'category',data:spec.categories,splitArea:{show:true}},yAxis:{...axis,type:'category',data:spec.series.map(s=>s.name),splitArea:{show:true}},
        visualMap:{min:0,max:Math.max(1,...data.map(d=>d[2])),calculable:true,orient:'horizontal',left:'center',bottom:0,inRange:{color:[token('primary-soft'),token('primary')]},textStyle:{color:token('text')}},
        series:[{type:'heatmap',data,label:{show:true,color:token('text'),backgroundColor:token('background'),padding:[2,4],borderRadius:2},itemStyle:{borderWidth:2,borderColor:token('background')}}]};
    }
    if(spec.kind==='timeline'){
      const labels=[...new Set(spec.points.map(p=>p.name))],states=[...new Set(spec.points.map(p=>p.status))];
      return {...base,tooltip:{trigger:'item',renderMode:'richText',confine:true,formatter:p=>p.seriesName+'\n'+p.value[1]+'\n'+utc(p.value[0])},
        xAxis:{...axis,type:'time',axisLabel:{...axis.axisLabel,formatter:v=>new Date(v).toISOString().slice(5,10)}},
        yAxis:{...axis,type:'category',data:labels,axisLabel:{...axis.axisLabel,width:120,overflow:'truncate'}},
        series:states.map(name=>({name,type:'scatter',symbolSize:11,data:spec.points.filter(p=>p.status===name).map(p=>[new Date(p.at).getTime(),p.name])})),
        dataZoom:labels.length>8?[{type:'slider',yAxisIndex:0,right:0,start:0,end:Math.min(100,800/labels.length)}]:[]};
    }
    const long=spec.categories.length>12;
    return {...base,grid:{...base.grid,bottom:long?90:65},
      xAxis:{...axis,type:'category',data:spec.categories,axisLabel:{...axis.axisLabel,width:100,overflow:'truncate',hideOverlap:true}},
      yAxis:{...axis,type:'value',min:0,name:spec.unit,nameTextStyle:{color:token('muted'),fontSize:10}},
      dataZoom:long?[{type:'slider',bottom:28,height:16,start:0,end:Math.min(100,1200/spec.categories.length)},{type:'inside'}]:[],
      series:spec.series.map((s,index)=>({name:s.name,type:spec.kind==='line'?'line':'bar',data:s.data.map(v=>Number.isFinite(v)?v:null),
        connectNulls:false,barMaxWidth:38,symbol:s.forecast?'emptyDiamond':'circle',symbolSize:6,
        lineStyle:{width:2,type:s.forecast?'dashed':'solid'},itemStyle:{color:palette[index%palette.length],borderRadius:spec.kind==='line'?0:[4,4,0,0],decal:s.forecast?{symbol:'rect',dashArrayX:[1,0],dashArrayY:[2,4],rotation:-Math.PI/4}:undefined}}))};
  }
  function render(spec){
    const card=el('article','card chart-card');card.dataset.chartId=spec.id;
    const heading=el('div','chart-heading');heading.append(el('h2','',spec.title),el('small','',spec.unit));card.append(heading);
    const data=rows(spec),hasData=spec.kind==='timeline'?spec.points?.length:spec.series.some(s=>s.data.some(Number.isFinite));
    const plot=el('div',hasData&&!spec.error?'chart-plot':'chart-empty');plot.setAttribute('role','img');plot.setAttribute('aria-label',spec.title);card.append(plot);
    if(spec.error){plot.textContent=spec.error;plot.setAttribute('role','alert');}
    else if(!hasData)plot.textContent=t('empty');
    card.append(el('p','chart-note',spec.note));
    const meta=el('div','chart-meta');
    for(const line of [t('source')+': '+spec.source,t('period')+': '+spec.period.start.slice(0,10)+' → '+spec.period.end.slice(0,10),t('updated')+': '+utc(spec.updated_at)])meta.append(el('span','',line));
    if(spec.observations?.length)meta.append(el('span','',t('source_observed')+': '+spec.observations.map(o=>o.center_id+' · '+(o.status==='AVAILABLE'?utc(o.observed_at):t('unknown'))).join(' / ')));
    card.append(meta);
    if(data.length){const details=el('details'),summary=el('summary','',t('data_table')),scroll=el('div','table-scroll'),table=el('table'),head=el('thead'),header=el('tr');
      [t('category'),t('series'),t('value')].forEach(v=>header.append(el('th','',v)));head.append(header);table.append(head);
      const body=el('tbody');data.forEach(row=>{const tr=el('tr');row.forEach(value=>tr.append(el('td','',String(value))));body.append(tr);});table.append(body);scroll.append(table);details.append(summary,scroll);card.append(details);}
    grid.append(card);
    if(hasData&&!spec.error){try {const chart=echarts.init(plot,null,{renderer:'svg',locale:'EN'});chart.setOption(option(spec));instances.push(chart);}catch{plot.className='chart-empty';plot.textContent=t('chart_error');}}
  }
  let controller;
  function operational(payload){
    const summary=root.querySelector('.analytics-summary');summary.replaceChildren();
    for(const item of payload.summary||[]){const card=el('article');card.append(el('small','',item.label),el('strong','',formatted(item.value)),el('span','',item.unit+' · '+payload.blood_type));summary.append(card);}
    const actions=root.querySelector('.analytics-actions');actions.replaceChildren();
    if(root.dataset.page==='panel'){
      const card=el('section','card');card.append(el('h2','',t('action_queue')),el('p','',t('note.actions')));
      if(!payload.actions.length)card.append(el('p','',t('no_pending_actions')));
      for(const item of payload.actions){const row=el('div','action-row'),link=el('a','',item.blood_type+' · '+item.center+' · '+item.status);
        link.href=root.dataset.appRoot+(item.kind==='transfers'?'/blood-transfers':'/donation-campaigns')+'?blood_type='+encodeURIComponent(item.blood_type)+'#'+encodeURIComponent(item.id);
        row.append(link,el('span','',formatted(item.units)+' '+t('unit.units')),el('small','',t('required_by')+': '+(item.due?utc(item.due):t('unknown'))));
        if(item.expected)row.append(el('small','',t('expected_release')+': '+utc(item.expected)));card.append(row);
      }actions.append(card);
    }
    const sources=root.querySelector('.analytics-sources');sources.replaceChildren();
    if(['panel','network'].includes(root.dataset.page)){
      const card=el('section','card'),table=el('table'),head=el('tr');card.append(el('h2','',t('source_evidence')),el('p','',t('note.source_evidence')));
      [t('center'),t('blood_type'),t('available'),t('transferable'),t('source_observed'),t('source_version')].forEach(v=>head.append(el('th','',v)));const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody');
      for(const item of payload.observations.filter(o=>o.blood_type===payload.blood_type)){const row=el('tr');[item.center_id,item.blood_type,item.available_units,item.transferable_units,utc(item.observed_at),item.data_version||t('unknown')].forEach(v=>row.append(el('td','',formatted(v))));body.append(row);}
      table.append(body);const scroll=el('div','table-scroll');scroll.append(table);card.append(scroll);sources.append(card);
    }
    document.querySelectorAll('[data-record-group]').forEach(card=>{card.hidden=!(form.elements.blood_type.value==='ALL'||card.dataset.recordGroup===form.elements.blood_type.value)||!(form.elements.center.value==='ALL'||card.dataset.recordCenters.split(',').includes(form.elements.center.value));});
  }
  async function load(){
    controller?.abort();controller=new AbortController();const current=controller;
    instances.splice(0).forEach(c=>c.dispose());grid.replaceChildren();grid.setAttribute('aria-busy','true');status.textContent=t('loading');
    form.querySelector('button').disabled=true;
    try{
      const query=new URLSearchParams(new FormData(form));
      const response=await fetch(root.dataset.analyticsUrl+'?'+query,{credentials:'same-origin',signal:current.signal});
      if(!response.ok)throw Error();const payload=await response.json();
      if(current!==controller)return;
      payload.charts.forEach(render);
      operational(payload);
      status.textContent=(payload.demo?t('demo_banner')+' · ':'')+t('updated')+': '+utc(payload.updated_at)+(payload.unavailable.length?' · '+t('unavailable')+': '+payload.unavailable.join(', '):'');
      status.classList.toggle('notice',payload.unavailable.length>0);
    }catch(error){if(error.name==='AbortError')return;status.textContent=t('request_error');const retry=el('button','',t('retry'));retry.type='button';retry.addEventListener('click',load);status.append(retry);}
    finally{if(current===controller){grid.setAttribute('aria-busy','false');form.querySelector('button').disabled=false;}}
  }
  form.addEventListener('submit',event=>{event.preventDefault();load();});
  form.querySelectorAll('select').forEach(select=>select.addEventListener('change',load));
  await load();
})();
