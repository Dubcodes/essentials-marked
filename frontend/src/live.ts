import{useEffect,useRef,useState}from'react';

export type LiveState='Live'|'Reconnecting'|'Offline';

/**
 * Signals are advisory only: callers refetch their normal authorised REST
 * resource.  Coalescing protects the bootstrap endpoints during write bursts;
 * foreground, online, reconnect and a 25-second interval cover missed events.
 */
export function useLiveReconciliation(refresh:()=>void|Promise<void>){
  const refreshRef=useRef(refresh);
  const timer=useRef<number>();
  const[state,setState]=useState<LiveState>(navigator.onLine?'Reconnecting':'Offline');
  useEffect(()=>{refreshRef.current=refresh},[refresh]);
  useEffect(()=>{
    let source:EventSource|undefined;
    let stopped=false;
    const reconcile=()=>{
      window.clearTimeout(timer.current);
      timer.current=window.setTimeout(()=>void Promise.resolve(refreshRef.current()).catch(()=>undefined),300);
    };
    const connect=()=>{
      if(stopped||!navigator.onLine)return;
      source?.close();
      setState('Reconnecting');
      source=new EventSource('/api/live');
      source.addEventListener('open',()=>{setState('Live');reconcile()});
      source.addEventListener('change',reconcile);
      source.addEventListener('reconcile',reconcile);
      source.addEventListener('error',()=>setState(navigator.onLine?'Reconnecting':'Offline'));
    };
    const online=()=>{setState('Reconnecting');reconcile();connect()};
    const offline=()=>{setState('Offline');source?.close()};
    const visible=()=>{if(document.visibilityState==='visible'){reconcile();connect()}};
    connect();
    addEventListener('online',online);addEventListener('offline',offline);document.addEventListener('visibilitychange',visible);
    const interval=window.setInterval(reconcile,25000);
    return()=>{stopped=true;source?.close();window.clearTimeout(timer.current);clearInterval(interval);removeEventListener('online',online);removeEventListener('offline',offline);document.removeEventListener('visibilitychange',visible)};
  },[]);
  return state;
}
