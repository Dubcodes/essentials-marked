import React,{useState}from'react';
import{api}from'../api';

export default function PairTablet(){
  const[token,setToken]=useState(()=>new URLSearchParams(location.search).get('token')||'');
  const[challenge,setChallenge]=useState('');const[error,setError]=useState('');
  const submit=()=>api('/device/pair',{method:'POST',body:JSON.stringify({token,challenge})}).then(()=>location.assign('/classroom')).catch(e=>setError(e.message));
  return <main className="login"><h1>Pair classroom tablet</h1><p>Confirm the device name and room shown by the administrator, then enter the three-digit challenge.</p><form onSubmit={event=>{event.preventDefault();if(token&&challenge.length===3)void submit()}}><label>One-time token<input value={token} onChange={e=>setToken(e.target.value)}/></label><label>3-digit challenge<input autoFocus inputMode="numeric" maxLength={3} value={challenge} onChange={e=>setChallenge(e.target.value.replace(/\D/g,''))}/></label><button type="submit" disabled={!token||challenge.length!==3}>Pair securely</button></form>{error&&<p className="error">{error}</p>}</main>;
}
