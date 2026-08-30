import React from'react';
import{api}from'../api';
import AccountPassword from'./AccountPassword';

export default function TeacherLanding({account}:{account:any}){
  return <main className="login">
    <h1>Essentials <i>Marked</i></h1>
    <p>{account.centre_name||'Centre'} · signed in as {account.email}</p>
    <h2>Teacher account</h2>
    <p>Classroom device pairing remains separate from your Account sign-in.</p>
    <a className="button-link" href="/classroom">Open Classroom</a>
    <AccountPassword/>
    <button className="minor" onClick={()=>void api('/auth/account/logout',{method:'POST'}).finally(()=>location.reload())}>Sign out</button>
  </main>;
}
