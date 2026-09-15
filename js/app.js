/* Arizona Drought Model Explorer -- front-end logic */
"use strict";

// ---------- tiny helpers ----------------------------------------------------
const $ = (id) => document.getElementById(id);
const getJSON = (u) => fetch(u).then(r => r.json());
const getBin  = (u) => fetch(u).then(r => r.arrayBuffer()).then(b => new Float32Array(b));

const PLOT_CFG = {displayModeLogo:false, responsive:true,
  modeBarButtonsToRemove:['select2d','lasso2d','autoScale2d']};

// diverging drought scale: dry(neg)=brown -> wet(pos)=teal/green  (BrBG-like)
const CS_DROUGHT = [[0,'#7f4909'],[0.2,'#c58a3d'],[0.4,'#e8d9b5'],[0.5,'#f6f4ef'],
  [0.6,'#bfe3dd'],[0.8,'#43a99a'],[1,'#00655a']];
const CS_ERR   = [[0,'#2166ac'],[0.5,'#f7f7f7'],[1,'#b2182b']];  // pred-obs
const CS_PFI   = [[0,'#fbeff2'],[0.4,'#d98aa2'],[0.7,'#b23a5f'],[1,'#8C1D40']];
// ASU brand: maroon for dynamic drought indices, gold for static predictors
const GROUP_COLORS = {dynamic:'#8C1D40', temporal:'#c98aa0', static:'#FFC627'};

// ---------- global state ----------------------------------------------------
let GRID = null, MANIFEST = null;
const cache = {idx:{}, model:{}, modelBin:{}, pfimap:{}, staticData:null};

// reshape a Float32Array slice (length nlat*nlon) into 2D [nlat][nlon] w/ nulls
function to2D(flat, off, nlat, nlon){
  const z = new Array(nlat);
  for(let r=0;r<nlat;r++){
    const row = new Array(nlon);
    for(let c=0;c<nlon;c++){
      const v = flat[off + r*nlon + c];
      row[c] = Number.isFinite(v) ? v : null;
    }
    z[r] = row;
  }
  return z;
}

function mapLayout(title, cbTitle){
  return {
    title:{text:title, font:{size:14}},
    margin:{l:44,r:12,t:34,b:50},
    xaxis:{title:{text:'Longitude', standoff:14}, constrain:'domain', zeroline:false},
    yaxis:{title:'Latitude', scaleanchor:'x', scaleratio:1, zeroline:false},
    paper_bgcolor:'white', plot_bgcolor:'#eef1f4',
  };
}

function heatTrace(z, opts){
  return Object.assign({
    type:'heatmap', z:z, x:GRID.lons, y:GRID.lats,
    connectgaps:false, hoverongaps:false,
    colorbar:{title:{text:opts.cbTitle||'', side:'right'}, thickness:14, len:.9},
    hovertemplate:'lon %{x:.2f}, lat %{y:.2f}<br>'+(opts.hlabel||'value')+
                  ' %{z:.3f}<extra></extra>',
  }, opts.extra||{});
}

// ---------- generic play/slider driver --------------------------------------
function makePlayer(btn, slider, onFrame){
  let timer=null;
  const step=()=>{ let v=+slider.value; v=(v+1>+slider.max)?+slider.min:v+1;
    slider.value=v; onFrame(v); };
  btn.onclick=()=>{
    if(timer){clearInterval(timer);timer=null;btn.classList.remove('playing');btn.innerHTML='&#9654;';}
    else{btn.classList.add('playing');btn.innerHTML='&#10073;&#10073;';
         timer=setInterval(step,450);}
  };
  slider.oninput=()=>onFrame(+slider.value);
}

