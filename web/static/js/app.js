/* ══════════════════════════════════════════════════════════
   Market Analysis Dashboard — Full Frontend Logic
   ══════════════════════════════════════════════════════════ */

/* ── Utility ── */
const $ = id => document.getElementById(id);
function show(id){ $(id)?.classList.remove('hidden'); }
function hide(id){ $(id)?.classList.add('hidden'); }
function setText(id,t){ const e=$(id); if(e) e.textContent=t; }
function setHTML(id,h){ const e=$(id); if(e) e.innerHTML=h; }
function formatNum(n){ if(n===null||n===undefined||isNaN(n)) return '—'; return Number(n).toLocaleString('en-IN',{maximumFractionDigits:2}); }
function colorClass(v){ return v>0?'positive':v<0?'negative':'neutral'; }
function setColored(id,v,suf='%'){ const e=$(id); if(!e) return; const n=parseFloat(v); e.textContent=(n>=0?'+':'')+n.toFixed(2)+suf; e.className='change-value '+colorClass(n); }
function tagBg(c){ return{green:'rgba(63,185,80,.15)',lightgreen:'rgba(63,185,80,.1)',red:'rgba(248,81,73,.15)',orange:'rgba(210,153,34,.15)',gray:'rgba(139,148,158,.15)'}[c]||'rgba(139,148,158,.15)'; }
function tagFg(c){ return{green:'#3fb950',lightgreen:'#3fb950',red:'#f85149',orange:'#d29922',gray:'#8b949e'}[c]||'#8b949e'; }
function fmtVol(v){ if(!v) return '—'; if(v>=1e7) return (v/1e7).toFixed(2)+' Cr'; if(v>=1e5) return (v/1e5).toFixed(2)+' L'; if(v>=1e6) return (v/1e6).toFixed(2)+'M'; if(v>=1e3) return (v/1e3).toFixed(1)+'K'; return String(v); }
function scoreColor(s){ if(s>=65) return '#3fb950'; if(s>=50) return '#58a6ff'; if(s>=35) return '#d29922'; return '#f85149'; }

/* ── State ── */
let currentAnalysisData = null;
let currentTicker = '';

/* ══════════════════════════════════════════════════════════
   TABS
══════════════════════════════════════════════════════════ */
function switchTab(name){
  document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  const tab = $('tab-'+name);
  if(tab){ tab.classList.add('active'); tab.classList.remove('hidden'); }
  const btns = document.querySelectorAll('.tab-btn');
  btns.forEach(b=>{ if(b.textContent.toLowerCase().includes(name.toLowerCase())) b.classList.add('active'); });

  if(name==='today') loadMarketSummary();
  if(name==='portfolio') loadPortfolio();
  if(name==='alerts') loadAlerts();
}

/* ══════════════════════════════════════════════════════════
   ANALYZE TAB
══════════════════════════════════════════════════════════ */

function quickPick(t){ $('tickerInput').value=t; runAnalysis(); }
function clearError(){ hide('errorSection'); }
function showError(msg){ hide('loadingSection'); hide('resultsSection'); setText('errorText',msg); show('errorSection'); }

async function runAnalysis(){
  const ticker = $('tickerInput').value.trim().toUpperCase();
  const period = parseInt($('periodSelect').value);
  if(!ticker){ showError('Please enter a ticker symbol.'); return; }

  currentTicker = ticker;
  hide('resultsSection'); hide('errorSection'); hide('narrativeCard');
  show('loadingSection');
  $('analyzeBtn').disabled = true;

  const steps = ['Fetching live market data...','Computing technical indicators...','Detecting market regime...','Running momentum analysis...','Training prediction model...','Building interactive charts...'];
  let si=0;
  setText('loadingText', steps[0]);
  setHTML('loadingSteps','');
  const iv = setInterval(()=>{ if(si<steps.length-1){ $('loadingSteps').innerHTML+=`<div class="loading-step done">✓ ${steps[si]}</div>`; si++; setText('loadingText',steps[si]); } },1000);

  try {
    const res = await fetch('/api/analyze',{ method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ticker,period_years:period}) });
    clearInterval(iv);
    if(!res.ok){ const e=await res.json(); throw new Error(e.detail||'Analysis failed'); }
    const data = await res.json();
    currentAnalysisData = data;
    renderResults(data);
  } catch(err){
    clearInterval(iv);
    showError(err.message||'Failed to analyze. Check the ticker and try again.');
  } finally {
    hide('loadingSection');
    $('analyzeBtn').disabled = false;
  }
}

/* ── Narrative ── */
async function loadNarrative(){
  if(!currentTicker){ return; }
  show('narrativeCard');
  setText('narrativeText','');
  show('narrativeLoading');

  try {
    const period = parseInt($('periodSelect').value);
    const res = await fetch('/api/narrative',{ method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ticker:currentTicker, period_years:period}) });
    const data = await res.json();
    hide('narrativeLoading');
    setText('narrativeText', data.narrative || 'Could not generate narrative.');
  } catch(e){
    hide('narrativeLoading');
    setText('narrativeText','Could not generate narrative. Please try again.');
  }
}

