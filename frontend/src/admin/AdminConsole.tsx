import React,{useEffect,useMemo,useState}from'react';
import{api}from'../api';
import AccountPassword from'../account/AccountPassword';
import AccountsSettings from'../account/AccountsSettings';
import FamiliesManager from'./FamiliesManager';
import ActivityLog from'./ActivityLog';
import{managementPagesForRole,settingsSections,type AdminPage}from'../account/role-ui';

type Page=AdminPage;

type Notice=(message:string)=>void;

export default function AdminConsole(){
  const[data,setData]=useState<any>();
  const[page,setPage]=useState<Page>('Dashboard');
  const[activityChild,setActivityChild]=useState('');
  const[activityRecord,setActivityRecord]=useState<any>();

  const[pair,setPair]=useState<any>();
  const[pairState,setPairState]=useState('');
  const[seconds,setSeconds]=useState(0);
  const[label,setLabel]=useState('Classroom tablet');
  const[room,setRoom]=useState('');
  const[message,setMessage]=useState('');

  const load=async()=>{
    const boot=await api('/admin/bootstrap');
    setData(boot);
    setRoom((value:string)=>
      value||boot.rooms[0]?.id||''
    );
  };

  useEffect(()=>{
    void load();
  },[]);

  useEffect(()=>{
    if(!pair?.id)return;

    let stopped=false;

    const tick=async()=>{
      const expires=String(pair.expires_at);

      const expiresAt=new Date(
        /[zZ]|[+-]\d\d:\d\d$/.test(expires)
          ?expires
          :`${expires}Z`
      );

      const left=Math.max(
        0,
        Math.ceil(
          (expiresAt.getTime()-Date.now())/1000
        )
      );

      setSeconds(left);

      if(!left){
        setPairState(
          'Expired — generate a new pairing'
        );
        stopped=true;
        return;
      }

      const status=await api(
        `/admin/pairings/${pair.id}`
      ).catch(()=>null);

      if(status?.consumed_at){
        setPairState(
          `Paired successfully to ${label}`
        );
        stopped=true;
        void load();
      }
    };

    void tick();

    const timer=setInterval(()=>{
      if(stopped){
        clearInterval(timer);
        return;
      }

      void tick();
    },1000);

    return()=>{
      stopped=true;
      clearInterval(timer);
    };
  },[pair?.id]);

  if(!data){
    return(
      <main className="loading">
        Opening administration…
      </main>
    );
  }

  const brand=
    data.centre.display_name||
    'Essentials Marked';

  const present=data.children.filter(
    (x:any)=>x.present
  );

  const notice:Notice=(value)=>{
    setMessage(value);
    window.setTimeout(
      ()=>setMessage(''),
      6000
    );
  };
  const isAdmin=data.account?.role==='admin';
  const visiblePages=managementPagesForRole(data.account?.role);

  return(
    <main className="admin">
      <header>
        {data.centre.logo_url&&
          <img
            className="brand-logo"
            src={data.centre.logo_url}
            alt=""
          />
        }

        <strong>{brand}</strong>

        <span>
          {data.centre.secondary_text||
           data.centre.name} administration
        </span>

        <button
          className="minor"
          onClick={()=>
            void load()
              .then(()=>notice('Admin refreshed'))
              .catch((e:any)=>notice(e.message))
          }
        >
          ↻ Refresh
        </button>

        <button
          className="minor"
          onClick={()=>void api(
            '/auth/account/logout',
            {method:'POST'}
          ).finally(()=>location.reload())}
        >
          Sign out
        </button>
      </header>

      <div className="adminbody">
        <aside>
          <b>Operations</b>

          {visiblePages.map(item=>
            <button
              key={item}
              className={
                page===item
                  ?'active'
                  :'minor'
              }
              onClick={()=>setPage(item)}
            >
              {item}
            </button>
          )}
        </aside>

        <section>
          <h1>{page}</h1>

          {message&&
            <p
              role="status"
              className="notice"
            >
              {message}
            </p>
          }

          {page==='Dashboard'&&
            <>
              <section className="dashboard-section"><h2>Overview</h2><div className="cards">
                <Card
                  value={present.length}
                  label="present now"
                  onClick={()=>setPage('Children')}
                />

                <Card
                  value={
                    data.children.filter(
                      (x:any)=>x.active
                    ).length
                  }
                  label="enrolled"
                  onClick={()=>setPage('Children')}
                />

                <Card
                  value={data.rooms.length}
                  label="rooms"
                  onClick={isAdmin?()=>setPage('Rooms'):undefined}
                />

                {isAdmin&&<Card
                  value={data.devices.filter((x:any)=>!x.revoked).length}
                  label="active devices"
                  onClick={()=>setPage('Devices')}
                />}

              </div></section>

              <section className="dashboard-section"><h2>Needs attention</h2><div className="cards">
                <Card
                  value={data.incident_drafts||0}
                  label="incident drafts"
                  onClick={()=>setPage('Activity log')}
                />

                <Card
                  value={
                    (data.data_requests||[])
                      .filter(
                        (x:any)=>
                          ![
                            'completed',
                            'declined'
                          ].includes(x.status)
                      ).length
                  }
                  label="data requests"
                  onClick={()=>
                    setPage('Data requests')
                  }
                />
              </div></section>

              <section className="dashboard-section"><h2>Quick actions</h2><div className="inline-actions"><button onClick={()=>openClassroom(data.rooms[0]?.id)}>Open Classroom</button><button onClick={()=>setPage('Children')}>Children</button><button onClick={()=>setPage('Activity log')}>Activity log</button>{isAdmin&&<button onClick={()=>setPage('Devices')}>Pair new tablet</button>}</div></section>
              <DashboardActivity notice={notice} openAll={()=>setPage('Activity log')} openRecord={item=>{setActivityRecord(item);setPage('Activity log')}}/>
            </>
          }

          {page==='Rooms'&&
            <RoomsManager
              data={data}
              reload={load}
              notice={notice}
            />
          }

          {page==='Children'&&
            <ChildrenManager
              data={data}
              reload={load}
              notice={notice}
              openHistory={(childId)=>{setActivityRecord(undefined);setActivityChild(childId);setPage('Activity log')}}
              openRecord={item=>{setActivityRecord(item);setPage('Activity log')}}
            />
          }

          {page==='Families'&&<FamiliesManager children={data.children} notice={notice}/>}

          {page==='Teachers'&&
            <StaffManager
              data={data}
              reload={load}
              notice={notice}
            />
          }

          {page==='Devices'&&
            <>
              <div className="pair">
                <label>
                  Device label
                  <input
                    value={label}
                    onChange={e=>
                      setLabel(e.target.value)
                    }
                  />
                </label>

                <label>
                  Room
                  <select
                    value={room}
                    onChange={e=>
                      setRoom(e.target.value)
                    }
                  >
                    {data.rooms.map((x:any)=>
                      <option
                        value={x.id}
                        key={x.id}
                      >
                        {x.name}
                      </option>
                    )}
                  </select>
                </label>

                <button
                  disabled={!label.trim()||!room}
                  onClick={()=>
                    void api(
                      '/admin/pairings',
                      {
                        method:'POST',
                        body:JSON.stringify({
                          room_id:room,
                          label:label.trim()
                        })
                      }
                    )
                      .then((result:any)=>{
                        setPair(result);
                        setPairState(
                          'Waiting for tablet'
                        );
                      })
                      .catch(
                        (e:any)=>notice(e.message)
                      )
                  }
                >
                  Pair new tablet
                </button>

                {pair&&
                  <>
                    <p>
                      {pairState} · {seconds}s
                      remaining
                    </p>

                    {pair.qr_data_url&&
                      <img
                        alt="Pairing QR code"
                        src={pair.qr_data_url}
                      />
                    }

                    <h2>
                      Separate challenge{' '}
                      {pair.challenge}
                    </h2>

                    <div className="inline-actions">
                      {pair.pairing_url&&
                        <a
                          className="button-link"
                          href={pair.pairing_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open pairing page
                        </a>
                      }

                      {pair.pairing_url&&
                        <button
                          className="minor"
                          onClick={()=>
                            void navigator.clipboard
                              .writeText(
                                pair.pairing_url
                              )
                              .then(()=>
                                notice(
                                  'Pairing link copied'
                                )
                              )
                              .catch(()=>
                                notice(
                                  'Could not copy automatically'
                                )
                              )
                          }
                        >
                          Copy pairing link
                        </button>
                      }
                    </div>
                  </>
                }
              </div>

              {data.devices.filter((device:any)=>!device.revoked).sort((a:any,b:any)=>String(b.last_active_at).localeCompare(String(a.last_active_at))).map((device:any)=>
                <div
                  className="presence-row"
                  key={device.id}
                >
                  <span>
                    <b>{device.label}</b>
                    <small>
                        {device.default_room||'No default room'} · active · {device.last_active_at?new Date(device.last_active_at).toLocaleString():'Never active'}
                    </small>
                  </span>

                   <button
                      className="danger"
                      onClick={()=>
                        void api(
                          `/admin/devices/${device.id}/revoke`,
                          {method:'POST'}
                        ).then(load)
                      }
                    >
                      Revoke
                    </button>
                </div>
              )}
              {data.devices.some((device:any)=>device.revoked)&&<details><summary>Revoked / old devices ({data.devices.filter((device:any)=>device.revoked).length})</summary>{data.devices.filter((device:any)=>device.revoked).map((device:any)=><div className="presence-row" key={device.id}><span><b>{device.label}</b><small>{device.default_room||'No default room'} · revoked</small></span></div>)}</details>}
            </>
          }

          {page==='Activity log'&&<ActivityLog data={data} isAdmin={isAdmin} notice={notice} initialChildId={activityChild} initialRecord={activityRecord}/>}

          {page==='Data requests'&&
            <>
              {(data.data_requests||[]).map(
                (request:any)=>
                  <div
                    className="presence-row"
                    key={request.id}
                  >
                    <span>
                      <b>
                        {request.child_name}
                      </b>

                      <small>
                        {request.start_date}
                        {' – '}
                        {request.end_date}
                        {' · '}
                        {request.note||
                         'No note'}
                      </small>
                    </span>

                    <select
                      aria-label={
                        `Status for ${request.child_name}`
                      }
                      value={request.status}
                      onChange={e=>
                        void api(
                          `/admin/data-requests/${request.id}`,
                          {
                            method:'PATCH',
                            body:JSON.stringify({
                              status:e.target.value
                            })
                          }
                        ).then(load)
                      }
                    >
                      {[
                        'new',
                        'in_progress',
                        'completed',
                        'declined'
                      ].map(x=>
                        <option
                          value={x}
                          key={x}
                        >
                          {x.replace('_',' ')}
                        </option>
                      )}
                    </select>
                  </div>
              )}
            </>
          }

          {page==='Settings'&&<section className="settings-panels"><details><summary>My sign-in</summary><AccountPassword embedded/></details>{isAdmin&&<><details open={settingsSections[0].open}><summary>{settingsSections[0].title}</summary><AccountsSettings/></details><details open={settingsSections[1].open}><summary>{settingsSections[1].title}</summary><Branding data={data} saved={async()=>{await load();notice('Branding saved')}}/></details></>}</section>}

          {page==='Help'&&
            <Help demo={data.demo_mode}/>
          }
        </section>
      </div>
    </main>
  );
}


function openClassroom(roomId:string){
  localStorage.setItem(
    'classroom-room',
    roomId
  );

  location.assign('/classroom');
}


function Card({
  value,
  label,
  onClick
}:{
  value:number;
  label:string;
  onClick?:()=>void;
}){
  if(onClick){
    return(
      <button
        type="button"
        className="metric-card"
        onClick={onClick}
      >
        <b>{value}</b>
        <span>{label}</span>
      </button>
    );
  }

  return(
    <div className="metric-card">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}

function DashboardActivity({notice,openAll,openRecord}:{notice:Notice;openAll:()=>void;openRecord:(item:any)=>void}){
  const[items,setItems]=useState<any[]>([]);
  useEffect(()=>{void api('/admin/activity?limit=10').then((result:any)=>setItems(result.items)).catch((error:any)=>notice(error.message))},[]);
  return <section className="dashboard-section"><div className="manager-toolbar"><h2>Recent activity</h2><button className="minor" onClick={openAll}>View all activity</button></div><div className="person-list">{items.map(item=><button className="person-row" key={`${item.source}-${item.id}`} onClick={()=>openRecord(item)}><span><b>{item.activity||item.type}</b><small>{item.child_name||'Centre'} · {item.teacher||'No teacher'} · {item.room||'No room'}{item.corrected?' · corrected':''}</small></span><small>{new Date(item.effective_at).toLocaleString()}</small></button>)}</div></section>;
}


function RoomsManager({
  data,
  reload,
  notice
}:{
  data:any;
  reload:()=>Promise<void>;
  notice:Notice;
}){
  const[editing,setEditing]=useState(false);
  const[adding,setAdding]=useState(false);

  return(
    <section>
      <div className="manager-toolbar">
        <div>
          <h2>Classrooms</h2>
          <p>
            Click a room card to open its
            classroom console.
          </p>
        </div>

        <div className="inline-actions">
          {editing&&
            <button
              onClick={()=>setAdding(true)}
            >
              + Add room
            </button>
          }

          <button
            className="minor"
            onClick={()=>{
              setEditing(value=>!value);
              setAdding(false);
            }}
          >
            {editing?'Done':'Edit'}
          </button>
        </div>
      </div>

      {adding&&
        <RoomEditor
          room={null}
          reload={async()=>{
            setAdding(false);
            await reload();
          }}
          notice={notice}
          cancel={()=>setAdding(false)}
        />
      }

      <div className="room-card-grid">
        {data.rooms.map((room:any)=>
          editing
            ?(
              <RoomEditor
                key={room.id}
                room={room}
                reload={reload}
                notice={notice}
              />
            )
            :(
              <button
                type="button"
                className="room-card"
                key={room.id}
                onClick={()=>
                  openClassroom(room.id)
                }
              >
                <span className="room-icon">
                  {room.icon}
                </span>

                <span className="room-card-main">
                  <b>{room.name}</b>

                  <small>
                    {room.present_count} present
                    {' · '}
                    {room.enrolled_count} enrolled
                  </small>
                </span>

                <span
                  className="accent-swatch"
                  style={{
                    backgroundColor:room.accent
                  }}
                  title={room.accent}
                  aria-label={
                    `Accent ${room.accent}`
                  }
                />
              </button>
            )
        )}
      </div>
    </section>
  );
}


function RoomEditor({
  room,
  reload,
  notice,
  cancel
}:{
  room:any|null;
  reload:()=>Promise<void>;
  notice:Notice;
  cancel?:()=>void;
}){
  const[name,setName]=useState(
    room?.name||''
  );
  const[icon,setIcon]=useState(
    room?.icon||'🌿'
  );
  const[accent,setAccent]=useState(
    room?.accent||'#176B5B'
  );
  const[deleting,setDeleting]=useState(false);
  const[password,setPassword]=useState('');
  const[busy,setBusy]=useState(false);

  const save=async()=>{
    try{
      setBusy(true);

      await api(
        room
          ?`/admin/rooms/${room.id}`
          :'/admin/rooms',
        {
          method:room?'PATCH':'POST',
          body:JSON.stringify({
            name:name.trim(),
            icon:icon.trim(),
            accent
          })
        }
      );

      await reload();

      notice(
        room
          ?'Room updated'
          :'Room added'
      );
    }catch(e:any){
      notice(e.message);
    }finally{
      setBusy(false);
    }
  };

  const remove=async()=>{
    if(!room)return;

    try{
      setBusy(true);

      await api(
        `/admin/rooms/${room.id}/delete`,
        {
          method:'POST',
          body:JSON.stringify({
            admin_password:password
          })
        }
      );

      await reload();
      notice('Room deleted');
    }catch(e:any){
      notice(e.message);
    }finally{
      setBusy(false);
      setPassword('');
    }
  };

  return(
    <article className="manager-editor">
      <div className="editor-grid">
        <label>
          Icon
          <input
            className="icon-input"
            value={icon}
            maxLength={8}
            onChange={e=>setIcon(e.target.value)}
          />
        </label>

        <div className="icon-presets" aria-label="Room icon presets">
          {['🌿','☀️','🌳','🌸','🌈','🐝','🦋','🐞','⭐','🌙','🐦'].map(value=><button type="button" className={value===icon?'active':'minor'} key={value} onClick={()=>setIcon(value)}>{value}</button>)}
        </div>

        <label>
          Name
          <input
            value={name}
            onChange={e=>setName(e.target.value)}
          />
        </label>

        <label>
          Accent
          <span className="colour-input">
            <input
              type="color"
              value={accent}
              onChange={e=>
                setAccent(
                  e.target.value.toUpperCase()
                )
              }
            />

            <code>{accent}</code>
          </span>
        </label>
      </div>

      <div className="inline-actions">
        <button
          disabled={
            busy||
            name.trim().length<2||
            !icon.trim()
          }
          onClick={()=>void save()}
        >
          {busy?'Saving…':'Save'}
        </button>

        {cancel&&
          <button
            className="minor"
            onClick={cancel}
          >
            Cancel
          </button>
        }

        {room&&
          <button
            className="minor"
            onClick={()=>
              openClassroom(room.id)
            }
          >
            Open classroom
          </button>
        }

        {room&&!deleting&&
          <button
            className="danger"
            onClick={()=>setDeleting(true)}
          >
            Delete room
          </button>
        }
      </div>

      {deleting&&
        <div className="danger-confirm">
          <b>Permanent deletion</b>

          <p>
            Only completely unused rooms can be
            deleted. Established rooms are kept
            for historical integrity.
          </p>

          <label>
            Current Admin password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={e=>
                setPassword(e.target.value)
              }
            />
          </label>

          <div className="inline-actions">
            <button
              className="danger"
              disabled={busy||!password}
              onClick={()=>void remove()}
            >
              Confirm delete
            </button>

            <button
              className="minor"
              onClick={()=>{
                setDeleting(false);
                setPassword('');
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      }
    </article>
  );
}


function ChildrenManager({
  data,
  reload,
  notice,
  openHistory,
  openRecord
}:{
  data:any;
  reload:()=>Promise<void>;
  notice:Notice;
  openHistory:(childId:string)=>void;
  openRecord:(item:any)=>void;
}){
  const[adding,setAdding]=useState(false);
  const[search,setSearch]=useState('');
  const[selectedChildId,setSelectedChildId]=useState('');
  const selected=data.children.find((child:any)=>child.id===selectedChildId);

  const filtered=useMemo(()=>{
    const query=search
      .trim()
      .toLowerCase();

    if(!query)return data.children;

    return data.children.filter(
      (child:any)=>
        [
          child.first_name,
          child.last_name,
          child.preferred_name,
          child.enrolled_room,
          child.physical_room,
          child.dob
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(query)
    );
  },[data.children,search]);

  return(
    <section>
      <div className="manager-toolbar">
        <div>
          <h2>Children</h2>
          <p>
            Add a fictional child here, then
            open their classroom to test the
            roster immediately.
          </p>
        </div>

        <div className="inline-actions">
          <input
            className="manager-search"
            aria-label="Search children"
            placeholder="Search children…"
            value={search}
            onChange={e=>
              setSearch(e.target.value)
            }
          />

          <button
            onClick={()=>setAdding(true)}
          >
            + Add child
          </button>

          <button
            className="minor no-print"
            onClick={()=>print()}
          >
            Print attended
          </button>
        </div>
      </div>

      {adding&&
        <ChildEditor
          child={null}
          rooms={data.rooms}
          reload={async()=>{
            setAdding(false);
            await reload();
          }}
          notice={notice}
          cancel={()=>setAdding(false)}
        />
      }

      {selected&&
        <section className="manager-editor child-detail">
          <button className="close" onClick={()=>setSelectedChildId('')}>×</button>
          <h3>{selected.preferred_name||selected.first_name} {selected.last_name}</h3>
          <p>{selected.present?'Present':'Absent'} · Enrolled: {selected.enrolled_room||'No room'} · Physical: {selected.physical_room||'Not at centre'}</p>
          <ChildEditor child={selected} rooms={data.rooms} reload={reload} notice={notice}/>
          <h4>Linked families</h4>
          <div className="person-list">{selected.families?.length?selected.families.map((family:any)=><div className="person-row" key={family.id}><span><b>{family.name}</b><small>{family.login}</small></span><small>{family.active?'Active':'Inactive'}</small></div>):<p>No family login linked.</p>}</div>
          <ChildHistory child={selected} notice={notice} openHistory={openHistory} openRecord={openRecord}/>
        </section>
      }

      <div className="person-list">
        {filtered.map((child:any)=>(
              <button
                type="button"
                onClick={()=>setSelectedChildId(child.id)}
                className={
                  `person-row ${
                    child.active
                      ?''
                      :'inactive'
                  }`
                }
                key={child.id}
              >
                <span>
                  <b>
                    {child.preferred_name||
                     child.first_name}{' '}
                    {child.last_name}
                  </b>

                  {child.preferred_name&&
                    <small>
                      Legal first name:{' '}
                      {child.first_name}
                    </small>
                  }

                  <small>
                    {child.enrolled_room||
                     'No enrolled room'}
                    {' · '}
                    {child.present
                      ?`Present in ${
                        child.physical_room||
                        'centre'
                      }`
                      :'Not currently present'}
                  </small>

                  {!child.active&&
                    <small className="warning-text">
                      Archived
                    </small>
                  }
                </span>
                <small>{child.active?'Active':'Archived'}</small>
              </button>
        ))}
      </div>
    </section>
  );
}

function ChildHistory({child,notice,openHistory,openRecord}:{child:any;notice:Notice;openHistory:(id:string)=>void;openRecord:(item:any)=>void}){
  const[items,setItems]=useState<any[]>([]);
  useEffect(()=>{void api(`/admin/activity?child_id=${child.id}&limit=12`).then((result:any)=>setItems(result.items)).catch((error:any)=>notice(error.message))},[child.id]);
  return <section className="child-history"><div className="manager-toolbar"><h4>Recent activity</h4><button className="minor" onClick={()=>openHistory(child.id)}>View full history</button></div>{items.map(item=><button className="person-row" key={`${item.source}-${item.id}`} onClick={()=>openRecord(item)}><span><b>{item.activity||item.type}</b><small>{item.teacher||'No teacher'} · {item.room||'No room'}{item.corrected?' · corrected':''}</small></span><small>{new Date(item.effective_at).toLocaleString()}</small></button>)}</section>;
}


function ChildEditor({
  child,
  rooms,
  reload,
  notice,
  cancel
}:{
  child:any|null;
  rooms:any[];
  reload:()=>Promise<void>;
  notice:Notice;
  cancel?:()=>void;
}){
  const[firstName,setFirstName]=useState(
    child?.first_name||''
  );
  const[lastName,setLastName]=useState(
    child?.last_name||''
  );
  const[preferredName,setPreferredName]=
    useState(child?.preferred_name||'');
  const[dob,setDob]=useState(
    child?.dob||''
  );
  const[roomId,setRoomId]=useState(
    child?.room_id||
    rooms[0]?.id||
    ''
  );
  const[active,setActive]=useState(
    child?.active??true
  );
  const[busy,setBusy]=useState(false);

  useEffect(()=>{
    setFirstName(child?.first_name||'');
    setLastName(child?.last_name||'');
    setPreferredName(child?.preferred_name||'');
    setDob(child?.dob||'');
    setRoomId(child?.room_id||rooms[0]?.id||'');
    setActive(child?.active??true);
  },[child,rooms]);

  const save=async()=>{
    try{
      setBusy(true);

      await api(
        child
          ?`/admin/children/${child.id}`
          :'/admin/children',
        {
          method:child?'PATCH':'POST',
          body:JSON.stringify({
            first_name:firstName.trim(),
            last_name:lastName.trim(),
            preferred_name:
              preferredName.trim()||null,
            dob:dob||null,
            room_id:roomId||null,
            active
          })
        }
      );

      await reload();

      notice(
        child
          ?'Child updated'
          :'Child added'
      );
    }catch(e:any){
      notice(e.message);
    }finally{
      setBusy(false);
    }
  };

  return(
    <article className="manager-editor">
      <div className="editor-grid">
        <label>
          First name
          <input
            value={firstName}
            onChange={e=>
              setFirstName(e.target.value)
            }
          />
        </label>

        <label>
          Last name
          <input
            value={lastName}
            onChange={e=>
              setLastName(e.target.value)
            }
          />
        </label>

        <label>
          Preferred name
          <input
            value={preferredName}
            onChange={e=>
              setPreferredName(e.target.value)
            }
          />
        </label>

        <label>
          Date of birth
          <input
            type="date"
            value={dob}
            onChange={e=>setDob(e.target.value)}
          />
        </label>

        <label>
          Enrolled room
          <select
            value={roomId}
            onChange={e=>
              setRoomId(e.target.value)
            }
          >
            <option value="">
              No room assigned
            </option>

            {rooms.map(room=>
              <option
                key={room.id}
                value={room.id}
              >
                {room.icon} {room.name}
              </option>
            )}
          </select>
        </label>

        <label className="check">
          <input
            type="checkbox"
            checked={active}
            onChange={e=>
              setActive(e.target.checked)
            }
          />
          Active / enrolled
        </label>
      </div>

      <div className="inline-actions">
        <button
          disabled={busy||!firstName.trim()}
          onClick={()=>void save()}
        >
          {busy?'Saving…':'Save'}
        </button>

        {cancel&&
          <button
            className="minor"
            onClick={cancel}
          >
            Cancel
          </button>
        }

        {child?.room_id&&
          <button
            className="minor"
            onClick={()=>
              openClassroom(child.room_id)
            }
          >
            Open classroom
          </button>
        }
      </div>

      {!active&&
        <p className="warning-text">
          Archived children remain in
          historical records but are marked
          inactive.
        </p>
      }
    </article>
  );
}


function StaffManager({
  data,
  reload,
  notice
}:{
  data:any;
  reload:()=>Promise<void>;
  notice:Notice;
}){
  const[editing,setEditing]=useState(false);
  const[adding,setAdding]=useState(false);
  const[search,setSearch]=useState('');

  const filtered=useMemo(()=>{
    const query=search
      .trim()
      .toLowerCase();

    if(!query)return data.staff;

    return data.staff.filter(
      (staff:any)=>
        [
          staff.first_name,
          staff.last_name,
          staff.preferred_name,
          staff.employment_type,
          staff.active?'active':'inactive'
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(query)
    );
  },[data.staff,search]);

  return(
    <section>
      <div className="manager-toolbar">
        <div>
          <h2>Teachers</h2>
          <p>
            Teachers are deactivated rather than
            deleted so old records keep their
            attribution.
          </p>
        </div>

        <div className="inline-actions">
          <input
            className="manager-search"
            aria-label="Search teachers"
            placeholder="Search teachers…"
            value={search}
            onChange={e=>
              setSearch(e.target.value)
            }
          />

          {editing&&
            <button
              onClick={()=>setAdding(true)}
            >
              + Add teacher
            </button>
          }

          <button
            className="minor"
            onClick={()=>{
              setEditing(value=>!value);
              setAdding(false);
            }}
          >
            {editing?'Done':'Edit'}
          </button>
        </div>
      </div>

      {adding&&
        <StaffEditor
          staff={null}
          reload={async()=>{
            setAdding(false);
            await reload();
          }}
          notice={notice}
          cancel={()=>setAdding(false)}
        />
      }

      <div className="person-card-grid">
        {filtered.map((staff:any)=>
          editing
            ?(
              <StaffEditor
                key={staff.id}
                staff={staff}
                reload={reload}
                notice={notice}
              />
            )
            :(
              <article
                className={
                  `person-card ${
                    staff.active
                      ?''
                      :'inactive'
                  }`
                }
                key={staff.id}
              >
                <div>
                  <b>
                    {staff.preferred_name||
                     staff.first_name}{' '}
                    {staff.last_name}
                  </b>

                  <small>
                    {staff.employment_type}
                    {' · '}
                    {staff.active
                      ?'Active'
                      :'Inactive'}
                  </small>
                </div>
              </article>
            )
        )}
      </div>
    </section>
  );
}


function StaffEditor({
  staff,
  reload,
  notice,
  cancel
}:{
  staff:any|null;
  reload:()=>Promise<void>;
  notice:Notice;
  cancel?:()=>void;
}){
  const[firstName,setFirstName]=useState(
    staff?.first_name||''
  );
  const[lastName,setLastName]=useState(
    staff?.last_name||''
  );
  const[preferredName,setPreferredName]=
    useState(staff?.preferred_name||'');
  const[employmentType,setEmploymentType]=
    useState(
      staff?.employment_type||'permanent'
    );
  const[active,setActive]=useState(
    staff?.active??true
  );

  const[initialPin,setInitialPin]=
    useState('');
  const[resettingPin,setResettingPin]=
    useState(false);
  const[newPin,setNewPin]=useState('');
  const[adminPassword,setAdminPassword]=
    useState('');
  const[busy,setBusy]=useState(false);

  const save=async()=>{
    try{
      setBusy(true);

      const payload:any={
        first_name:firstName.trim(),
        last_name:lastName.trim(),
        preferred_name:
          preferredName.trim()||null,
        employment_type:employmentType,
        active
      };

      if(!staff){
        payload.pin=initialPin||null;
      }

      await api(
        staff
          ?`/admin/staff/${staff.id}`
          :'/admin/staff',
        {
          method:staff?'PATCH':'POST',
          body:JSON.stringify(payload)
        }
      );

      await reload();

      notice(
        staff
          ?'Teacher updated'
          :'Teacher added'
      );
    }catch(e:any){
      notice(e.message);
    }finally{
      setBusy(false);
    }
  };

  const resetPin=async()=>{
    if(!staff)return;

    try{
      setBusy(true);

      await api(
        `/admin/staff/${staff.id}/pin-reset`,
        {
          method:'POST',
          body:JSON.stringify({
            pin:newPin,
            account_password:adminPassword
          })
        }
      );

      setNewPin('');
      setAdminPassword('');
      setResettingPin(false);

      notice('Teacher PIN reset');
    }catch(e:any){
      notice(e.message);
    }finally{
      setBusy(false);
    }
  };

  return(
    <article className="manager-editor">
      <div className="editor-grid">
        <label>
          First name
          <input
            value={firstName}
            onChange={e=>
              setFirstName(e.target.value)
            }
          />
        </label>

        <label>
          Last name
          <input
            value={lastName}
            onChange={e=>
              setLastName(e.target.value)
            }
          />
        </label>

        <label>
          Preferred name
          <input
            value={preferredName}
            onChange={e=>
              setPreferredName(e.target.value)
            }
          />
        </label>

        <label>
          Employment type
          <select
            value={employmentType}
            onChange={e=>
              setEmploymentType(
                e.target.value
              )
            }
          >
            <option value="permanent">
              Permanent
            </option>
            <option value="casual">
              Casual
            </option>
            <option value="reliever">
              Reliever
            </option>
            <option value="contractor">
              Contractor
            </option>
          </select>
        </label>

        <label className="check">
          <input
            type="checkbox"
            checked={active}
            onChange={e=>
              setActive(e.target.checked)
            }
          />
          Active
        </label>

        {!staff&&
          <label>
            Initial 4-digit PIN
            <input
              inputMode="numeric"
              maxLength={4}
              value={initialPin}
              onChange={e=>
                setInitialPin(
                  e.target.value
                    .replace(/\D/g,'')
                    .slice(0,4)
                )
              }
            />
          </label>
        }
      </div>

      <div className="inline-actions">
        <button
          disabled={
            busy||
            !firstName.trim()||
            !lastName.trim()||
            (
              !staff&&
              initialPin.length!==4
            )
          }
          onClick={()=>void save()}
        >
          {busy?'Saving…':'Save'}
        </button>

        {cancel&&
          <button
            className="minor"
            onClick={cancel}
          >
            Cancel
          </button>
        }

        {staff&&
          <button
            className="minor"
            onClick={()=>
              setResettingPin(
                value=>!value
              )
            }
          >
          Reset teacher PIN
          </button>
        }
      </div>

      {staff&&resettingPin&&
        <div className="danger-confirm">
          <h3>Reset teacher PIN</h3>

          <label>
            New 4-digit PIN
            <input
              type="password"
              inputMode="numeric"
              maxLength={4}
              value={newPin}
              onChange={e=>
                setNewPin(
                  e.target.value
                    .replace(/\D/g,'')
                    .slice(0,4)
                )
              }
            />
          </label>

          <label>
            Your account password
            <input
              type="password"
              autoComplete="current-password"
              value={adminPassword}
              onChange={e=>
                setAdminPassword(
                  e.target.value
                )
              }
            />
          </label>

          <div className="inline-actions">
            <button
              disabled={
                busy||
                newPin.length!==4||
                !adminPassword
              }
              onClick={()=>void resetPin()}
            >
              Confirm PIN reset
            </button>

            <button
              className="minor"
              onClick={()=>{
                setResettingPin(false);
                setNewPin('');
                setAdminPassword('');
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      }
    </article>
  );
}


function Table({
  items,
  fields
}:{
  items:any[];
  fields:string[];
}){
  const value=(
    item:any,
    field:string
  )=>{
    const current=item[field];

    if(
      current &&
      (
        field.endsWith('_at')||
        field==='created_at'
      )
    ){
      const date=new Date(current);

      if(!Number.isNaN(date.getTime())){
        return date.toLocaleString(
          'en-NZ',
          {
            day:'numeric',
            month:'short',
            hour:'numeric',
            minute:'2-digit'
          }
        );
      }
    }

    if(field==='type'&&current){
      return String(current)
        .replaceAll('_',' ');
    }

    return String(current??'—');
  };

  return(
    <table>
      <thead>
        <tr>
          {fields.map(field=>
            <th key={field}>
              {field.replaceAll('_',' ')}
            </th>
          )}
        </tr>
      </thead>

      <tbody>
        {items.map((item,index)=>
          <tr key={item.id||index}>
            {fields.map(field=>
              <td key={field}>
                {value(item,field)}
              </td>
            )}
          </tr>
        )}
      </tbody>
    </table>
  );
}


function Branding({
  data,
  saved
}:{
  data:any;
  saved:()=>void|Promise<void>;
}){
  const[display_name,setName]=useState(
    data.centre.display_name||''
  );
  const[secondary_text,setSecondary]=
    useState(
      data.centre.secondary_text||''
    );
  const[timezone,setTimezone]=useState(
    data.centre.timezone||
    'Pacific/Auckland'
  );
  const[logo,setLogo]=useState(
    data.centre.logo_url
  );
  const[busy,setBusy]=useState(false);

  const upload=async(file:File)=>{
    setBusy(true);

    try{
      const body=new FormData();
      body.append('file',file);

      const response=await fetch(
        '/api/admin/branding/logo',
        {
          method:'POST',
          credentials:'include',
          body
        }
      );

      if(!response.ok){
        throw new Error(
          (await response.json()).detail||
          'Logo upload failed'
        );
      }

      const result=await response.json();

      setLogo(
        `${result.logo_url}?v=${Date.now()}`
      );

      await saved();
    }finally{
      setBusy(false);
    }
  };

  return(
    <section>
      <form
        onSubmit={e=>{
          e.preventDefault();

          void api(
            '/admin/branding',
            {
              method:'PATCH',
              body:JSON.stringify({
                display_name,
                secondary_text,
                timezone
              })
            }
          ).then(saved);
        }}
      >
        <label>
          Display name
          <input
            value={display_name}
            onChange={e=>
              setName(e.target.value)
            }
          />
        </label>

        <label>
          Secondary text
          <input
            value={secondary_text}
            onChange={e=>
              setSecondary(e.target.value)
            }
          />
        </label>

        <label>
          Centre timezone
          <input
            value={timezone}
            onChange={e=>
              setTimezone(e.target.value)
            }
          />
        </label>

        <button>Save branding</button>
      </form>

      <h2>Logo</h2>

      {logo&&
        <img
          className="branding-preview"
          src={logo}
          alt="Current centre logo"
        />
      }

      <label>
        Upload PNG, JPEG, or WebP
        <input
          aria-label="Upload centre logo"
          disabled={busy}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={e=>{
            const file=e.target.files?.[0];

            if(file){
              void upload(file);
            }
          }}
        />
      </label>

      {logo&&
        <button
          className="danger"
          onClick={()=>void api(
            '/admin/branding/logo',
            {method:'DELETE'}
          ).then(()=>{
            setLogo(null);
            return saved();
          })}
        >
          Remove logo
        </button>
      }
    </section>
  );
}


function Help({demo}:{demo:boolean}){
  const topics=[
    [
      'Pairing',
      'Create a labeled 90-second QR pairing under Devices, confirm its room, then enter the separate three-digit challenge on the tablet.'
    ],
    [
      'Attendance and visits',
      'Arrive and depart from Attendance / Presence. Start and end visits from the destination room. Resolve any open sleep first.'
    ],
    [
      'Toileting',
      'Select children, choose nappy or toilet, record the outcome and save once.'
    ],
    [
      'Food',
      'Select one or more children, add servings and optional food detail. Offline batches remain pending until exact replay succeeds.'
    ],
    [
      'Sunscreen',
      'Select physically present children and record the application.'
    ],
    [
      'Sleep lifecycle',
      'Record Put down, Fell asleep, Wake, then Got up in chronological order. Reconcile stale sessions explicitly.'
    ],
    [
      'Sleep Check',
      'Select sleeping children, check warmth, breathing and wellbeing, then record the check.'
    ],
    [
      'Medication',
      'Use only an active authority. Verify the staff PIN at final administration; active does not automatically mean due.'
    ],
    [
      'Incident drafts',
      'Partial drafts autosave locally and to the server after a child is selected. Review and verify the PIN to finalise; discard removes both copies.'
    ],
    [
      'Parent notes',
      'Teacher notes appear in Parent Notes. Mark read or pin operationally.'
    ],
    [
      'Offline and sync',
      'Ordinary care may queue. Medicine and incident finalisation require a live connection. Open Sync for pending state.'
    ],
    [
      'Emergency Roll',
      'Uses only the last-confirmed attendance snapshot, grouped by physical room. Offline and stale states are prominent.'
    ]
  ];

  return(
    <section className="help-page">
      {topics.map(([title,body])=>
        <article key={title}>
          <h2>{title}</h2>
          <p>{body}</p>
        </article>
      )}

      {demo&&
        <aside className="demo-cheat">
          <h2>Demo Cheat Sheet</h2>
          <p>
            Admin: admin@demo.local /
            ChangeMe123!
          </p>
          <p>
            Parent: demo-parent / 123456
          </p>
          <p>
            Staff PINs: Sarah 1234 ·
            Michael 2345 · Aroha 3456
          </p>
        </aside>
      }
    </section>
  );
}
