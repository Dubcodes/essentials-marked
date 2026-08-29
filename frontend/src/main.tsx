import React,{useEffect,useState}from'react';import{createRoot}from'react-dom/client';import{api}from'./api';import Classroom from'./classroom/Classroom';import PairTablet from'./classroom/Pair';import ParentView from'./parent/Parent';import AdminConsole from'./admin/AdminConsole';import{ErrorBoundary}from'./ErrorBoundary';import'./style.css';import'./classroom.css';import'./admin.css';import'./emergency.css';import'./branding.css';
type Child={id:string;first_name:string;last_name:string};const icons:Record<string,string>={nappy:'🚽',toilet:'🚻',food:'🍽',sunscreen:'☀',sleep:'😴',medicine:'💊',incident:'⚠',staff_note:'📝'};
function Login({parent,onDone}:{parent:boolean;onDone:()=>void}){const[id,setId]=useState(''),[secret,setSecret]=useState(''),[error,setError]=useState('');return <main className="login"><h1>Essentials <i>Marked</i></h1><label>{parent?'Family login':'Email'}<input autoComplete="username" value={id} onChange={e=>setId(e.target.value)}/></label><label>{parent?'6-digit PIN':'Password'}<input autoComplete="current-password" type="password" value={secret} onChange={e=>setSecret(e.target.value)}/></label><button disabled={!id||!secret} onClick={()=>api('/auth/'+(parent?'parent':'admin')+'/login',{method:'POST',body:JSON.stringify(parent?{login:id,pin:secret}:{email:id,password:secret})}).then(onDone).catch(e=>setError(e.message))}>Sign in</button>{error&&<p className="error">{error}</p>}</main>}
function Pair(){const[token,setToken]=useState(''),[challenge,setChallenge]=useState(''),[error,setError]=useState('');return <main className="login"><h1>Pair classroom tablet</h1><label>One-time token<input value={token} onChange={e=>setToken(e.target.value)}/></label><label>3-digit challenge<input value={challenge} onChange={e=>setChallenge(e.target.value)}/></label><button onClick={()=>api('/device/pair',{method:'POST',body:JSON.stringify({token,challenge})}).then(()=>location.assign('/classroom')).catch(e=>setError(e.message))}>Pair securely</button>{error&&<p className="error">{error}</p>}</main>}
function Parent(){const[data,setData]=useState<any>(),[child,setChild]=useState(''),[events,setEvents]=useState<any[]>([]),[login,setLogin]=useState(false),[note,setNote]=useState('');useEffect(()=>{void api('/parent/me').then(x=>{setData(x);setChild(x.children[0]?.id)}).catch(()=>setLogin(true))},[]);useEffect(()=>{if(child)void api('/parent/children/'+child+'/timeline').then(setEvents)},[child]);if(login)return <Login parent onDone={()=>location.reload()}/>;if(!data)return <main className="loading">Loading daily record…</main>;return <main className="parent"><header><strong>Essentials <i>Marked</i></strong><span>{data.centre}</span></header><nav>{data.children.map((c:Child)=><button key={c.id} className={c.id===child?'active':''} onClick={()=>setChild(c.id)}>{c.first_name}</button>)}</nav><h1>Today’s essentials</h1><section className="timeline">{events.map(e=><article key={e.id}><span className="eventicon">{icons[e.type]||'•'}</span><time>{new Date(e.effective_at).toLocaleTimeString('en-NZ',{hour:'numeric',minute:'2-digit'})}</time><div><b>{e.type.replaceAll('_',' ')}</b><p>{Object.values(e.data).filter(Boolean).join(' · ')||'Recorded'} {e.room&&' · '+e.room}</p></div></article>)}</section><a href={'/api/parent/children/'+child+'/export'}>Download CSV record</a><section className="note"><h2>Note for the teachers</h2><textarea value={note} onChange={e=>setNote(e.target.value)}/><button onClick={()=>api('/parent/notes',{method:'POST',body:JSON.stringify({child_id:child,body:note})}).then(()=>setNote(''))}>Send note</button></section></main>}
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
function Admin(){const[data,setData]=useState<any>(),[login,setLogin]=useState(false),[events,setEvents]=useState<any[]>([]),[pair,setPair]=useState<any>();useEffect(()=>{void api('/admin/bootstrap').then(setData).catch(()=>setLogin(true))},[]);useEffect(()=>{if(data)void api('/admin/events').then(setEvents)},[data]);if(login)return <Login parent={false} onDone={()=>location.reload()}/>;if(!data)return <main className="loading">Opening administration…</main>;return <main className="admin"><header><strong>Essentials <i>Marked</i></strong><span>{data.centre.name} administration</span><button onClick={()=>api('/admin/pairings',{method:'POST',body:JSON.stringify({room_id:data.rooms[0]?.id,label:'Classroom tablet'})}).then(setPair)}>Add classroom tablet</button></header><div className="adminbody"><aside><b>Operations</b><a>Dashboard</a><a>Rooms</a><a>Children</a><a>Families</a><a>Staff</a><a>Devices</a><a>Records</a><a>Audit log</a></aside><section><h1>Recent records</h1><div className="cards"><div><b>{data.children.length}</b> children</div><div><b>{data.rooms.length}</b> rooms</div><div><b>{data.devices.length}</b> devices</div></div>{pair&&<div className="pair"><h2>Pairing challenge</h2><code>{pair.token}</code><h1>{pair.challenge}</h1></div>}<table><thead><tr><th>Time</th><th>Child</th><th>Record</th><th>Performed by</th></tr></thead><tbody>{events.map(e=><tr key={e.id}><td>{new Date(e.effective_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</td><td>{e.child.first_name}</td><td>{e.type}</td><td>{e.performed_by}</td></tr>)}</tbody></table></section></div></main>}
if('serviceWorker'in navigator)window.addEventListener('load',()=>void navigator.serviceWorker.register('/sw.js'));
function AdminGate(){const[state,setState]=useState<'loading'|'ready'|'login'>('loading');useEffect(()=>{void api('/admin/bootstrap').then(()=>setState('ready')).catch(()=>setState('login'))},[]);if(state==='loading')return <main className="loading">Opening administration…</main>;if(state==='login')return <Login parent={false} onDone={()=>location.reload()}/>;return <AdminConsole/>}
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

function QuickNav(){
  const current=location.pathname;

  const links=[
    ['Admin','/'],
    ['Classroom','/classroom'],
    ['Parent','/parent'],
    ['Pair tablet','/classroom/pair']
  ] as const;

  return(
    <nav
      className="quick-nav"
      aria-label="Quick navigation"
    >
      {links.map(([label,href])=>{
        const active=
          href==='/'
            ? current==='/'||current.startsWith('/admin')
            : current===href;

        return(
          <a
            key={href}
            href={href}
            className={active?'active':''}
          >
            {label}
          </a>
        );
      })}
    </nav>
  );
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
            :path==='/parent'
              ?<ParentRoute/>
              :<AdminGate/>
      }
    </ErrorBoundary>

    <QuickNav/>
    <VersionMarker/>
  </>
);
