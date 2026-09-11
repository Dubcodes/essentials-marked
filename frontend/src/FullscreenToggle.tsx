import React,{useEffect,useState}from'react';

export function useFullscreen(){
  const[active,setActive]=useState(Boolean(document.fullscreenElement));
  useEffect(()=>{const changed=()=>setActive(Boolean(document.fullscreenElement));document.addEventListener('fullscreenchange',changed);return()=>document.removeEventListener('fullscreenchange',changed)},[]);
  const toggle=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen?.();else await document.documentElement.requestFullscreen?.()}catch{/* Browser policy may reject fullscreen; leave the screen usable. */}};
  return{active,toggle};
}

export function FullscreenToggle(){
  const{active,toggle}=useFullscreen();
  return <button type="button" className={active?'minor fullscreen-toggle fullscreen-exit':'fullscreen-toggle fullscreen-enter'} onClick={()=>void toggle()}>{active?'Exit full screen':'⛶ Full screen'}</button>;
}