// ============================================================================
// TAB 1 : drought indices
// ============================================================================
async function loadIdx(col){
  if(!cache.idx[col]) cache.idx[col] = await getBin(`data/idx_${col}.f32`);
  return cache.idx[col];
}
let idxInit=false;
async function initIndices(){
  const selA=$('idx-select-a'), selB=$('idx-select-b'),
        sl=$('idx-slider'), lbl=$('idx-datelbl');
  const dates=GRID.index_dates;
  sl.max=dates.length-1; sl.value=dates.length-1;
  const nlat=GRID.nlat, nlon=GRID.nlon, cells=nlat*nlon;

  async function drawOne(divId, col, t){
    const cube=await loadIdx(col);
    const z=to2D(cube, t*cells, nlat, nlon);
    const tr=heatTrace(z,{cbTitle:col.toUpperCase(),hlabel:col.toUpperCase(),
      extra:{colorscale:CS_DROUGHT, zmin:-3, zmax:3, zmid:0}});
    Plotly.react(divId,[tr],mapLayout(col.toUpperCase()+' — '+dates[t]),PLOT_CFG);
  }
  async function draw(t){
    lbl.textContent=dates[t];
    await Promise.all([
      drawOne('idx-map-a', selA.value, t),
      drawOne('idx-map-b', selB.value, t),
    ]);
  }
  selA.onchange=()=>draw(+sl.value);
  selB.onchange=()=>draw(+sl.value);
  makePlayer($('idx-play'), sl, draw);
  idxInit=true;
  await draw(+sl.value);
}

// ============================================================================
// TAB 2 : static variables
// ============================================================================
const PRETTY=(s)=>s.replace(/_/g,' ');
let statInit=false;
async function initStatic(){
  if(!cache.staticData) cache.staticData=await getJSON('data/static.json');
  const D=cache.staticData, sel=$('stat-select');
  sel.innerHTML='';
  D.variables.forEach(v=>{const o=document.createElement('option');
    o.value=v;o.textContent=PRETTY(v);sel.appendChild(o);});
  function draw(){
    const v=sel.value, z=D.maps[v], mt=D.meta[v];
    const tr=heatTrace(z,{cbTitle:'',hlabel:PRETTY(v),
      extra:{colorscale:'Viridis', zmin:mt.min, zmax:mt.max}});
    Plotly.react('stat-map',[tr],mapLayout(PRETTY(v)),PLOT_CFG);
  }
  sel.onchange=draw; statInit=true; draw();
}