/* ── Render Full Results ── */
function renderResults(data){
  const {ticker,company_name,sector,exchange,currency,market_cap,as_of,market_status,live_quote,regime,metrics,strategy,performance,chart_data,intraday,intraday_momentum,predictions,momentum_score} = data;
  const sym = currency==='INR'?'₹':'$';

  setText('companyName',company_name);
  setText('tickerBadge',ticker);
  setText('exchangeBadge',exchange||'—');
  setText('sectorBadge',sector||'—');
  setText('marketCapBadge',market_cap||'—');
  setText('currentPrice',sym+formatNum(metrics.price));

  const d=metrics.change_day;
  const dayEl=$('dayChange');
  dayEl.textContent=(d>=0?'+':'')+d.toFixed(2)+'% today';
  dayEl.className='price-change '+colorClass(d);

  const msEl=$('marketStatusBadge');
  msEl.textContent=market_status.status_label+' · '+market_status.local_time;
  msEl.style.color={green:'#3fb950',orange:'#d29922',gray:'#8b949e'}[market_status.status_color]||'#8b949e';

  // Pre-fill modal fields with current ticker
  if($('holdingTicker')) $('holdingTicker').value = ticker;
  if($('alertTicker')) $('alertTicker').value = ticker;

  // Live quote
  if(live_quote?.price){
    setText('lqHigh', sym+formatNum(live_quote.day_high));
    setText('lqLow', sym+formatNum(live_quote.day_low));
    setText('lqPrevClose', sym+formatNum(live_quote.prev_close));
    setText('lqVolume', fmtVol(live_quote.volume));
    setText('lq52High', sym+formatNum(live_quote.week52_high));
    setText('lq52Low', sym+formatNum(live_quote.week52_low));
    const rp=live_quote.week52_range_pct||0;
    if($('rangeBarFill')) $('rangeBarFill').style.width=rp+'%';
    setText('lqRangePct', rp.toFixed(1)+'% from 52W low');
  }

  // Regime
  const banner=$('regimeBanner');
  banner.className='regime-banner '+(regime.color||'gray');
  setText('regimeName',regime.regime);
  setText('regimeDesc',regime.description);
  setText('regimeTip',regime.strategy_tip);

  // Momentum
  if(momentum_score) renderMomentumScore(momentum_score);

  // Intraday
  if(intraday?.candles?.length>0) renderIntraday(intraday,intraday_momentum,sym);

  // Indicators
  setText('rsiValue',metrics.rsi);
  const rsiTag=$('rsiLabel'); rsiTag.textContent=metrics.rsi_label; rsiTag.style.background=tagBg(metrics.rsi_color); rsiTag.style.color=tagFg(metrics.rsi_color);
  setText('bbValue',metrics.bb_pct+'%');
  const bbTag=$('bbLabel'); bbTag.textContent=metrics.bb_label; bbTag.style.background=tagBg(metrics.bb_color); bbTag.style.color=tagFg(metrics.bb_color);
  const macdEl=$('macdLabel'); macdEl.textContent=metrics.macd_label; macdEl.className='metric-value '+(metrics.macd_color==='green'?'positive':'negative');
  setText('volumeLabel',metrics.volume_label);
  setText('volatility',metrics.volatility_annual+'%');
  setText('atrValue',sym+metrics.atr);

  // Changes
  setColored('changeDay',metrics.change_day);
  setColored('changeWeek',metrics.change_week);
  setColored('changeMonth',metrics.change_month);
  setColored('changeYear',metrics.change_year);

  // Predictions
  if(predictions) renderPredictions(predictions,sym);

  // Strategy
  const riskEl=$('strategyRisk'); riskEl.textContent='⚡ Risk Level: '+strategy.risk_level; riskEl.style.background=tagBg(strategy.risk_color); riskEl.style.color=tagFg(strategy.risk_color);
  setHTML('strategyActions',strategy.actions.map(a=>`<div class="action-item">${a}</div>`).join(''));

  // Signals
  setHTML('signalsList', regime.signals?.length ? regime.signals.map(s=>`<div class="signal-item">• ${s}</div>`).join('') : '<div class="signal-item">No strong signals detected.</div>');

  // Charts
  renderPriceChart(chart_data,sym);
  renderRSIChart(chart_data);
  renderMACDChart(chart_data);

  // Performance
  if(performance && Object.keys(performance).length){
    const ret=performance.total_return;
    const retEl=$('perfReturn'); retEl.textContent=(ret>=0?'+':'')+ret+'%'; retEl.className='perf-value '+colorClass(ret);
    const cagr=performance.cagr;
    const cagrEl=$('perfCagr'); cagrEl.textContent=(cagr>=0?'+':'')+cagr+'%'; cagrEl.className='perf-value '+colorClass(cagr);
    const s=performance.sharpe;
    const sEl=$('perfSharpe'); sEl.textContent=s; sEl.className='perf-value '+(s>1?'positive':s>0?'warn':'negative');
    const dd=performance.max_drawdown;
    const ddEl=$('perfDrawdown'); ddEl.textContent=dd.toFixed(1)+'%'; ddEl.className='perf-value '+(dd>-10?'positive':dd>-25?'warn':'negative');
    setText('perfWinrate',performance.win_rate+'%');
    setText('perfSortino',performance.sortino);
  }

  show('resultsSection');
  $('resultsSection').scrollIntoView({behavior:'smooth',block:'start'});
}

/* ── Sub-renderers ── */
function renderMomentumScore(ms){
  const color={green:'#3fb950',lightgreen:'#3fb950',orange:'#d29922',red:'#f85149',gray:'#8b949e'}[ms.color]||'#8b949e';
  Plotly.newPlot('momentumGaugeChart',[{type:'indicator',mode:'gauge+number',value:ms.score,gauge:{axis:{range:[0,100],tickcolor:'#8b949e',tickfont:{color:'#8b949e',size:10}},bar:{color},bgcolor:'#21262d',bordercolor:'#30363d',steps:[{range:[0,30],color:'rgba(248,81,73,.15)'},{range:[30,45],color:'rgba(210,153,34,.1)'},{range:[45,60],color:'rgba(139,148,158,.1)'},{range:[60,75],color:'rgba(63,185,80,.1)'},{range:[75,100],color:'rgba(63,185,80,.2)'}]},number:{font:{color:'#e6edf3',size:28}}}],{paper_bgcolor:'#161b22',font:{color:'#e6edf3'},margin:{t:20,r:20,b:20,l:20},height:180},{responsive:true,displayModeBar:false});
  const lEl=$('momentumLabel'); lEl.textContent=ms.emoji+' '+ms.label; lEl.style.color=color;
  setText('momentumAdvice',ms.advice);
  if(ms.breakdown) setHTML('momentumBreakdown',ms.breakdown.map(b=>`<div class="mb-row"><span class="mb-name">${b.name} <small>(${b.weight})</small></span><div class="mb-bar-track"><div class="mb-bar-fill" style="width:${b.score}%;background:${scoreColor(b.score)}"></div></div><span class="mb-score">${Math.round(b.score)}</span></div>`).join(''));
}

