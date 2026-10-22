(() => {
const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); try { tg.setHeaderColor('#080a12'); tg.setBackgroundColor('#080a12'); } catch(e){} }
const $ = id => document.getElementById(id);
const state = {user:null, game:'crash', cashout:1.5, picks:2, tab:'games', mode:localStorage.getItem('xzgift_mode')||'', crashTimer:null, crashStartedAt:0, crashBusy:false};
const initData = tg?.initData || '';
async function api(path, options={}) {
  const response = await fetch(path, {method:options.method||'GET',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},body:options.body?JSON.stringify(options.body):undefined});
  const data = await response.json().catch(()=>({error:'پاسخ سرور قابل خواندن نیست.'}));
  if (!response.ok) throw new Error(data.error || 'درخواست ناموفق بود.');
  return data;
}
function fa(n){return Number(n||0).toLocaleString('fa-IR')}
function toast(msg){$('toast').textContent=msg;$('toast').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').classList.remove('show'),2600)}
function renderUser(u){state.user=u;$('balance').textContent=fa(u.balance);$('level').textContent=fa(u.level);$('xp').textContent=fa(u.xp)+' XP';$('avatar').textContent=(u.first_name||'TB').slice(0,2)}
function setMode(mode){if(mode==='ton'){toast('حالت TON هنوز فعال نیست؛ فعلاً می‌تونی با سکه مجازی بازی کنی.');return}state.mode='virtual';localStorage.setItem('xzgift_mode','virtual');$('mode-gate').classList.add('dismissed');$('mode-gate').setAttribute('aria-hidden','true');$('mode-switch').textContent='🪙 سکه مجازی ▾';$('mode-switch').classList.remove('ton-mode');$('balance-caption').textContent='موجودی مجازی تو';$('game-disclaimer').textContent='این نسخه آزمایشی از سکه مجازی استفاده می‌کند؛ واریز و برداشت واقعی فعال نیست.';setTimeout(()=>$('mode-gate').style.display='none',260)}
$('choose-virtual').addEventListener('click',()=>setMode('virtual'));$('choose-ton').addEventListener('click',()=>setMode('ton'));$('mode-switch').addEventListener('click',()=>{const gate=$('mode-gate');gate.style.display='flex';requestAnimationFrame(()=>gate.classList.remove('dismissed'));gate.setAttribute('aria-hidden','false')});
if(state.mode==='virtual'){ $('mode-gate').style.display='none'; $('mode-gate').setAttribute('aria-hidden','true'); } else { $('mode-gate').classList.remove('dismissed'); }
function renderHistory(items){const el=$('history');if(!items?.length){el.innerHTML='<div class="empty">هنوز فعالیتی ثبت نشده.</div>';return}el.innerHTML=items.map(x=>{const positive=Number(x.amount)>=0;const icon=x.kind?.includes('spin')?'🎁':x.kind?.includes('crash')?'🚀':x.kind?.includes('mines')?'💣':'✦';return `<div class="history-row"><div class="history-icon">${icon}</div><div><b>${escapeHtml(x.note||x.kind||'تراکنش')}</b><small>${new Date(x.created_at).toLocaleString('fa-IR')}</small></div><strong class="${positive?'positive':'negative'}">${positive?'+':''}${fa(x.amount)}</strong></div>`}).join('')}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function refresh(){try{const d=await api('/api/me');renderUser(d.user);renderHistory(d.transactions)}catch(e){toast(e.message)}}
const gameMeta={crash:{title:'CRASH',symbol:'🚀',desc:'مبلغ بازی و ضریب خروج هدف رو انتخاب کن.',kicker:'ریسک و هیجان',bet:true,cashout:true},mines:{title:'MINES',symbol:'💣',desc:'تعداد انتخاب‌ها رو مشخص کن. این نسخه یک دور ساده‌شده است.',kicker:'با دقت انتخاب کن',bet:true,mines:true},spin:{title:'DAILY SPIN',symbol:'🎁',desc:'یک جایزه مجازی رایگان در هر روز؛ بدون هزینه.',kicker:'جایزه روزانه',bet:false},arena:{title:'ARENA',symbol:'⚔️',desc:'رقابت آنلاین در نسخه بعدی اضافه می‌شود.',kicker:'به‌زودی',bet:false,disabled:true}};
function openGame(game){stopCrashAnimation();state.game=game;const m=gameMeta[game];$('modal-symbol').textContent=m.symbol;$('modal-title').textContent=m.title;$('modal-desc').textContent=m.desc;$('modal-kicker').textContent=m.kicker;$('bet-controls').classList.toggle('hidden',!m.bet);$('cashout-controls').classList.toggle('hidden',!m.cashout);$('mines-controls').classList.toggle('hidden',!m.mines);$('result').classList.add('hidden');$('crash-live').classList.toggle('hidden',game!=='crash');$('cashout-now').classList.add('hidden');$('crash-live-status').textContent='برای شروع، مبلغ بازی را وارد کن.';$('crash-multiplier').textContent='1.00x';$('play').classList.toggle('hidden',game==='crash');$('play').disabled=!!m.disabled;$('play').innerHTML=m.disabled?'به‌زودی':'شروع بازی <span>←</span>';$('modal').classList.add('open');$('modal').setAttribute('aria-hidden','false');if(game==='crash')resumeCrash()}
function closeModal(){stopCrashAnimation();$('modal').classList.remove('open');$('modal').setAttribute('aria-hidden','true')}
document.querySelectorAll('.game-card').forEach(b=>b.addEventListener('click',()=>openGame(b.dataset.game)));
$('close').addEventListener('click',closeModal);$('modal').addEventListener('click',e=>{if(e.target===$('modal'))closeModal()});
document.querySelectorAll('[data-bet]').forEach(b=>b.addEventListener('click',()=>{$('bet').value=b.dataset.bet}));
$('cashout-down').onclick=()=>{state.cashout=Math.max(1.1,Math.round((state.cashout-.1)*10)/10);$('cashout-label').textContent=state.cashout.toFixed(2)+'x'};
$('cashout-up').onclick=()=>{state.cashout=Math.min(5,Math.round((state.cashout+.1)*10)/10);$('cashout-label').textContent=state.cashout.toFixed(2)+'x'};
$('picks-down').onclick=()=>{state.picks=Math.max(1,state.picks-1);$('picks-label').textContent=fa(state.picks)+' خانه'};
$('picks-up').onclick=()=>{state.picks=Math.min(5,state.picks+1);$('picks-label').textContent=fa(state.picks)+' خانه'};
function stopCrashAnimation(){if(state.crashTimer){clearInterval(state.crashTimer);state.crashTimer=null}state.crashBusy=false}
function paintCrash(multiplier){$('crash-multiplier').textContent=multiplier.toFixed(2)+'x';const progress=Math.min(100,Math.max(0,(multiplier-1)*18));$('crash-rocket').style.left=progress+'%';$('crash-rocket').style.bottom=(8+Math.min(55,progress*.55))+'%';$('crash-track-line').style.width=progress+'%'}
async function resumeCrash(){
 try{const d=await api('/api/game/crash/status');if(!d.active||state.game!=='crash'||!$('modal').classList.contains('open'))return;
 state.crashStartedAt=Date.now()-Number(d.elapsed||0)*1000;state.crashBusy=true;$('bet').value=d.bet;$('play').classList.add('hidden');$('cashout-now').classList.remove('hidden');$('cashout-now').disabled=false;$('crash-live-status').textContent='دور قبلی ادامه دارد؛ قبل از سقوط خارج شو!';paintCrash(Number(d.multiplier||1));
 state.crashTimer=setInterval(async()=>{if(!state.crashBusy)return;const elapsed=(Date.now()-state.crashStartedAt)/1000;paintCrash(Math.min(10,1+elapsed*.22+elapsed*elapsed*.025));try{const status=await api('/api/game/crash/status');if(!status.active&&status.status==='busted')finishCrash(status)}catch(e){}},250);
 }catch(e){}
}
async function startCrash(){
 const bet=Number($('bet').value);if(!Number.isInteger(bet)||bet<1||bet>10000)throw new Error('مبلغ باید بین ۱ تا ۱۰٬۰۰۰ سکه باشد.');
 const d=await api('/api/game/crash/start',{method:'POST',body:{bet}});renderUser(d.user);state.crashStartedAt=Date.now();state.crashBusy=true;
 $('play').classList.add('hidden');$('cashout-now').classList.remove('hidden');$('cashout-now').disabled=false;$('crash-live-status').textContent='دور در جریانه؛ قبل از سقوط خارج شو!';$('result').classList.add('hidden');paintCrash(1);
 state.crashTimer=setInterval(async()=>{if(!state.crashBusy)return;const elapsed=(Date.now()-state.crashStartedAt)/1000;const m=Math.min(10,1+elapsed*.22+elapsed*elapsed*.025);paintCrash(m);try{const status=await api('/api/game/crash/status');if(!status.active&&status.status==='busted'){finishCrash(status);}}catch(e){}},250);
}
function finishCrash(d){stopCrashAnimation();$('cashout-now').classList.add('hidden');$('play').classList.remove('hidden');$('play').disabled=false;$('play').innerHTML='بازی دوباره <span>↻</span>';paintCrash(Number(d.bust||d.multiplier||1));$('crash-live-status').textContent=d.status==='cashed_out'?'خروج موفق ثبت شد.':'سقوط! دور به پایان رسید.';$('result').textContent=d.message||'دور به پایان رسید.';$('result').classList.remove('hidden');if(d.user)renderUser(d.user);toast(d.message||'دور به پایان رسید.');refresh()}
$('cashout-now').addEventListener('click',async()=>{if(state.crashBusy===false)return;$('cashout-now').disabled=true;try{const d=await api('/api/game/crash/cashout',{method:'POST',body:{}});finishCrash(d)}catch(e){toast(e.message);$('cashout-now').disabled=false}});
$('play').addEventListener('click',async()=>{
 const m=gameMeta[state.game],btn=$('play');btn.disabled=true;$('result').classList.add('hidden');
 try{
  if(state.game==='spin'){const d=await api('/api/spin',{method:'POST',body:{}});renderUser(d.user);$('result').textContent=d.message;$('result').classList.remove('hidden');$('play').textContent='جایزه دریافت شد';toast(d.message);await refresh();return}
  if(state.game==='arena'){toast('این بازی در نسخه بعدی اضافه می‌شود.');return}
  if(state.game==='crash'){await startCrash();return}
  const bet=Number($('bet').value);if(!Number.isInteger(bet)||bet<1||bet>10000)throw new Error('مبلغ باید بین ۱ تا ۱۰٬۰۰۰ سکه باشد.');
  const d=await api('/api/game/'+state.game,{method:'POST',body:state.game==='crash'?{bet,cashout:state.cashout}:{bet,picks:state.picks}});
  renderUser(d.user);$('result').textContent=d.message+ (state.game==='crash'?` ضریب سقوط سرور: ${d.bust.toFixed(2)}x`:'');$('result').classList.remove('hidden');toast(d.message);await refresh();
 }catch(e){toast(e.message);$('result').textContent=e.message;$('result').classList.remove('hidden')}finally{if(!state.crashBusy){btn.disabled=false;if(state.game==='spin')btn.textContent='دریافت شد';else btn.innerHTML='شروع بازی <span>←</span>'}}
});
$('refresh').onclick=refresh;
document.querySelectorAll('.nav-item').forEach(b=>b.addEventListener('click',async()=>{
 document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x===b));state.tab=b.dataset.tab;
 if(state.tab==='games'){document.querySelector('.welcome').classList.remove('hidden');document.querySelector('.games-grid').classList.remove('hidden');document.querySelector('.promo-card').classList.remove('hidden');document.querySelector('.history-head').classList.remove('hidden');$('history').classList.remove('hidden')}
 if(state.tab==='leaderboard'){document.querySelector('.welcome').classList.add('hidden');document.querySelector('.games-grid').classList.add('hidden');document.querySelector('.promo-card').classList.add('hidden');document.querySelector('.history-head').classList.add('hidden');$('history').classList.remove('hidden');$('history').innerHTML='<div class="empty">در حال دریافت رتبه‌بندی…</div>';try{const d=await api('/api/leaderboard');$('history').innerHTML=d.items.map((x,i)=>`<div class="leader-row"><span class="rank">${fa(i+1)}</span><b>${escapeHtml(x.name)}</b><small>سطح ${fa(x.level)} · ${fa(x.balance)} سکه</small></div>`).join('')}catch(e){toast(e.message)}}
 if(state.tab==='profile'){document.querySelector('.welcome').classList.add('hidden');document.querySelector('.games-grid').classList.add('hidden');document.querySelector('.promo-card').classList.add('hidden');document.querySelector('.history-head').classList.add('hidden');$('history').classList.remove('hidden');const u=state.user;$('history').innerHTML=`<div class="promo-card"><div class="promo-icon">👤</div><div><b>${escapeHtml(u?.first_name||'کاربر')}</b><p>شناسه تلگرام: ${fa(u?.id)}<br>سطح ${fa(u?.level)} · ${fa(u?.xp)} امتیاز تجربه</p></div></div><div class="empty">این نسخه از سکه‌های مجازی آزمایشی استفاده می‌کند.</div>`}
}));
refresh();
})();