// ============================================================================
// TAB 3 : modeled vs observed
// ============================================================================
async function loadModel(key){
  if(!cache.model[key]) cache.model[key]=await getJSON(`data/model_${key}.json`);
  if(!cache.modelBin[key]){
    const [obs,pred]=await Promise.all([
      getBin(`data/model_${key}_obs.f32`), getBin(`data/model_${key}_pred.f32`)]);
    cache.modelBin[key]={obs,pred};
  }
  return {meta:cache.model[key], bin:cache.modelBin[key]};
}
let moInit=false, moKey=null;
async function initModObs(){
  const sel=$('mo-select'); moKey=sel.value;
  await drawModObs(); moInit=true;
  sel.onchange=async()=>{moKey=sel.value; await drawModObs();};
}
async function drawModObs(){
  const {meta,bin}=await loadModel(moKey);
  const nlat=GRID.nlat, nlon=GRID.nlon, cells=nlat*nlon;

  // metrics
  const m=meta.metrics;
  $('mo-metrics').innerHTML=[
    ['R²', m.r2!=null?m.r2.toFixed(3):'—'],
    ['RMSE', m.rmse.toFixed(3)], ['MAE', m.mae.toFixed(3)],
    ['Bias', (m.bias>=0?'+':'')+m.bias.toFixed(3)],
    ['n', m.n.toLocaleString()],
  ].map(([s,v])=>`<div class="m"><b>${v}</b><span>${s}</span></div>`).join('');

  // scatter obs vs pred
  const sc=meta.scatter;
  const lo=Math.min(...sc.obs,...sc.pred), hi=Math.max(...sc.obs,...sc.pred);
  Plotly.react('mo-scatter',[
    {x:sc.obs,y:sc.pred,mode:'markers',type:'scattergl',
      marker:{size:3,color:'#8C1D40',opacity:.35},name:'test cells',
      hovertemplate:'obs %{x:.2f}<br>pred %{y:.2f}<extra></extra>'},
    {x:[lo,hi],y:[lo,hi],mode:'lines',line:{color:'#5c5658',dash:'dash',width:1.5},
      name:'1:1',hoverinfo:'skip'}
  ],{title:{text:'Predicted vs observed ('+meta.index_col.toUpperCase()+')',font:{size:13}},
     margin:{l:48,r:10,t:34,b:40},showlegend:false,
     xaxis:{title:'Observed'}, yaxis:{title:'Predicted',scaleanchor:'x',scaleratio:1}},PLOT_CFG);

  // time series domain mean
  const ts=meta.timeseries;
  Plotly.react('mo-ts',[
    {x:ts.dates,y:ts.obs,mode:'lines',name:'observed',line:{color:'#191919',width:1.6}},
    {x:ts.dates,y:ts.pred,mode:'lines',name:'predicted',line:{color:'#8C1D40',width:1.6}}
  ],{title:{text:'Domain-mean '+meta.index_col.toUpperCase()+' over test period',font:{size:13}},
     margin:{l:44,r:10,t:34,b:40},
     legend:{orientation:'h',x:0,y:1.0,yanchor:'top',bgcolor:'rgba(255,255,255,0.55)'},
     xaxis:{title:''}, yaxis:{title:'index'}},PLOT_CFG);

  // map trio with slider
  const sl=$('mo-slider'), lbl=$('mo-datelbl');
  sl.max=meta.ntest-1; sl.value=0;
  const rng=meta.value_range;
  const vlim=Math.min(3, Math.max(Math.abs(rng.min),Math.abs(rng.max)));
  function frame(t){
    lbl.textContent=meta.test_dates[t];
    const zo=to2D(bin.obs,  t*cells, nlat, nlon);
    const zp=to2D(bin.pred, t*cells, nlat, nlon);
    const ze=zo.map((row,r)=>row.map((v,c)=>
      (v==null||zp[r][c]==null)?null:(zp[r][c]-v)));
    Plotly.react('mo-obs',[heatTrace(zo,{cbTitle:'',hlabel:'obs',
      extra:{colorscale:CS_DROUGHT,zmin:-3,zmax:3,zmid:0}})],
      mapLayout('Observed'),PLOT_CFG);
    Plotly.react('mo-pred',[heatTrace(zp,{cbTitle:'',hlabel:'pred',
      extra:{colorscale:CS_DROUGHT,zmin:-3,zmax:3,zmid:0}})],
      mapLayout('Predicted'),PLOT_CFG);
    Plotly.react('mo-err',[heatTrace(ze,{cbTitle:'',hlabel:'pred−obs',
      extra:{colorscale:CS_ERR,zmin:-2,zmax:2,zmid:0}})],
      mapLayout('Error (pred − obs)'),PLOT_CFG);
  }
  makePlayer($('mo-play'), sl, frame);
  frame(0);
}

// ============================================================================
// TAB 4 : feature importance (ranked bar)
// ============================================================================
let pfiInit=false;
async function initPFI(){
  const sel=$('pfi-select'), grp=$('pfi-group'), top=$('pfi-top');
  async function draw(){
    const key=sel.value;
    const meta=(await loadModelMetaOnly(key));
    let rows=meta.pfi_rank.slice();
    if(grp.value!=='all') rows=rows.filter(r=>r.group===grp.value);
    rows.sort((a,b)=>a.delta-b.delta);            // ascending -> largest on top
    if(top.checked) rows=rows.slice(-5);
    Plotly.react('pfi-bar',[{
      type:'bar', orientation:'h',
      y:rows.map(r=>r.feature), x:rows.map(r=>r.delta),
      error_x:{type:'data',array:rows.map(r=>r.std),thickness:1,color:'#8899a5'},
      marker:{color:rows.map(r=>GROUP_COLORS[r.group]||'#888')},
      hovertemplate:'%{y}<br>ΔRMSE %{x:.4f}<extra></extra>'
    }],{
      title:{text:'Permutation importance — '+meta.title,font:{size:13}},
      margin:{l:200,r:20,t:36,b:44},
      xaxis:{title:'Δ RMSE when feature permuted'},
      yaxis:{automargin:true, tickfont:{size:10}, ticklabelstandoff:8},
      showlegend:false,
    },PLOT_CFG);
  }
  sel.onchange=draw; grp.onchange=draw; top.onchange=draw;
  pfiInit=true; await draw();
}
async function loadModelMetaOnly(key){
  if(!cache.model[key]) cache.model[key]=await getJSON(`data/model_${key}.json`);
  return cache.model[key];
}