function renderIntraday(intraday,momentum,sym){
  setText('intradayStatus',`${intraday.date} · ${intraday.interval} intervals`);
  const idPct=intraday.intraday_change_pct||0;
  setHTML('intradayStats',`
    <div class="id-stat"><div class="id-stat-label">Open</div><div class="id-stat-value">${sym}${formatNum(intraday.open_price)}</div></div>
    <div class="id-stat"><div class="id-stat-label">Current</div><div class="id-stat-value">${sym}${formatNum(intraday.current_price)}</div></div>
    <div class="id-stat"><div class="id-stat-label">Day Change</div><div class="id-stat-value ${colorClass(idPct)}">${idPct>=0?'+':''}${idPct.toFixed(2)}%</div></div>
    <div class="id-stat"><div class="id-stat-label">Intraday High</div><div class="id-stat-value positive">${sym}${formatNum(intraday.intraday_high)}</div></div>
    <div class="id-stat"><div class="id-stat-label">Intraday Low</div><div class="id-stat-value negative">${sym}${formatNum(intraday.intraday_low)}</div></div>
    <div class="id-stat"><div class="id-stat-label">Volume</div><div class="id-stat-value">${fmtVol(intraday.total_volume)}</div></div>
  `);
  if(momentum?.label){
    const mc={green:'#22d3a0',lightgreen:'#22d3a0',orange:'#f59e0b',red:'#ff4f6b',gray:'#8b949e'}[momentum.color]||'#8b949e';
    setHTML('intradayMomentumBanner',`<div style="font-weight:700;color:${mc};font-size:.95rem;">${momentum.label}</div><div class="im-signals">${(momentum.signals||[]).map(s=>`<span>${s}</span>`).join('')}</div>`);
  }
  const candles=intraday.candles||[], openP=intraday.open_price||0;

  const CHART_BG = 'rgba(0,0,0,0)';
  const PLOT_BG  = 'rgba(255,255,255,.02)';
  const GRID     = 'rgba(255,255,255,.06)';

  Plotly.newPlot('intradayChart',
    [
      { x:candles.map(c=>c.time), open:candles.map(c=>c.open), high:candles.map(c=>c.high),
        low:candles.map(c=>c.low), close:candles.map(c=>c.close),
        type:'candlestick', name:'Price',
        increasing:{line:{color:'#22d3a0',width:1.5}, fillcolor:'rgba(34,211,160,.55)'},
        decreasing:{line:{color:'#ff4f6b',width:1.5}, fillcolor:'rgba(255,79,107,.55)'},
      },
      { x:candles.map(c=>c.time), y:intraday.vwap||[],
        type:'scatter', name:'VWAP',
        line:{color:'#a78bfa',width:1.8,dash:'dot'},
      },
      { x:candles.map(c=>c.time), y:candles.map(c=>c.volume),
        type:'bar', name:'Volume', yaxis:'y2',
        marker:{color:candles.map(c=>c.close>=openP?'rgba(34,211,160,.45)':'rgba(255,79,107,.45)')},
      },
    ],
    {
      paper_bgcolor: CHART_BG,
      plot_bgcolor:  PLOT_BG,
      font:{color:'#f0f4ff', size:11},
      margin:{t:12, r:14, b:36, l:58},
      autosize: true,
      xaxis:{
        gridcolor: GRID, linecolor: GRID,
        type:'category', nticks:10,
        rangeslider:{visible:false},    // ← key fix: removes the mini scrollbar
        tickfont:{size:10, color:'rgba(240,244,255,.5)'},
      },
      yaxis:{
        gridcolor: GRID, linecolor:'rgba(0,0,0,0)',
        title:{text:sym+' Price', font:{size:11, color:'rgba(240,244,255,.5)'}},
        domain:[0.28,1],
        tickfont:{size:10, color:'rgba(240,244,255,.5)'},
        zeroline:false,
      },
      yaxis2:{
        gridcolor:'rgba(0,0,0,0)', linecolor:'rgba(0,0,0,0)',
        title:{text:'Vol', font:{size:10, color:'rgba(240,244,255,.4)'}},
        domain:[0, 0.22],
        showgrid:false,
        tickfont:{size:9, color:'rgba(240,244,255,.35)'},
        zeroline:false,
      },
      showlegend:true,
      legend:{bgcolor:'rgba(10,15,35,.6)', bordercolor:'rgba(255,255,255,.08)', borderwidth:1, font:{size:11}},
      hovermode:'x unified',
    },
    {responsive:true, displayModeBar:false}
  );
}

function renderPredictions(predictions,sym){
  setText('predDisclaimer',predictions.disclaimer||'');
  for(const[key,dirId,targId,probId] of[['1_week','pred1wDir','pred1wTargets','pred1wProb'],['1_month','pred1mDir','pred1mTargets','pred1mProb']]){
    const p=predictions[key]; if(!p||p.error) continue;
    const dc={Bullish:'#3fb950',Bearish:'#f85149',Neutral:'#8b949e'}[p.direction]||'#8b949e';
    const dEl=$(dirId); dEl.textContent=p.direction_icon+' '+p.direction+' ('+(p.predicted_return_pct>=0?'+':'')+p.predicted_return_pct+'%)'; dEl.style.color=dc;
    setHTML(targId,`<div class="pred-target-row"><span class="pred-target-label">🐻 Bear Case</span><span class="pred-target-value negative">${sym}${formatNum(p.price_bear)}</span></div><div class="pred-target-row" style="border:1px solid #30363d"><span class="pred-target-label">📊 Base Case</span><span class="pred-target-value" style="color:${dc}">${sym}${formatNum(p.price_base)}</span></div><div class="pred-target-row"><span class="pred-target-label">🐂 Bull Case</span><span class="pred-target-value positive">${sym}${formatNum(p.price_bull)}</span></div>`);
    setHTML(probId,`Probability of positive return: <span>${p.probability_up_pct}%</span>`);
  }
  if(predictions.top_drivers){ const mx=Math.max(...predictions.top_drivers.map(d=>d.importance)); setHTML('topDrivers',predictions.top_drivers.map(d=>`<div class="driver-row"><span class="driver-name">${d.feature}</span><div class="driver-bar-track"><div class="driver-bar-fill" style="width:${(d.importance/mx*100).toFixed(0)}%"></div></div><span class="driver-pct">${d.importance.toFixed(1)}%</span></div>`).join('')); }
}

/* ── Shared chart layout base ── */
const CHART_BG = 'rgba(0,0,0,0)';
const PLOT_BG  = 'rgba(255,255,255,.02)';
const GRID     = 'rgba(255,255,255,.06)';
const TICK_C   = 'rgba(240,244,255,.45)';

