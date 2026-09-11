import React,{useEffect,useState}from'react';import{createRoot}from'react-dom/client';import{api}from'./api';import Classroom from'./classroom/Classroom';import PairTablet from'./classroom/Pair';import ParentView from'./parent/Parent';import AttendanceKiosk from'./attendance/AttendanceKiosk';import AdminConsole from'./admin/AdminConsole';import TeacherLanding from'./account/TeacherLanding';import{Login}from'./account/Login';import{accountLandingForRole}from'./account/role-ui';import{ErrorBoundary}from'./ErrorBoundary';import'./style.css';import'./classroom.css';import'./admin.css';import'./emergency.css';import'./branding.css';
function ParentRoute(){
  const[state,setState]=useState<'loading'|'ready'|'login'>('loading');

  useEffect(()=>{
    void api('/parent/me')
      .then(()=>setState('ready'))
      .catch(()=>setState('login'));
  },[]);

  if(state==='loading'){
    return <main className="loading">Loading parent portal…</main>;
  }

  if(state==='login'){
    return <Login parent onDone={()=>location.reload()}/>;
  }

  return <ParentView/>;
}
if('serviceWorker'in navigator)window.addEventListener('load',()=>{void navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'}).then(registration=>{const check=()=>void registration.update().catch(()=>undefined);const announce=()=>window.dispatchEvent(new Event('build-update'));registration.addEventListener('updatefound',()=>{const worker=registration.installing;worker?.addEventListener('statechange',()=>{if(worker.state==='installed'&&navigator.serviceWorker.controller)announce()})});addEventListener('online',check);document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')check()});check()}).catch(()=>undefined)});
function Entry(){return <main className="login parent-first"><h1>Essentials <i>Marked</i></h1><p>Daily essentials for your centre.</p><a className="primary-link" href="/parent">Parent / whānau sign in</a><a className="secondary-link" href="/?staff=1">Staff / administration sign in</a></main>}
function AdminGate(){const[state,setState]=useState<'loading'|'ready'|'login'|'teacher'>('loading'),[account,setAccount]=useState<any>();useEffect(()=>{void api('/auth/account/me').then((value:any)=>{setAccount(value);setState(accountLandingForRole(value.role)==='teacher'?'teacher':'ready')}).catch(()=>setState('login'))},[]);if(state==='loading')return <main className="loading">Opening account…</main>;if(state==='login')return new URLSearchParams(location.search).get('staff')==='1'?<Login parent={false} onDone={()=>location.reload()}/>:<Entry/>;if(state==='teacher')return <TeacherLanding account={account}/>;return <AdminConsole/>}
function VersionMarker(){
  const built=new Date(__BUILD_TIME__);

  const stamp=new Intl.DateTimeFormat(
    'en-NZ',
    {
      day:'2-digit',
      month:'short',
      hour:'2-digit',
      minute:'2-digit',
      hour12:false
    }
  ).format(built);

  return(
    <div
      className="version-marker"
      aria-hidden="true"
    >
      EM v{__APP_VERSION__} · {stamp}
    </div>
  );
}

function BuildUpdate(){
  const[available,setAvailable]=useState(false);
  useEffect(()=>{const ready=()=>setAvailable(true);addEventListener('build-update',ready);return()=>removeEventListener('build-update',ready)},[]);
  return available?<button className="build-update minor" onClick={()=>location.reload()}>Update available</button>:null;
}

const path=location.pathname;

createRoot(
  document.getElementById('root')!
).render(
  <>
    <ErrorBoundary>
      {
        path==='/classroom'
          ?<Classroom/>
          :path==='/classroom/pair'
            ?<PairTablet/>
            :path==='/attendance'
              ?<AttendanceKiosk/>
            :path==='/parent'
              ?<ParentRoute/>
              :<AdminGate/>
      }
    </ErrorBoundary>

    <BuildUpdate/>
    <VersionMarker/>
  </>
);
