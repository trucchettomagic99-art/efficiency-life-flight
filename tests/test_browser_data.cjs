const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('src/app.html','utf8');
const section = source.slice(source.indexOf('const IDX_BY_O = {}'), source.indexOf('/* Il punteggio arriva con la riga'));
const row = {o:'FCO',d:'MAN',p:50,dep:'2027-01-08',ret:'2027-01-11',sc:70};
function context(fetch){
  const c={IDX:{deals:[row],shards:{FCO:'/data/origins/FCO-123.json'}},
    PL:{FCO:{},MAN:{}},S:{origins:new Set(['FCO']),liveRows:[]},fetch,AbortSignal,Date};
  vm.createContext(c);vm.runInContext(section,c);return c;
}
(async()=>{
  let calls=0;
  const c=context(async()=>{calls++;return {ok:true,json:async()=>({schema:2,origin:'FCO',deals:[row,{...row,ret:'2027-01-10',p:60}]})};});
  await vm.runInContext('Promise.all([fetchDates(),fetchDates()])',c);
  assert.equal(calls,1,'same origin in flight is coalesced');
  assert.equal(vm.runInContext('rawPool().length',c),2,'both returns preserved');
  c.S.liveRows=[{...row,p:80,live:true}];
  assert.equal(vm.runInContext('rawPool().length',c),2,'LIVE does not erase alternatives');
  assert.equal(vm.runInContext('rawPool().find(r=>r.ret==="2027-01-11").p',c),80,'fresh price rise replaces old cheap offer');
  c.S.origins=new Set(['MAN']);
  assert.equal(vm.runInContext('rawPool().length',c),0,'late response cannot change selection');
  const offline=context(async()=>{throw new Error('offline');});
  await vm.runInContext('fetchDates()',offline);
  assert.equal(vm.runInContext('rawPool().length',offline),1,'embedded fallback survives');
  const invalid=context(async()=>({ok:true,json:async()=>({schema:2,origin:'WRONG',deals:[row]})}));
  await vm.runInContext('fetchDates()',invalid);
  assert.equal(vm.runInContext('Object.keys(DATE_BY_O).length',invalid),0,'foreign shard rejected');
  console.log('OK: date loading, coalescing, fallback, LIVE merge and selection isolation');
})().catch(e=>{console.error(e);process.exitCode=1;});
