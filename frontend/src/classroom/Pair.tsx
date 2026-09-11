import React,{useState}from'react';
import{api}from'../api';

export default function PairTablet(){
  const[token,setToken]=useState(()=>new URLSearchParams(location.search).get('token')||'');
  const[challenge,setChallenge]=useState('');const[error,setError]=useState('');
  const submit=()=>api('/device/pair',{method:'POST',body:JSON.stringify({token,challenge})}).then((device:any)=>location.assign(device.mode==='attendance'?'/attendance':'/classroom')).catch(e=>setError(e.message));
  return <main className="login"><h1>Pair tablet</h1><p>Enter the three-word pairing code shown by the administrator, plus the separate three-digit challenge. Spaces, hyphens, and letter case are accepted.</p><form onSubmit={event=>{event.preventDefault();if(token&&challenge.length===3)void submit()}}><label>Three-word pairing code<input autoCapitalize="none" autoCorrect="off" placeholder="river lamp garden" value={token} onChange={e=>setToken(e.target.value)}/></label><label>3-digit challenge<input autoFocus inputMode="numeric" maxLength={3} value={challenge} onChange={e=>setChallenge(e.target.value.replace(/\D/g,''))}/></label><button type="submit" disabled={!token||challenge.length!==3}>Pair securely</button></form>{error&&<p className="error">{error}</p>}</main>;
}