// ============================================================================
// TAB 5 : PFI maps
// ============================================================================
async function loadPfiMaps(key){
  if(!cache.pfimap[key]) cache.pfimap[key]=await getBin(`data/model_${key}_pfimaps.f32`);
  return cache.pfimap[key];
}
let pmInit=false;
async function initPfiMap(){
  const sel=$('pm-select'), feat=$('pm-feature');
  async function refreshFeatures(){
    const meta=await loadModelMetaOnly(sel.value);
    feat.innerHTML='';
    meta.pfi_features.forEach((f,i)=>{const o=document.createElement('option');
      o.value=i;o.textContent=f;feat.appendChild(o);});
  }
  async function draw(){
    const key=sel.value;
    const meta=await loadModelMetaOnly(key);
    const maps=await loadPfiMaps(key);
    const nlat=GRID.nlat, nlon=GRID.nlon, cells=nlat*nlon;
    const i=+feat.value||0;
    const z=to2D(maps, i*cells, nlat, nlon);
    let mx=0; for(const v of maps.subarray(i*cells,(i+1)*cells)) if(Number.isFinite(v)&&v>mx) mx=v;
    const tr=heatTrace(z,{cbTitle:'ΔRMSE',hlabel:'ΔRMSE',
      extra:{colorscale:CS_PFI, zmin:0, zmax:mx||1}});
    Plotly.react('pm-map',[tr],mapLayout('Spatial importance — '+meta.pfi_features[i]),PLOT_CFG);
  }
  sel.onchange=async()=>{await refreshFeatures(); await draw();};
  feat.onchange=draw;
  await refreshFeatures(); pmInit=true; await draw();
}

// ============================================================================
// tab routing + boot
// ============================================================================
const INITS={indices:()=>!idxInit&&initIndices(), static:()=>!statInit&&initStatic(),
  modobs:()=>!moInit&&initModObs(), pfi:()=>!pfiInit&&initPFI(),
  pfimap:()=>!pmInit&&initPfiMap()};

function activate(name){
  document.querySelectorAll('nav .tab').forEach(b=>
    b.classList.toggle('active', b.dataset.tab===name));
  document.querySelectorAll('main .panel').forEach(p=>
    p.classList.toggle('active', p.id===name));
  const fn=INITS[name]; if(fn) fn();
  // Plotly needs a resize nudge when a hidden plot becomes visible
  setTimeout(()=>window.dispatchEvent(new Event('resize')),60);
}

async function boot(){
  [MANIFEST, GRID] = await Promise.all([getJSON('data/manifest.json'), getJSON('data/grid.json')]);
  $('genstamp').textContent='data generated '+MANIFEST.generated;
  const m=MANIFEST.models;
  $('footinfo').innerHTML=
    `Grid ${GRID.nlat}×${GRID.nlon} @0.25° &middot; `+
    `${MANIFEST.index_ndates} monthly steps (${GRID.index_dates[0]}–${GRID.index_dates.at(-1)}) &middot; `+
    `${MANIFEST.n_static} static variables &middot; `+
    `${Object.keys(m).length} models, ${m.ssmi?m.ssmi.ntest:0} test months each`;
  document.querySelectorAll('nav .tab').forEach(b=>
    b.onclick=()=>activate(b.dataset.tab));
  activate('indices');
}
boot();
