import React,{useRef,useState}from'react';
import{api}from'../api';

export function Login({parent,onDone}:{parent:boolean;onDone:()=>void}){
  const[id,setId]=useState(''),[secret,setSecret]=useState(''),[error,setError]=useState(''),[saving,setSaving]=useState(false);
  const idRef=useRef<HTMLInputElement>(null);
  const submit=async()=>{if(saving||!id.trim()||!secret)return;setSaving(true);setError('');try{await api('/auth/'+(parent?'parent':'admin')+'/login',{method:'POST',body:JSON.stringify(parent?{login:id.trim(),pin:secret}:{email:id.trim(),password:secret})});onDone()}catch(e:any){setError(e.message)}finally{setSaving(false)}};
  return <main className="login"><h1>Essentials <i>Marked</i></h1><form onSubmit={event=>{event.preventDefault();void submit()}}><label>{parent?'Family login':'Email'}<input ref={idRef} autoFocus autoComplete="username" value={id} onChange={event=>setId(event.target.value)}/></label><label>{parent?'6-digit PIN':'Password'}<input autoComplete="current-password" type="password" value={secret} onChange={event=>setSecret(event.target.value)}/></label><button type="submit" disabled={saving||!id.trim()||!secret}>{saving?'Signing in…':'Sign in'}</button></form>{error&&<p className="error">{error}</p>}</main>;
}
