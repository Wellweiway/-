const Costs=(function(){
const fl=x=>Math.floor(x+1e-9);
const amt=(p,s)=>Math.round(p*100)*s/100;
function fee(a,p){return a>0?Math.max(p.minFee,fl(a*p.rate*p.disc)):0}
function tax(a,p){return fl(a*p.tax)}
function trade(buy,sell,sh,p){
 const ba=amt(buy,sh),bf=fee(ba,p),bc=ba+bf;
 const sa=amt(sell,sh),sf=fee(sa,p),st=tax(sa,p),net=sa-sf-st;
 return {ba,bf,bc,sa,sf,st,net,pnl:net-bc,ret:bc>0?(net-bc)/bc:0};
}
function size(o,p){
 let c=Math.min(o.invest/o.buy,o.maxLoss/(o.buy-o.stop));
 if(o.maxPct)c=Math.min(c,o.capital*o.maxPct/100/o.buy);
 c=Math.floor(c/o.unit)*o.unit;
 const cap=o.maxPct?o.capital*o.maxPct/100:Infinity;
 const ok=n=>{const t=trade(o.buy,o.stop,n,p);return t.bc<=o.invest+1e-9&&-t.pnl<=o.maxLoss+1e-9&&t.bc<=cap+1e-9};
 while(c>0&&!ok(c))c-=o.unit;
 return Math.max(c,0);
}
return {fee,tax,trade,size,amt};
})();
if(typeof module!=='undefined')module.exports=Costs;
