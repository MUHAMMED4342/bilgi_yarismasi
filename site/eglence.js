/* Bilgi Yarışması - eğlence katmanı (masaüstü uygulamasındaki eglence.py ile aynı kurallar).
   Puan, seri, rütbe, başarım, günlük meydan okuma, arkadaşa sor, seyirciye sor, çok oyunculu. */
const EG=(()=>{
"use strict";
const MODE_NAMES={klasik:"Klasik",can:"Can modu",gunluk:"Günün meydan okuması",coklu:"Çok oyunculu"};
const MODE_RULES={klasik:[10,1],can:[15,3],gunluk:[10,2]};   /* soru sayısı, can */
const SPARE=3,PER_PLAYER=5,MAX_PLAYERS=4;

/* ---------- rastgele sayı (günlük meydan okuma masaüstüyle birebir aynı sorular) ---------- */
function mulberry32(seed){let a=seed>>>0;return()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296}}
function makeRng(rand){
  return{
    random:rand,
    shuffle(a){for(let i=a.length-1;i>0;i--){const j=Math.floor(rand()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a},
    sample(pool,k){const a=pool.slice(),n=a.length;k=Math.min(k,n);for(let i=0;i<k;i++){const j=i+Math.floor(rand()*(n-i));[a[i],a[j]]=[a[j],a[i]]}return a.slice(0,k)},
    pick(a){return a[Math.floor(rand()*a.length)]}
  };
}
const rngDefault=()=>makeRng(Math.random);
function dailySeed(d){d=d||new Date();return d.getFullYear()*10000+(d.getMonth()+1)*100+d.getDate()}
const rngDaily=d=>makeRng(mulberry32(dailySeed(d)));

/* ---------- tarih ---------- */
const pad=n=>(n<10?"0":"")+n;
function todayStr(d){d=d||new Date();return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate())}
function yesterdayStr(d){d=d||new Date();return todayStr(new Date(d.getFullYear(),d.getMonth(),d.getDate()-1))}

/* ---------- rütbeler ---------- */
const RANKS=[[0,"Çaylak"],[400,"Meraklı"],[1200,"Bilgiç"],[3000,"Uzman"],[6000,"Üstat"],[10000,"Bilge"],[16000,"Efsane"]];
function rankInfo(xp){
  let idx=0;RANKS.forEach((r,i)=>{if(xp>=r[0])idx=i});
  if(idx+1<RANKS.length)return{name:RANKS[idx][1],next:RANKS[idx+1][1],left:RANKS[idx+1][0]-xp,idx};
  return{name:RANKS[idx][1],next:null,left:0,idx};
}
function rankLine(p){
  const r=rankInfo(p.xp);
  return r.next?`Rütben: ${r.name}, ${p.xp} puan. ${r.next} rütbesine ${r.left} puan kaldı.`:`Rütben: ${r.name}, ${p.xp} puan. En yüksek rütbedesin!`;
}

/* ---------- profil (tarayıcıda saklanır) ---------- */
const DEFAULT_PROFILE=()=>({xp:0,oyun:0,dogru:0,soru:0,rekorlar:{},seri:0,gun_seri:0,son_gun:"",gunluk_tarih:"",gunluk_puan:0,kat:{},basarim:[]});
function loadProfile(){
  const p=DEFAULT_PROFILE();
  try{const raw=JSON.parse(localStorage.getItem("by_profil")||"null");if(raw&&typeof raw==="object")Object.assign(p,raw)}catch(e){}
  if(!p.rekorlar||typeof p.rekorlar!=="object")p.rekorlar={};
  if(!p.kat||typeof p.kat!=="object")p.kat={};
  if(!Array.isArray(p.basarim))p.basarim=[];
  ["xp","oyun","dogru","soru","seri","gun_seri","gunluk_puan"].forEach(k=>{p[k]=Number.isFinite(+p[k])?Math.trunc(+p[k]):0});
  return p;
}
function saveProfile(p){try{localStorage.setItem("by_profil",JSON.stringify(p))}catch(e){}}
function currentDayStreak(p,d){const t=todayStr(d);return(p.son_gun===t||p.son_gun===yesterdayStr(d))?p.gun_seri:0}
function dailyPlayed(p,d){return p.gunluk_tarih===todayStr(d)}

/* ---------- puanlama ---------- */
function scoreQuestion(elapsed,window_,streak,half,friend,audience){
  const base=Math.max(30,100-(half?40:0)-(friend?30:0)-(audience?20:0));
  const frac=window_?Math.max(0,1-elapsed/window_):0;
  const speed=Math.round(50*frac);
  const bonus=10*Math.min(Math.max(streak-1,0),6);
  return{base,speed,bonus,total:base+speed+bonus};
}
const GOOD_LINES=["Doğru cevap!","Harika!","Tam isabet!","Bildin!","Muhteşem!","Çok iyi gidiyorsun!","Şahane!","Aferin!"];
const BAD_LINES=["Yanlış.","Eyvah, yanlış.","Olmadı, yanlış.","Maalesef yanlış.","Yazık, yanlış."];
const TIMEOUT_LINES=["Süre doldu.","Zaman bitti.","Eyvah, süre doldu."];
const STREAK_LINES={3:"Isınıyorsun! 3'lü seri.",5:"Ateş aldın! 5'li seri.",7:"Durdurulamıyorsun! 7'li seri.",10:"Efsane gidiyorsun! 10'lu seri.",15:"Bu artık rekor kokuyor! 15'li seri."};
const STREAK_SOUND_AT=[3,5,7,10,15];
const streakLine=n=>STREAK_LINES[n]||(n>=3?n+"'li seri.":"");
const pickOf=a=>a[Math.floor(Math.random()*a.length)];

/* ---------- arkadaşa sor ---------- */
/* [ad, açılış cümlesi, iyi bildiği kategoriler, zayıf olduğu kategoriler] */
const FRIENDS=[
 ["Kankan Mehmet","Ooo sürpriz telefon! Dur bir bakayım.",["Spor","Müzik","Sinema"],["Edebiyat","Felsefe ve Mantık","Matematik"]],
 ["Teyzem","Aman yavrum, ben bunu televizyonda görmüştüm!",["Yemek ve Mutfak","Tıp ve Sağlık","Dil ve Kültür"],["Teknoloji","Matematik","Astronomi"]],
 ["Dayım","Ben bu işlerden anlarım, dinle beni.",["Tarih","Coğrafya","Ekonomi","Hukuk ve Siyaset"],["Sanat","Müzik","Teknoloji"]],
 ["Komşu Fatma Abla","Çayı koymuştum ama neyse, hemen söyleyeyim.",["Yemek ve Mutfak","Doğa","Dil ve Kültür"],["Teknoloji","Hukuk ve Siyaset","Matematik"]],
 ["Kuzenim Ece","Aaa tam dün bunu okumuştum!",["Sanat","Edebiyat","Psikoloji","Sinema"],["Spor","Ekonomi"]],
 ["Arkadaşım Burak","Alo, müsaitim, söyle bakalım.",["Teknoloji","Bilim","Keşifler ve İcatlar"],["Edebiyat","Sanat"]],
 ["Öğretmenim Ayşe Hanım","Bak şimdi evladım, dikkatle dinle.",["Edebiyat","Tarih","Dil ve Kültür","Mitoloji"],["Spor","Teknoloji"]],
 ["Ablam Zeynep","Hayırdır, yine mi yarışma? Neyse, sor bakalım.",["Tıp ve Sağlık","Psikoloji","Doğa"],["Ekonomi","Hukuk ve Siyaset"]],
 ["İş arkadaşım Murat","Toplantıdayım ama iki dakikam var.",["Ekonomi","Teknoloji","Hukuk ve Siyaset"],["Doğa","Mitoloji"]],
 ["Babam","Hah, aradığın iyi oldu, bunu biliyorum galiba.",["Tarih","Coğrafya","Spor","Arkeoloji"],["Teknoloji","Sinema"]],
 ["Annem","Canım benim, hemen düşünüyorum.",["Yemek ve Mutfak","Müzik","Tıp ve Sağlık"],["Teknoloji","Matematik"]],
 ["Eski sınıf arkadaşım Cem","Vay be, kaç yıl oldu! Hadi sor bakalım.",["Matematik","Astronomi","Felsefe ve Mantık","Bilim"],["Yemek ve Mutfak","Spor"]]
];
function confidenceWords(p){
  if(p>=0.85)return"Yüzde doksan eminim.";
  if(p>=0.65)return"Yüzde yetmiş eminim.";
  if(p>=0.5)return"Yarı yarıya eminim.";
  return"Pek emin değilim ama içime öyle doğdu.";
}
function friendHint(rightIdx,available,category){
  const f=pickOf(FRIENDS);
  let prob=[[0.82,3],[0.68,4],[0.5,3]];
  let r=Math.random()*10,acc=0,base=0.5;
  for(const [pr,w] of prob){acc+=w;if(r<acc){base=pr;break}}
  prob=base;let note="";
  if(f[2].includes(category)){prob=Math.min(0.97,prob+0.12);note="Bu benim alanım!"}
  else if(f[3].includes(category)){prob=Math.max(0.3,prob-0.15);note="Bu konuda pek iyi değilimdir ama bir deneyeyim."}
  const wrong=available.filter(k=>k!==rightIdx);
  const knows=Math.random()<prob||!wrong.length;
  const idx=knows?rightIdx:pickOf(wrong);
  return{name:f[0],intro:f[1],note,level:confidenceWords(prob),idx,right:idx===rightIdx};
}

/* ---------- seyirciye sor ---------- */
function audiencePoll(rightIdx,available){
  const avail=available.slice();if(!avail.includes(rightIdx))avail.push(rightIdx);
  const k=avail.length;if(k===1)return{[rightIdx]:100};
  const u=(a,b)=>a+Math.random()*(b-a);
  const lead=k===2?u(0.55,0.88):u(0.45,0.80);
  const misled=Math.random()<0.15;
  const top=misled?pickOf(avail.filter(a=>a!==rightIdx)):rightIdx;
  const others=avail.filter(a=>a!==top),rest=1-lead;
  const w=others.map(()=>Math.random()+0.15),ws=w.reduce((a,b)=>a+b,0);
  const shares={[top]:lead};
  others.forEach((a,i)=>{shares[a]=rest*w[i]/ws});
  if(Math.max(...others.map(a=>shares[a]))>lead*0.9)others.forEach(a=>{shares[a]=rest/others.length});
  const raw={},out={};let sum=0;
  avail.forEach(a=>{raw[a]=shares[a]*100;out[a]=Math.floor(raw[a]);sum+=out[a]});
  let left=100-sum;
  avail.slice().sort((a,b)=>(raw[b]-out[b])-(raw[a]-out[a])).slice(0,left).forEach(a=>{out[a]++});
  return out;
}

/* ---------- oyuncu isimleri ---------- */
function cleanNames(raw){
  const out=[];
  raw.forEach((nm,i)=>{
    let n=String(nm||"").split(/\s+/).filter(Boolean).join(" ").slice(0,20)||("Oyuncu "+(i+1));
    const base=n;let c=2;
    while(out.some(x=>x.toLowerCase()===n.toLowerCase()))n=base+" "+(c++);
    out.push(n);
  });
  return out;
}

/* ---------- soru ve oyun ---------- */
function toQ(p){return{cat:p[0],q:p[1],opts:p[2],ans:p[3],exp:p[4]||""}}
const cmpQ=(a,b)=>a.q<b.q?-1:a.q>b.q?1:a.ans-b.ans;
function prepQ(q,rng){
  const o=rng.shuffle(q.opts.map((t,i)=>({t,c:i===q.ans,gone:false})));
  return{cat:q.cat,q:q.q,o,e:q.exp,half:false,audience:false,friend:null,friendRight:true};
}
function newPlayer(name){return{name,joker:true,friend:true,audience:true,swap:true,jokersUsed:0,score:0,correct:0,answered:0,streak:0,best:0}}
function newGame(pool,o){
  const rng=o.rng,names=(o.players&&o.players.length)?o.players:[""];
  const spareN=Math.max(SPARE,names.length);
  const picks=rng.sample(pool,Math.min(o.n+spareN,pool.length));
  const qs=picks.slice(0,o.n).map(q=>prepQ(q,rng));
  const spares=picks.slice(o.n).map(q=>prepQ(q,rng));
  return{mode:o.mode,qs,spares,n:qs.length,i:0,lock:false,limit:o.limit||0,tm:null,deadline:0,
    players:names.map(newPlayer),cur:0,lives:o.lives,livesLost:0,
    qStart:0,elapsed:0,remAtPick:null,fastest:null,lastSec:false,fooledRight:false,
    cats:{},over:false,finished:false,saved:false};
}
function summary(g){
  const p=g.players[0];
  return{mode:g.mode,n:g.n,correct:p.correct,answered:p.answered,score:p.score,bestStreak:p.best,jokers:p.jokersUsed,
    fastest:g.fastest,lastSec:g.lastSec,fooledRight:g.fooledRight,finished:g.finished,cats:g.cats};
}

/* ---------- başarımlar ---------- */
const ACHIEVEMENTS=[
 ["ilk","İlk Adım","İlk oyununu bitir.",(c,p)=>p.oyun>=1],
 ["kusursuz","Kusursuz","Hiç yanlış yapmadan en az 10 soruluk bir oyunu bitir.",(c,p)=>c.n>=10&&c.correct===c.n],
 ["jokersiz","Jokersiz Kahraman","Hiç joker kullanmadan hatasız bir oyun bitir.",(c,p)=>c.n>=10&&c.correct===c.n&&c.jokers===0],
 ["seri7","Ateş Hattı","Üst üste 7 soru bil.",(c,p)=>c.bestStreak>=7],
 ["simsek","Şimşek","Bir soruyu 4 saniyeden kısa sürede doğru bil.",(c,p)=>c.fastest!==null&&c.fastest<4],
 ["son_saniye","Son Saniye","Süreli oyunda son 2 saniyede doğru cevap ver.",(c,p)=>c.lastSec],
 ["sagduyu","Kendine Güvenen","Arkadaşının yanlış yönlendirdiği bir soruyu yine de doğru bil.",(c,p)=>c.fooledRight],
 ["gunluk","Günün Kahramanı","Günün meydan okumasında en az 7 soru bil.",(c,p)=>c.mode==="gunluk"&&c.correct>=7],
 ["maraton","Maratoncu","Can modunda 15 sorunun hepsini bitir.",(c,p)=>c.mode==="can"&&c.finished],
 ["bin","Bin Puan","Tek oyunda 1000 puan topla.",(c,p)=>c.score>=1000],
 ["muddavim","Müdavim","10 oyun bitir.",(c,p)=>p.oyun>=10],
 ["aliskanlik","Alışkanlık","3 gün üst üste oyna.",(c,p)=>p.gun_seri>=3],
 ["usta","Alanında Usta","Aynı kategoride toplam 20 doğru cevap ver.",(c,p)=>Object.values(p.kat).some(v=>v[0]>=20)]
];
function applyResult(p,c,d){
  const t=todayStr(d),oldRank=rankInfo(p.xp).idx,mode=c.mode;
  p.oyun++;p.dogru+=c.correct;p.soru+=c.answered;p.xp+=c.score;
  const oldRecord=+p.rekorlar[mode]||0,newRecord=c.score>oldRecord;
  if(newRecord)p.rekorlar[mode]=c.score;
  const newStreakRecord=c.bestStreak>p.seri;if(newStreakRecord)p.seri=c.bestStreak;
  if(p.son_gun===t){}else if(p.son_gun===yesterdayStr(d))p.gun_seri++;else p.gun_seri=1;
  p.son_gun=t;
  if(mode==="gunluk"){
    if(p.gunluk_tarih===t)p.gunluk_puan=Math.max(p.gunluk_puan,c.score);
    else{p.gunluk_tarih=t;p.gunluk_puan=c.score}
  }
  Object.keys(c.cats).forEach(cat=>{const v=p.kat[cat]||(p.kat[cat]=[0,0]);v[0]+=c.cats[cat][0];v[1]+=c.cats[cat][1]});
  const newAch=[];
  ACHIEVEMENTS.forEach(a=>{if(!p.basarim.includes(a[0])&&a[3](c,p)){p.basarim.push(a[0]);newAch.push([a[1],a[2]])}});
  const r=rankInfo(p.xp);
  return{oldRecord,newRecord:newRecord&&c.score>0,newStreakRecord:newStreakRecord&&c.bestStreak>=3,
    newRank:r.idx>oldRank?r.name:null,newAch,dayStreak:p.gun_seri};
}

/* ---------- metinler ---------- */
function statsLines(p,d){
  const L=[rankLine(p)];
  if(p.oyun){const pct=p.soru?Math.round(100*p.dogru/p.soru):0;L.push(`Bitirilen oyun: ${p.oyun}. Doğru cevap: ${p.dogru} / ${p.soru} (yüzde ${pct}).`)}
  else L.push("Henüz oyun bitirmedin.");
  const recs=["klasik","can","gunluk"].filter(m=>p.rekorlar[m]).map(m=>`${MODE_NAMES[m]} ${p.rekorlar[m]}`);
  L.push(recs.length?`Rekorlar: ${recs.join(", ")}.`:"Henüz rekorun yok.");
  L.push(`En uzun doğru serisi: ${p.seri}.`);
  const ds=currentDayStreak(p,d);
  L.push(ds?`Üst üste oynanan gün: ${ds}.`:"Günlük serin şu an yok. Bugün oyna, başlat!");
  L.push(dailyPlayed(p,d)?`Bugünün meydan okumasından ${p.gunluk_puan} puan aldın.`:"Günün meydan okuması seni bekliyor.");
  const cats=Object.keys(p.kat).filter(c=>p.kat[c][1]>=5).map(c=>[c,p.kat[c][0],p.kat[c][1]]);
  if(cats.length){
    const rate=x=>x[1]/x[2];
    const best=cats.reduce((a,b)=>(rate(b)>rate(a)||(rate(b)===rate(a)&&b[2]>a[2]))?b:a);
    const worst=cats.reduce((a,b)=>(rate(b)<rate(a)||(rate(b)===rate(a)&&b[2]>a[2]))?b:a);
    L.push(`En iyi kategorin: ${best[0]} (${best[1]} / ${best[2]} doğru).`);
    if(worst[0]!==best[0])L.push(`Çalışman gereken kategori: ${worst[0]} (${worst[1]} / ${worst[2]} doğru).`);
  }
  return L;
}
function achievementLists(p){
  return{got:ACHIEVEMENTS.filter(a=>p.basarim.includes(a[0])).map(a=>[a[1],a[2]]),
         lock:ACHIEVEMENTS.filter(a=>!p.basarim.includes(a[0])).map(a=>[a[1],a[2]]),total:ACHIEVEMENTS.length};
}

return{MODE_NAMES,MODE_RULES,SPARE,PER_PLAYER,MAX_PLAYERS,rngDefault,rngDaily,mulberry32,makeRng,dailySeed,todayStr,
  rankInfo,rankLine,loadProfile,saveProfile,currentDayStreak,dailyPlayed,scoreQuestion,
  GOOD_LINES,BAD_LINES,TIMEOUT_LINES,STREAK_SOUND_AT,streakLine,pickOf,friendHint,audiencePoll,cleanNames,
  toQ,cmpQ,newGame,summary,applyResult,statsLines,achievementLists,FRIENDS};
})();