const LB = {
  paper_bgcolor: CHART_BG,
  plot_bgcolor:  PLOT_BG,
  font:   { color:'#f0f4ff', size:11 },
  margin: { t:12, r:14, b:36, l:58 },
  autosize: true,
  xaxis: {
    gridcolor: GRID, linecolor: 'rgba(0,0,0,0)',
    tickfont:  { size:10, color:TICK_C },
    rangeslider: { visible:false },   // always off
    zeroline: false,
  },
  yaxis: {
    gridcolor: GRID, linecolor: 'rgba(0,0,0,0)',
    tickfont:  { size:10, color:TICK_C },
    zeroline: false,
  },
  hovermode: 'x unified',
  legend: {
    bgcolor:'rgba(10,15,35,.65)', bordercolor:'rgba(255,255,255,.08)',
    borderwidth:1, font:{ size:11, color:'#f0f4ff' },
  },
};

function renderPriceChart(cd, sym) {
  const traces = [
    { x:cd.dates, y:cd.price, type:'scatter', name:'Price',
      line:{color:'#f0f4ff', width:2},
    },
    { x:cd.dates, y:cd.bb_upper, type:'scatter', name:'BB Upper',
      line:{color:'#4f9eff', width:1, dash:'dot'}, opacity:.55,
    },
    { x:cd.dates, y:cd.bb_lower, type:'scatter', name:'BB Lower',
      line:{color:'#4f9eff', width:1, dash:'dot'},
      fill:'tonexty', fillcolor:'rgba(79,158,255,.04)', opacity:.55,
    },
    { x:cd.dates, y:cd.sma20, type:'scatter', name:'SMA 20',
      line:{color:'#22d3a0', width:1.8},
    },
    { x:cd.dates, y:cd.sma50, type:'scatter', name:'SMA 50',
      line:{color:'#f59e0b', width:1.8},
    },
  ];
  const layout = {
    ...LB,
    yaxis: { ...LB.yaxis, title:{ text:sym+' Price', font:{size:11,color:TICK_C} } },
    showlegend: true,
  };
  Plotly.newPlot('priceChart', traces, layout, {responsive:true, displayModeBar:false});
}

function renderRSIChart(cd) {
  const traces = [
    { x:cd.dates, y:cd.rsi, type:'scatter', name:'RSI',
      line:{color:'#a78bfa', width:2},
      fill:'tozeroy', fillcolor:'rgba(167,139,250,.06)',
    },
  ];
  const layout = {
    ...LB,
    yaxis: { ...LB.yaxis, range:[0,100], title:{text:'RSI', font:{size:11,color:TICK_C}} },
    margin: { ...LB.margin, t:5 },
    showlegend: false,
    shapes: [
      { type:'line', xref:'paper', x0:0, x1:1, y0:70, y1:70,
        line:{color:'rgba(255,79,107,.55)', dash:'dot', width:1} },
      { type:'line', xref:'paper', x0:0, x1:1, y0:30, y1:30,
        line:{color:'rgba(34,211,160,.55)', dash:'dot', width:1} },
    ],
  };
  Plotly.newPlot('rsiChart', traces, layout, {responsive:true, displayModeBar:false});
}

function renderMACDChart(cd) {
  const dc = cd.macd_diff.map(v => v >= 0 ? 'rgba(34,211,160,.75)' : 'rgba(255,79,107,.75)');
  const traces = [
    { x:cd.dates, y:cd.macd_diff, type:'bar', name:'Histogram',
      marker:{color:dc},
    },
    { x:cd.dates, y:cd.macd, type:'scatter', name:'MACD',
      line:{color:'#4f9eff', width:2},
    },
    { x:cd.dates, y:cd.macd_signal, type:'scatter', name:'Signal',
      line:{color:'#f59e0b', width:1.6, dash:'dot'},
    },
  ];
  const layout = {
    ...LB,
    yaxis: { ...LB.yaxis, title:{text:'MACD', font:{size:11,color:TICK_C}} },
    margin: { ...LB.margin, t:5 },
    showlegend: true,
    barmode: 'overlay',
  };
  Plotly.newPlot('macdChart', traces, layout, {responsive:true, displayModeBar:false});
}

/* ══════════════════════════════════════════════════════════
   TODAY'S MARKET TAB
══════════════════════════════════════════════════════════ */
let marketSummaryLoaded = false;

async function loadMarketSummary(){
  show('todayLoading');
  hide('moodBanner');
  setHTML('indexCards','');
  setHTML('indexNarratives','');

  try {
    const res = await fetch('/api/market-summary');
    const data = await res.json();
    hide('todayLoading');
    renderMarketSummary(data);
    marketSummaryLoaded = true;
  } catch(e){
    hide('todayLoading');
    setHTML('indexCards','<p class="empty-text">Could not load market data. Please try again.</p>');
  }
}

function renderMarketSummary(data){
  // Mood banner
  const mb=$('moodBanner');
  mb.className='mood-banner';
  setText('moodLabel', data.overall_mood||'—');
  setText('moodDesc', data.mood_description||'');
  setText('moodTime', 'As of '+data.as_of);
  show('moodBanner');

  // Index cards
  const cards = data.indices||[];
  setHTML('indexCards', cards.map(idx => {
    if(idx.error) return `<div class="index-card"><div class="index-name">${idx.flag} ${idx.name}</div><div class="empty-text">Data unavailable</div></div>`;
    const d = idx.change_day||0;
    const mcolor = scoreColor(idx.momentum_score||50);
    return `<div class="index-card" onclick="quickAnalyze('${idx.ticker}')">
      <div class="index-card-header"><div><div class="index-name">${idx.flag} ${idx.name}</div><div style="font-size:.72rem;color:#8b949e;">${idx.ticker}</div></div></div>
      <div class="index-price">${formatNum(idx.price)}</div>
      <div class="index-change ${colorClass(d)}">${d>=0?'+':''}${d.toFixed(2)}% today</div>
      <div class="index-meta">
        <span class="index-chip">${idx.regime}</span>
        <span class="index-chip" style="color:${mcolor}">Momentum: ${(idx.momentum_score||0).toFixed(0)}</span>
      </div>
    </div>`;
  }).join(''));

  // Generate narratives for each index
  loadIndexNarratives(cards.map(i=>i.ticker).filter(t=>t&&!t.includes('error')));
}

