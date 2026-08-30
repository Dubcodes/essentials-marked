import React,{useState}from'react';
import{api}from'../api';

export default function AccountPassword(){
  const[current,setCurrent]=useState('');
  const[next,setNext]=useState('');
  const[confirm,setConfirm]=useState('');
  const[message,setMessage]=useState('');
  const[busy,setBusy]=useState(false);

  const change=async()=>{
    try{
      setBusy(true);setMessage('');
      const result=await api('/auth/account/password',{
        method:'POST',
        body:JSON.stringify({
          current_password:current,
          new_password:next,
          confirm_new_password:confirm
        })
      });
      setCurrent('');setNext('');setConfirm('');
      setMessage(
        result.other_sessions_revoked
          ?`Password changed · ${result.other_sessions_revoked} other session${result.other_sessions_revoked===1?'':'s'} signed out`
          :'Password changed · this session remains signed in'
      );
    }catch(e:any){
      setMessage(e.message);
    }finally{
      setBusy(false);
    }
  };

  return(
    <details className="account-password">
      <summary>My account</summary>
      <div className="account-password-panel">
        <b>Change my password</b>
        <label>
          Current password
          <input type="password" autoComplete="current-password" value={current} onChange={e=>setCurrent(e.target.value)}/>
        </label>
        <label>
          New password
          <input type="password" autoComplete="new-password" value={next} onChange={e=>setNext(e.target.value)}/>
        </label>
        <label>
          Confirm new password
          <input type="password" autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)}/>
        </label>
        <button disabled={busy||!current||next.length<8||confirm!==next} onClick={()=>void change()}>
          {busy?'Changing…':'Change password'}
        </button>
        {message&&<small role="status">{message}</small>}
      </div>
    </details>
  );
}
