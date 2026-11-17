(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const escape = x => String(x ?? '').replace(/[&<>"']/g,c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeLink = s => {
    try { const u=new URL(String(s||''));return u.protocol==='https:' && (['www.jstage.jst.go.jp','jstage.jst.go.jp','doi.org','academic.oup.com','muse.jhu.edu'].includes(u.hostname)) ? u.href : ''; }
    catch {return '';}
  };
  let items=[], tax={families:[]}, meta={};
  const state={q:'',concept:'',language:'',year:'',journal:'',sort:'discovered',savedOnly:false,limit:18};
  let saved=new Set();
  try {saved=new Set(JSON.parse(localStorage.getItem('curio-paper:saved')||'[]'));} catch{}
  const save=()=>{try{localStorage.setItem('curio-paper:saved',JSON.stringify([...saved]));}catch{}};
  const uniq=xs=>[...new Set(xs.filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b),'ja'));
  const options=(id,values,text)=>{$(id).innerHTML=`<option value="">${escape(text)}</option>`+values.map(t=>`<option value="${escape(t)}">${escape(t)}</option>`).join('');};
  function initData(){
    $('stat-total').textContent=items.length;
    $('stat-concepts').textContent=tax.families.length||18;
    if(meta.updated_at){const d=new Date(meta.updated_at);$('last-update').textContent=d.toLocaleDateString('ja-JP',{timeZone:'Asia/Tokyo'});$('update-note').textContent=`前回追加 ${meta.new_last_run||0}件 · 取得成功 ${meta.sources_ok||0}誌 · 取得失敗 ${meta.sources_failed||0}誌`;}
    else {$('last-update').textContent='初回更新前';$('update-note').textContent='新着RSSの定期確認';}
    options('year',uniq(items.map(p=>p.published)).reverse(),'すべての年');
    options('journal',uniq(items.map(p=>p.journal)),'すべての掲載誌');
    options('concept',tax.families.map(f=>f.label),'すべての概念');
    $('concept-grid').innerHTML=tax.families.map((f,i)=>`<button class="concept-card" type="button" data-topic="${escape(f.label)}"><small>NO. ${String(i+1).padStart(2,'0')} / CONCEPT</small><span class="concept-arrow">↗</span><strong>${escape(f.label)}</strong><span>${escape((f.core||[]).slice(0,2).join(' · '))}</span></button>`).join('');
    render();
  }
  const searchHaystack=p=>[p.title,(p.authors||[]).join(' '),p.journal,p.doi,(p.tags||[]).join(' '),(p.matched_terms||[]).join(' ')].join(' ').toLocaleLowerCase();
  function filtered(){
    const a=items.filter(p=>(!state.q||searchHaystack(p).includes(state.q.toLocaleLowerCase()))&&(!state.concept||(p.tags||[]).includes(state.concept))&&(!state.language||(p.language||'ja')===state.language)&&(!state.year||p.published===state.year)&&(!state.journal||p.journal===state.journal)&&(!state.savedOnly||saved.has(p.id)));
    a.sort((x,y)=>state.sort==='score'? (y.score||0)-(x.score||0):state.sort==='publication'? String(y.published).localeCompare(String(x.published)):state.sort==='title'?String(x.title).localeCompare(String(y.title),'ja'):String(y.discovered_at||'').localeCompare(String(x.discovered_at||''))||(y.score||0)-(x.score||0));
    return a;
  }
  let visible=[];
  function makeCard(p,i){
    const labels=(p.tags||[]).slice(0,2).map(t=>`<span class="card-tag">${escape(t)}</span>`).join('');
    return `<article class="book-card paper-card">
      <div class="card-cover paper-cover"><span class="cover-issue">RESEARCH / ${escape(p.published||'DATE UNKNOWN')}</span><span class="cover-title">${escape(p.title)}</span><span class="cover-footer">ARS · SCIENTIA · MIRABILIA</span></div>
      <div class="card-info"><div class="card-kicker"><span>自動発見候補 · ${escape(p.language==='en'?'EN':'JA')}</span><span>一致度 ${Number(p.score)||0}</span></div>
      <h3 class="card-title">${escape(p.title)}</h3><p class="card-sub">${escape((p.authors||[]).join(' / ')||'著者情報未取得')}<br>${escape(p.journal)} ${escape(p.published||'')}</p>
      <div class="card-tags">${labels}</div><div class="card-actions"><button type="button" class="card-open" data-view="${i}">論文情報を見る ↗</button><button type="button" class="save-button" data-save="${escape(p.id)}" aria-label="あとで見るに保存">${saved.has(p.id)?'★':'☆'}</button></div>
      </div></article>`;
  }
  function render(){
    visible=filtered();$('result-count').textContent=visible.length;
    const empty=visible.length===0;
    $('empty-state').hidden=!empty;$('book-grid').hidden=empty;
    if(empty){$('empty-title').textContent=items.length?'条件に合う論文が見つかりません。':'航路は、まだ白紙です。';$('empty-description').textContent=items.length?'検索語・掲載誌・概念を変更してください。':'初期登録論文は0件です。定期RSS確認で条件に合う研究論文が見つかると、ここに追加されます。';}
    $('book-grid').innerHTML=visible.slice(0,state.limit).map(makeCard).join('');
    $('loadbar').hidden=empty||visible.length<=state.limit;
    $('toggle-saved').setAttribute('aria-pressed',String(state.savedOnly));
  }
  function openDetail(idx){
    const p=visible[idx];if(!p)return;
    const rows=[['著者',(p.authors||[]).join(' / ')||'未取得'],['言語（論文メタデータ）',p.language==='en'?'English':'日本語'],['掲載誌',p.journal||'未取得'],['公開年',p.published||'不明'],['DOI',p.doi||'記録なし'],['概念',(p.tags||[]).join(' / ')],['一致した語',(p.matched_terms||[]).join(' / ')],['自動評価',String(p.score||0)],['発見日',p.discovered_at||'—'],['情報源',p.source||p.provider||'学術誌 RSS']];
    const link=safeLink(p.url);
    const host=link?new URL(link).hostname:'';
    const linkText=host==='muse.jhu.edu'?'Project MUSEで論文情報を見る':host==='academic.oup.com'?'Oxford Academicで論文情報を見る':host==='doi.org'?'DOIから論文情報を見る':'J-STAGEで論文情報を見る';
    $('detail-content').innerHTML=`<div class="dialog-kicker">CURIO PAPER ATLAS / RESEARCH NOTE</div><h3 id="detail-title">${escape(p.title)}</h3><p class="dialog-desc">論題・書誌情報をもとに自動分類された候補です。本文を読んだ上での評価や査読保証ではありません。論文の公開範囲は掲載元で確認してください。</p><div class="dialog-meta">${rows.map(r=>`<span class="dialog-label">${escape(r[0])}</span><span>${escape(r[1])}</span>`).join('')}</div>${link?`<a class="dialog-link" href="${escape(link)}" target="_blank" rel="noopener noreferrer">${escape(linkText)} ↗</a>`:''}`;
    const dlg=$('detail-dialog'); if(typeof dlg.showModal==='function')dlg.showModal();else dlg.setAttribute('open','');
  }
  function clear(){state.q='';state.concept='';state.language='';state.year='';state.journal='';state.savedOnly=false;state.limit=18;for(const id of ['q','concept','language','year','journal'])$(id).value='';render();}
  async function load(){
    try{
      const [a,b]=await Promise.all([fetch('./data/papers.json',{cache:'no-cache'}),fetch('./data/taxonomy.json',{cache:'no-cache'})]);
      if(!a.ok||!b.ok)throw new Error('Data not available');
      const d=await a.json(); tax=await b.json();items=Array.isArray(d.papers)?d.papers:[];meta=d.meta||{};initData();
    }catch(e){
      if(location.protocol==='file:'){const d=JSON.parse($('inline-preview').textContent);tax=d.taxonomy;items=d.papers;meta=d.meta;initData();return;}
      $('empty-state').hidden=false;$('empty-title').textContent='データが読み込めませんでした。';$('empty-description').textContent='GitHub Actionsの実行とPagesの設定を確認してください。';
    }
  }
  $('q').addEventListener('input',e=>{state.q=e.target.value.trim();state.limit=18;render()});
  for(const k of ['concept','language','year','journal','sort']) $(k).addEventListener('change',e=>{state[k]=e.target.value;state.limit=18;render();});
  $('reset-filters').addEventListener('click',clear);
  $('toggle-saved').addEventListener('click',()=>{state.savedOnly=!state.savedOnly;render();});
  $('load-more').addEventListener('click',()=>{state.limit+=18;render();});
  $('book-grid').addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(b){openDetail(Number(b.dataset.view));return;}const s=e.target.closest('[data-save]');if(s){const id=s.dataset.save;if(saved.has(id))saved.delete(id);else saved.add(id);save();render();}});
  $('concept-grid').addEventListener('click',e=>{const b=e.target.closest('[data-topic]');if(b){clear();state.concept=b.dataset.topic;$('concept').value=state.concept;render();$('discovery').scrollIntoView({behavior:'smooth'});}});
  $('close-dialog').addEventListener('click',()=>$('detail-dialog').close());
  $('detail-dialog').addEventListener('click',e=>{if(e.target===$('detail-dialog'))$('detail-dialog').close();});
  load();
})();