async function loadIndexNarratives(tickers){
  const container = $('indexNarratives');
  for(const ticker of tickers){
    const card = document.createElement('div');
    card.className = 'index-narrative-card';
    card.innerHTML = `<div class="in-header"><span class="in-ticker">${ticker}</span><span style="font-size:.75rem;color:#8b949e;">Generating summary...</span></div><div class="in-text">...</div>`;
    container.appendChild(card);

    try {
      const res = await fetch('/api/narrative',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticker,period_years:1})});
      const data = await res.json();
      card.querySelector('.in-header').innerHTML = `<span class="in-ticker">${ticker}</span>`;
      card.querySelector('.in-text').textContent = data.narrative||'';
    } catch(e){
      card.querySelector('.in-text').textContent = 'Could not generate summary.';
    }
  }
}

function quickAnalyze(ticker){
  $('tickerInput').value = ticker;
  switchTab('analyze');
  runAnalysis();
}

/* ══════════════════════════════════════════════════════════
   PORTFOLIO TAB
══════════════════════════════════════════════════════════ */

async function loadPortfolio(){
  show('portfolioLoading');
  hide('portfolioEmpty'); hide('portfolioSummary'); hide('portfolioFlags');
  setHTML('holdingsGrid','');

  try {
    const res = await fetch('/api/portfolio');
    const data = await res.json();
    hide('portfolioLoading');
    renderPortfolio(data);
  } catch(e){
    hide('portfolioLoading');
    show('portfolioEmpty');
  }
}

function renderPortfolio(data){
  const {holdings, summary} = data;

  // Update tab badge
  const cnt = $('portfolioCount');
  if(holdings.length>0){ cnt.textContent=holdings.length; show('portfolioCount'); }
  else { hide('portfolioCount'); }

  if(!holdings || holdings.length===0){
    show('portfolioEmpty');
    return;
  }

  // Summary strip
  if(summary){
    const sym = '₹'; // Mixed portfolios — show raw
    const pnlColor = summary.total_pnl>=0?'var(--green)':'var(--red)';
    setHTML('portfolioSummary',`
      <div class="ps-item"><div class="ps-label">Total Invested</div><div class="ps-value">${formatNum(summary.total_invested)}</div></div>
      <div class="ps-item"><div class="ps-label">Current Value</div><div class="ps-value">${formatNum(summary.total_current)}</div></div>
      <div class="ps-item"><div class="ps-label">Total P&L</div><div class="ps-value" style="color:${pnlColor}">${summary.total_pnl>=0?'+':''}${formatNum(summary.total_pnl)}</div></div>
      <div class="ps-item"><div class="ps-label">Return</div><div class="ps-value" style="color:${pnlColor}">${summary.total_pnl_pct>=0?'+':''}${summary.total_pnl_pct.toFixed(2)}%</div></div>
      <div class="ps-item"><div class="ps-label">Portfolio Momentum</div><div class="ps-value" style="color:${scoreColor(summary.portfolio_momentum)}">${summary.portfolio_momentum.toFixed(0)}/100</div></div>
      <div class="ps-item"><div class="ps-label">Holdings</div><div class="ps-value">${summary.stock_count}</div></div>
    `);
    show('portfolioSummary');

    // Risk flags
    if(summary.risk_flags?.length>0){
      setHTML('portfolioFlags', summary.risk_flags.map(f=>`<div class="flag-item">${f}</div>`).join(''));
      show('portfolioFlags');
    }
  }

  // Holdings
  setHTML('holdingsGrid', holdings.map(h=>{
    const pnl = h.pnl||0;
    const pnlPct = h.pnl_pct||0;
    const mc = scoreColor(h.momentum_score||50);
    const rc = {green:'var(--green)',lightgreen:'var(--green)',red:'var(--red)',orange:'var(--orange)',gray:'var(--text-muted)'}[h.regime_color]||'var(--text-muted)';
    return `<div class="holding-card">
      <div class="holding-left">
        <div class="holding-name">${h.company_name||h.ticker}</div>
        <div class="holding-ticker">${h.ticker} · ${h.quantity} shares @ ${formatNum(h.buy_price)}</div>
        <div class="holding-meta">
          <span class="holding-chip" style="background:${tagBg(h.regime_color||'gray')};color:${rc}">${h.regime||'—'}</span>
          <span class="holding-chip" style="background:rgba(255,255,255,.05);color:${mc}">Momentum: ${(h.momentum_score||0).toFixed(0)}</span>
          ${h.buy_date?`<span class="holding-chip" style="background:var(--bg3);color:var(--text-muted)">${h.buy_date}</span>`:''}
        </div>
      </div>
      <div class="holding-right">
        <div class="holding-pnl ${colorClass(pnl)}">${pnl>=0?'+':''}${formatNum(pnl)}</div>
        <div class="holding-pnl-pct ${colorClass(pnlPct)}">${pnlPct>=0?'+':''}${pnlPct.toFixed(2)}%</div>
        <div class="holding-price">Current: ${formatNum(h.current_price)}</div>
        <div class="holding-actions">
          <button class="holding-action-btn" onclick="quickAnalyze('${h.resolved_ticker||h.ticker}')">Analyze</button>
          <button class="holding-action-btn" onclick="removeHolding('${h.ticker}')">Remove</button>
        </div>
      </div>
    </div>`;
  }).join(''));
}

async function removeHolding(ticker){
  if(!confirm(`Remove ${ticker} from portfolio?`)) return;
  await fetch(`/api/portfolio/${ticker}`,{method:'DELETE'});
  loadPortfolio();
}

/* ── Add Holding Modal ── */
function openAddHolding(){
  if(currentTicker) $('holdingTicker').value = currentTicker;
  $('holdingDate').value = new Date().toISOString().split('T')[0];
  hide('holdingError');
  show('addHoldingModal');
}

