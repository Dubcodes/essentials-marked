import React,{createContext,useContext,useEffect,useId,useRef}from'react';

type Layer={token:symbol;depth:number;order:number};
const layers:Layer[]=[];
const LayerDepth=createContext(0);
let nextOrder=0;
const topLayer=()=>layers.reduce<Layer|undefined>((top,layer)=>!top||layer.depth>top.depth||(layer.depth===top.depth&&layer.order>top.order)?layer:top,undefined);

export function useDismissibleLayer(active:boolean,onClose:()=>void){
  const token=useRef(Symbol('dismissible-layer')),close=useRef(onClose),depth=useContext(LayerDepth);close.current=onClose;
  useEffect(()=>{
    if(!active)return;
    const current={token:token.current,depth,order:nextOrder++};layers.push(current);
    const key=(event:KeyboardEvent)=>{if(event.key==='Escape'&&topLayer()?.token===current.token){event.preventDefault();event.stopImmediatePropagation();close.current()}};
    window.addEventListener('keydown',key);
    return()=>{window.removeEventListener('keydown',key);const index=layers.indexOf(current);if(index>=0)layers.splice(index,1)};
  },[active,depth]);
  return token;
}

export function DismissibleOverlay({onClose,label,title,backdropClass='modal-backdrop',panelClass='',children}:{onClose:()=>void;label?:string;title?:string;backdropClass?:string;panelClass?:string;children:React.ReactNode}){
  const token=useDismissibleLayer(true,onClose);
  const titleId=useId();
  const depth=useContext(LayerDepth);
  return <div className={backdropClass} role="presentation" onClick={event=>{if(event.target===event.currentTarget&&topLayer()?.token===token.current)onClose()}}><section className={panelClass} role="dialog" aria-modal="true" aria-label={title?undefined:label} aria-labelledby={title?titleId:undefined}>{title&&<h2 id={titleId}>{title}</h2>}<LayerDepth.Provider value={depth+1}>{children}</LayerDepth.Provider></section></div>;
}