async function submitAddHolding(){
  const ticker = $('holdingTicker').value.trim();
  const qty = parseFloat($('holdingQty').value);
  const price = parseFloat($('holdingPrice').value);
  const date = $('holdingDate').value;
  const notes = $('holdingNotes').value;

  if(!ticker){ showFormError('holdingError','Please enter a ticker.'); return; }
  if(!qty||qty<=0){ showFormError('holdingError','Please enter a valid quantity.'); return; }
  if(!price||price<=0){ showFormError('holdingError','Please enter a valid buy price.'); return; }

  try {
    const res = await fetch('/api/portfolio/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticker,quantity:qty,buy_price:price,buy_date:date,notes})});
    if(!res.ok){ const e=await res.json(); throw new Error(e.detail); }
    closeModal('addHoldingModal');
    switchTab('portfolio');
    loadPortfolio();
  } catch(e){ showFormError('holdingError',e.message||'Failed to add. Check ticker.'); }
}

/* ══════════════════════════════════════════════════════════
   ALERTS TAB
══════════════════════════════════════════════════════════ */

async function loadAlerts(){
  try {
    const res = await fetch('/api/alerts');
    const data = await res.json();
    renderAlerts(data.alerts||[], data.history||[]);
  } catch(e){}
}

async function checkAlerts(){
  show('alertsLoading');
  try {
    const res = await fetch('/api/alerts/check');
    const data = await res.json();
    hide('alertsLoading');

    // Update badge
    const badge = $('alertsBadge');
    if(data.triggered_count>0){ badge.textContent='!'; show('alertsBadge'); }
    else hide('alertsBadge');

    // Re-render all
    const allAlerts = [...(data.triggered||[]),...(data.watching||[]),...(data.paused||[])];
    renderAlerts(allAlerts, []);

    if(data.triggered_count>0){
      const tSection = $('triggeredSection');
      show('triggeredSection');
      setHTML('triggeredList', (data.triggered||[]).map(a=>`
        <div class="alert-card triggered">
          <div class="alert-left">
            <div class="alert-ticker">${a.ticker}</div>
            <div class="alert-message">${a.trigger_message||''}</div>
            <div class="alert-current">Price: ${formatNum(a.current_price)} · RSI: ${(a.current_rsi||0).toFixed(1)} · Momentum: ${(a.current_momentum||0).toFixed(0)}</div>
            <div class="alert-time">Triggered: ${a.triggered_at||''}</div>
          </div>
          <div class="alert-right"><button class="alert-delete-btn" onclick="deleteAlert('${a.id}')">Dismiss</button></div>
        </div>`).join(''));
    }
  } catch(e){ hide('alertsLoading'); }
}

function renderAlerts(alerts, history){
  const watching = alerts.filter(a=>a.active!==false);
  const badge = $('alertsBadge');
  const triggered = watching.filter(a=>a.triggered);
  if(triggered.length>0){ badge.textContent='!'; show('alertsBadge'); }

  if(watching.length===0){
    setHTML('watchingList','<p class="empty-text">No active alerts. Click "+ New Alert" to add one.</p>');
  } else {
    setHTML('watchingList', watching.map(a=>{
      const typeLabels={'price_above':'Price above','price_below':'Price below','rsi_above':'RSI above','rsi_below':'RSI below','regime_change':'Regime change','momentum_below':'Momentum below','momentum_above':'Momentum above'};
      const val = a.value!=null?` ${formatNum(a.value)}`:'';
      return `<div class="alert-card ${a.triggered?'triggered':''}">
        <div class="alert-left">
          <div class="alert-ticker">${a.ticker}</div>
          <div class="alert-type">${typeLabels[a.type]||a.type}${val}${a.notes?' · '+a.notes:''}</div>
          ${a.trigger_message?`<div class="alert-message">${a.trigger_message}</div>`:''}
          <div class="alert-current">Current Price: ${formatNum(a.current_price)||'—'} · RSI: ${a.current_rsi?a.current_rsi.toFixed(1):'—'}</div>
        </div>
        <div class="alert-right">
          <div class="alert-time">${a.created_at?.split('T')[0]||''}</div>
          <button class="alert-delete-btn" onclick="deleteAlert('${a.id}')">Delete</button>
        </div>
      </div>`;
    }).join(''));
  }

  if(history?.length>0){
    show('alertHistorySection');
    setHTML('alertHistoryList', history.map(h=>`<div class="history-item"><strong>${h.ticker}</strong> — ${h.message} <span style="float:right">${h.triggered_at?.split('.')[0]||''}</span></div>`).join(''));
  }
}

async function deleteAlert(id){
  await fetch(`/api/alerts/${id}`,{method:'DELETE'});
  loadAlerts();
}

/* ── Add Alert Modal ── */
function openAddAlert(){
  if(currentTicker) $('alertTicker').value = currentTicker;
  hide('alertError');
  toggleAlertValue();
  show('addAlertModal');
}

function toggleAlertValue(){
  const t = $('alertType').value;
  const grp = $('alertValueGroup');
  const lbl = $('alertValueLabel');
  if(t==='regime_change'){ hide('alertValueGroup'); return; }
  show('alertValueGroup');
  const labels={'price_above':'Target Price (e.g. 2500)','price_below':'Target Price (e.g. 2000)','rsi_below':'RSI threshold (e.g. 30)','rsi_above':'RSI threshold (e.g. 70)','momentum_below':'Momentum score (e.g. 30)','momentum_above':'Momentum score (e.g. 70)'};
  setText('alertValueLabel', labels[t]||'Value');
}

async function submitAddAlert(){
  const ticker = $('alertTicker').value.trim();
  const type = $('alertType').value;
  const value = type!=='regime_change' ? parseFloat($('alertValue').value) : null;
  const notes = $('alertNotes').value;

  if(!ticker){ showFormError('alertError','Please enter a ticker.'); return; }
  if(type!=='regime_change' && (!value||isNaN(value))){ showFormError('alertError','Please enter a valid value.'); return; }

  try {
    const res = await fetch('/api/alerts/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticker,alert_type:type,value,notes})});
    if(!res.ok){ const e=await res.json(); throw new Error(e.detail); }
    closeModal('addAlertModal');
    switchTab('alerts');
    loadAlerts();
  } catch(e){ showFormError('alertError',e.message||'Failed to create alert.'); }
}

/* ── Shared modal/form helpers ── */
function closeModal(id){ hide(id); }
function showFormError(id,msg){ const e=$(id); e.textContent=msg; show(id); }

/* ══════════════════════════════════════════════════════════
   MARKET CLOCKS + SEARCH AUTOCOMPLETE + INIT
══════════════════════════════════════════════════════════ */
function updateMarketClocks(){
  const clocks=$('marketClocks'); if(!clocks) return;
  const now=new Date(), utc=now.getTime()+now.getTimezoneOffset()*60000;
  const ist=new Date(utc+5.5*3600000), est=new Date(utc-5*3600000);
  const istH=ist.getHours(),istM=ist.getMinutes();
  const estH=est.getHours(),estM=est.getMinutes();
  const isWE=now.getDay()===0||now.getDay()===6;
  const nseOpen=!isWE&&(istH>9||(istH===9&&istM>=15))&&(istH<15||(istH===15&&istM<=30));
  const nyseOpen=!isWE&&estH>=9&&(estH>9||estM>=30)&&estH<16;
  clocks.innerHTML=`<div class="clock-chip">🇮🇳 NSE <span class="${nseOpen?'open':'closed'}">${nseOpen?'🟢 Open':'⚫ Closed'}</span></div><div class="clock-chip">🇺🇸 NYSE <span class="${nyseOpen?'open':'closed'}">${nyseOpen?'🟢 Open':'⚫ Closed'}</span></div>`;
}

let searchDebounce=null;
function setupSearch(){
  const input=$('tickerInput'), sugg=$('suggestions');
  if(!input||!sugg) return;
  input.addEventListener('input',()=>{
    clearTimeout(searchDebounce);
    const q=input.value.trim();
    if(q.length<2){ hide('suggestions'); return; }
    searchDebounce=setTimeout(async()=>{
      try {
        const res=await fetch(`/api/search?q=${encodeURIComponent(q)}`);
        const data=await res.json();
        if(data.suggestions?.length>0){
          sugg.innerHTML=data.suggestions.map(s=>`<div class="suggestion-item" onclick="pickSuggestion('${s.symbol}')"><div style="display:flex;flex-direction:column;gap:2px;"><span class="suggestion-sym">${s.symbol} <small style="color:#8b949e;font-weight:400;">${s.exchange||''}</small></span><span class="suggestion-name" style="font-size:.78rem;">${s.query||''}</span></div></div>`).join('');
          show('suggestions');
        } else hide('suggestions');
      } catch{ hide('suggestions'); }
    },300);
  });
  document.addEventListener('click',e=>{ if(!e.target.closest('.input-wrapper')) hide('suggestions'); });
}

function pickSuggestion(sym){ $('tickerInput').value=sym; hide('suggestions'); runAnalysis(); }

/* ══════════════════════════════════════════════════════════
   USER MENU
══════════════════════════════════════════════════════════ */

function toggleUserDropdown(){
  const dd = $('userDropdown');
  dd?.classList.toggle('hidden');
}

// Close dropdown when clicking anywhere outside
document.addEventListener('click', e => {
  if (!e.target.closest('.user-menu')) {
    $('userDropdown')?.classList.add('hidden');
  }
});

function doLogout(){
  localStorage.removeItem('niveshai_token');
  localStorage.removeItem('niveshai_user');
  window.location.href = '/';
}

function loadUserMenu(){
  const token = localStorage.getItem('niveshai_token');
  const raw   = localStorage.getItem('niveshai_user');

  if(!token || !raw){
    // Not authenticated — show Sign In link
    hide('userMenu');
    show('guestMenu');
    return;
  }

  try {
    const user = JSON.parse(raw);
    if(!user || !user.full_name) throw new Error('bad user');

    // Populate header trigger
    $('userAvatar').textContent = user.avatar_initials || '?';
    $('userName').textContent   = user.full_name.split(' ')[0];

    // Populate dropdown
    $('udAvatar').textContent   = user.avatar_initials || '?';
    $('udName').textContent     = user.full_name;
    $('udEmail').textContent    = user.email;
    $('udRisk').textContent     = '⚡ ' + (user.risk_profile || 'moderate') + ' investor';

    show('userMenu');
    hide('guestMenu');

    // Verify token is still valid in the background (silent refresh)
    fetch('/api/auth/me', { headers:{ 'Authorization':'Bearer '+token } })
      .then(r => {
        if(r.status === 401){
          // Token expired — log out silently
          localStorage.removeItem('niveshai_token');
          localStorage.removeItem('niveshai_user');
          hide('userMenu');
          show('guestMenu');
        }
      })
      .catch(() => {}); // offline — keep showing as logged in

  } catch {
    // Corrupted data — clear and show Sign In
    localStorage.removeItem('niveshai_token');
    localStorage.removeItem('niveshai_user');
    hide('userMenu');
    show('guestMenu');
  }
}

/* ══════════════════════════════════════════════════════════
   SETTINGS MODAL
══════════════════════════════════════════════════════════ */

let _settingsRisk = 'moderate';

function openSettings(){
  // Pre-fill with current user data
  const raw = localStorage.getItem('niveshai_user');
  if(raw){
    try {
      const u = JSON.parse(raw);
      $('set-name').value = u.full_name || '';
      $('settingsAvatar').textContent  = u.avatar_initials || '?';
      $('settingsFullName').textContent = u.full_name || '—';
      $('settingsEmail').textContent    = u.email || '—';
      _settingsRisk = u.risk_profile || 'moderate';
      selectSettingsRisk(_settingsRisk, false);
    } catch {}
  }
  // Reset tabs to profile
  switchSettingsTab('profile');
  // Clear all feedback messages
  ['profile-success','profile-error','pass-success','pass-error','delete-error'].forEach(id => {
    hide(id); const el=$(id); if(el) el.textContent='';
  });
  ['set-cur-pass','set-new-pass','set-confirm-pass','delete-password'].forEach(id => {
    const el=$(id); if(el) el.value='';
  });
  $('delete-confirm-cb') && ($('delete-confirm-cb').checked = false);
  toggleDeleteBtn();
  showDeleteStep1();
  show('settingsModal');
}

function closeSettings(){
  hide('settingsModal');
}

function switchSettingsTab(name){
  ['profile','security','danger'].forEach(t => {
    $('stab-'+t)?.classList.remove('active');
    hide('stab-content-'+t);
  });
  $('stab-'+name)?.classList.add('active');
  show('stab-content-'+name);
}

const RISK_DESCS = {
  conservative: 'Capital preservation first, minimal risk exposure',
  moderate:     'Balanced approach — growth and safety combined',
  aggressive:   'Maximum growth focus, comfortable with higher risk',
};

function selectSettingsRisk(val, save=true){
  _settingsRisk = val;
  ['conservative','moderate','aggressive'].forEach(r => {
    $('rpill-'+r)?.classList.toggle('active', r === val);
  });
  if($('risk-pill-desc')) $('risk-pill-desc').textContent = RISK_DESCS[val] || '';
}

/* ── Save Profile ── */
async function saveProfile(){
  const name = $('set-name').value.trim();
  hide('profile-success'); hide('profile-error');

  if(!name){ showSettingsError('profile-error','Name cannot be empty.'); return; }

  const token = localStorage.getItem('niveshai_token');
  if(!token){ window.location.href='/auth'; return; }

  try {
    const res = await fetch('/api/auth/profile', {
      method: 'PUT',
      headers: { 'Content-Type':'application/json', 'Authorization':'Bearer '+token },
      body: JSON.stringify({ full_name: name, risk_profile: _settingsRisk }),
    });
    const data = await res.json();
    if(!res.ok){ showSettingsError('profile-error', data.detail || 'Update failed.'); return; }

    // Update localStorage
    const u = JSON.parse(localStorage.getItem('niveshai_user') || '{}');
    u.full_name        = data.user.full_name;
    u.avatar_initials  = data.user.avatar_initials;
    u.risk_profile     = data.user.risk_profile;
    localStorage.setItem('niveshai_user', JSON.stringify(u));

    // Refresh header
    loadUserMenu();

    // Update settings display
    $('settingsAvatar').textContent  = data.user.avatar_initials;
    $('settingsFullName').textContent = data.user.full_name;
    show('profile-success');
    setTimeout(() => hide('profile-success'), 3000);
  } catch {
    showSettingsError('profile-error', 'Server error. Please try again.');
  }
}

/* ── Change Password ── */
async function changePassword(){
  const cur     = $('set-cur-pass').value;
  const newPass = $('set-new-pass').value;
  const confirm = $('set-confirm-pass').value;
  hide('pass-success'); hide('pass-error');

  if(!cur || !newPass || !confirm){ showSettingsError('pass-error','Please fill in all fields.'); return; }
  if(newPass.length < 6){ showSettingsError('pass-error','New password must be at least 6 characters.'); return; }
  if(newPass !== confirm){ showSettingsError('pass-error','New passwords do not match.'); return; }

  const token = localStorage.getItem('niveshai_token');
  try {
    const res = await fetch(`/api/auth/change-password?current_password=${encodeURIComponent(cur)}&new_password=${encodeURIComponent(newPass)}`, {
      method: 'PUT',
      headers: { 'Authorization': 'Bearer '+token },
    });
    const data = await res.json();
    if(!res.ok){ showSettingsError('pass-error', data.detail || 'Failed to change password.'); return; }

    show('pass-success');
    $('set-cur-pass').value = '';
    $('set-new-pass').value = '';
    $('set-confirm-pass').value = '';
    setTimeout(() => hide('pass-success'), 3000);
  } catch {
    showSettingsError('pass-error','Server error. Please try again.');
  }
}

/* ── Delete Account — two-step ── */
function showDeleteStep1(){
  show('delete-step1');
  hide('delete-step2');
}

function showDeleteStep2(){
  hide('delete-step1');
  show('delete-step2');
  $('delete-password')?.focus();
}

function toggleDeleteBtn(){
  const checked = $('delete-confirm-cb')?.checked;
  const btn = $('deleteAccountBtn');
  if(btn) btn.disabled = !checked;
}

async function deleteAccount(){
  const password = $('delete-password')?.value;
  hide('delete-error');

  if(!password){ showSettingsError('delete-error','Please enter your password.'); return; }
  if(!$('delete-confirm-cb')?.checked){ showSettingsError('delete-error','Please check the confirmation box.'); return; }

  const token = localStorage.getItem('niveshai_token');
  if(!token){ window.location.href='/auth'; return; }

  const btn = $('deleteAccountBtn');
  btn.textContent = 'Deleting...';
  btn.disabled = true;

  try {
    const res = await fetch(`/api/auth/account?password=${encodeURIComponent(password)}`, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer '+token },
    });
    const data = await res.json();

    if(!res.ok){
      showSettingsError('delete-error', data.detail || 'Deletion failed.');
      btn.textContent = '🗑️ Delete My Account Forever';
      toggleDeleteBtn();
      return;
    }

    // Clear local storage and redirect to landing
    localStorage.removeItem('niveshai_token');
    localStorage.removeItem('niveshai_user');
    closeSettings();
    // Show goodbye message briefly before redirect
    document.body.innerHTML = `
      <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0d1117;color:#e6edf3;font-family:sans-serif;text-align:center;padding:24px;">
        <div>
          <div style="font-size:3rem;margin-bottom:16px;">👋</div>
          <h2 style="color:#58a6ff;margin-bottom:10px;">Account Deleted</h2>
          <p style="color:#8b949e;">Your NiveshAI account and all data have been permanently deleted.</p>
          <p style="color:#8b949e;margin-top:8px;">Redirecting you to the home page...</p>
        </div>
      </div>`;
    setTimeout(() => window.location.href = '/', 3000);
  } catch {
    showSettingsError('delete-error','Server error. Please try again.');
    btn.textContent = '🗑️ Delete My Account Forever';
    toggleDeleteBtn();
  }
}

/* ── Toggle password visibility ── */
function togglePassField(id){
  const el = $(id);
  if(el) el.type = el.type === 'password' ? 'text' : 'password';
}

/* ── Settings error helper ── */
function showSettingsError(id, msg){
  const el = $(id);
  if(el){ el.textContent = msg; show(id); }
}

// Run immediately — don't wait for DOM. Prevents flash of "Sign In" when logged in.
loadUserMenu();

document.addEventListener('DOMContentLoaded',()=>{
  updateMarketClocks();
  setInterval(updateMarketClocks,60000);
  setupSearch();
  $('tickerInput')?.addEventListener('keydown',e=>{ if(e.key==='Enter') runAnalysis(); });
  const params=new URLSearchParams(window.location.search);
  const auto=params.get('ticker');
  if(auto){ $('tickerInput').value=auto.toUpperCase(); if(params.get('period')) $('periodSelect').value=params.get('period'); runAnalysis(); }
  // Load portfolio count on startup
  fetch('/api/portfolio').then(r=>r.json()).then(d=>{ if(d.holdings?.length>0){ $('portfolioCount').textContent=d.holdings.length; show('portfolioCount'); } }).catch(()=>{});
  // Check alerts on startup
  fetch('/api/alerts').then(r=>r.json()).then(d=>{ const t=(d.alerts||[]).filter(a=>a.triggered); if(t.length>0){ $('alertsBadge').textContent='!'; show('alertsBadge'); } }).catch(()=>{});
});
