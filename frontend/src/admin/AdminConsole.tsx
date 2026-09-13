import React,{useEffect,useMemo,useState}from'react';
import{api}from'../api';
import{useLiveReconciliation}from'../live';
import FamiliesManager from'./FamiliesManager';
import ActivityLog,{activityContext}from'./ActivityLog';
import{formatCentreDateTime}from'../centre-time';
import{ConfirmDialog}from'./ConfirmDialog';
import{managementPagesForRole,type AdminPage}from'../account/role-ui';
import{SettingsPage}from'./SettingsPage';
import{EmergencyRoll}from'../ui/EmergencyRoll';
import{ClearableSearch}from'../ui/ClearableSearch';

type Page=AdminPage;

type Notice=(message:string)=>void;
export const pairingShowsChallenge=(pair:any)=>Boolean(pair&&!pair.consumed_at);

export default function AdminConsole(){
  const[data,setData]=useState<any>();
  const[page,setPage]=useState<Page>('Dashboard');
  const[activityChild,setActivityChild]=useState('');
  const[activityRecord,setActivityRecord]=useState<any>();
  const[printing,setPrinting]=useState(false);

  const[pair,setPair]=useState<any>();
  const[pairState,setPairState]=useState('');
  const[seconds,setSeconds]=useState(0);
  const[pairView,setPairView]=useState<'qr'|'words'>('qr');
  const[label,setLabel]=useState('Classroom tablet');
  const[deviceMode,setDeviceMode]=useState<'classroom'|'attendance'>('classroom');
  const[room,setRoom]=useState('');
  const[message,setMessage]=useState('');

  const load=async()=>{
    const boot=await api('/admin/bootstrap');
    setData(boot);
    setRoom((value:string)=>
      value||boot.rooms[0]?.id||''
    );
  };

  const liveState=useLiveReconciliation(load);

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
        setPair((value:any)=>({...value,...status}));
        setPairState(
          'Paired successfully'
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
  },[pair?.id,pair?.expires_at]);

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

        <small className={liveState==='Live'?'live-indicator':'live-indicator offline'}>
          {liveState}
        </small>

        {isAdmin&&<button type="button" className="minor" onClick={()=>setPrinting(true)}>Emergency roll</button>}

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
            <div className="dashboard-grid">
              <section className="dashboard-section dashboard-overview"><h2>Overview</h2><div className="cards">
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

              <section className="dashboard-section dashboard-attention"><h2>Needs attention</h2><div className="cards">
                <Card value={(data.attendance_signature_issues||data.missing_sign_outs||[]).length} label="attendance evidence issues"/>
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
              </div>{(data.attendance_signature_issues||data.missing_sign_outs||[]).length>0&&<details className="attention-list"><summary>Children awaiting Parent attendance evidence</summary>{(data.attendance_signature_issues||data.missing_sign_outs).map((item:any)=><div className="person-row" key={item.attendance_id+'-'+(item.phase||'sign_out')}><span><b>{item.child_name}</b><small>{item.phase==='sign_in'?'Marked present':item.departed_at?'Departure recorded':'Open since'}: {formatCentreDateTime(item.phase==='sign_out'&&item.departed_at?item.departed_at:item.arrived_at,data.centre.timezone)}{item.room?' · '+item.room:''}</small></span><small>{item.status}</small></div>)}</details>}</section>

              <section className="dashboard-section dashboard-status"><h2>Operational status</h2><p><b>{liveState}</b> live reconciliation</p><p>{data.devices.filter((x:any)=>!x.revoked).length} active devices</p></section>
              <div className="dashboard-activity"><DashboardActivity timezone={data.centre.timezone} notice={notice} openAll={()=>setPage('Activity log')} openRecord={item=>{setActivityRecord(item);setPage('Activity log')}}/></div>
            </div>
          }

          {page==='Rooms'&&
            <RoomsManager
              data={data}
              reload={load}
              notice={notice}
            />
          }

          {page==='Safety check'&&<SafetyChecks data={data} notice={notice}/>}

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
                  Device use
                  <select value={deviceMode} onChange={event=>{const mode=event.target.value as 'classroom'|'attendance';setDeviceMode(mode);setLabel(mode==='attendance'?'Sign-in tablet':'Classroom tablet')}}><option value="classroom">Classroom tablet</option><option value="attendance">Sign-in tablet</option></select>
                </label>

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
                          label:label.trim(),
                          mode:deviceMode
                        })
                      }
                    )
                      .then((result:any)=>{
                        setPair(result);
                        setPairView('qr');
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

                {pair&&pair.consumed_at&&<div className="pair-success" role="status"><h2>✓ Paired successfully</h2><p>{deviceMode==='attendance'?'Sign-in tablet':'Classroom tablet'} · {data.rooms.find((item:any)=>item.id===room)?.name}</p><button type="button" className="minor" onClick={()=>{setPair(undefined);setPairState('');setSeconds(0);setPairView('qr')}}>Pair another tablet</button></div>}
                {pairingShowsChallenge(pair)&&
                  <>
                    <p>
                      {pairState} · {seconds}s
                      remaining
                    </p>

                    {pairView==='qr'&&pair.qr_data_url&&
                      <img
                        alt="Pairing QR code"
                        src={pair.qr_data_url}
                      />
                    }

                    {pairView==='words'&&<div className="pairing-words" aria-label="Three-word pairing code">{String(pair.token).split('-').join(' ')}</div>}

                    <h2>
                      Separate challenge{' '}
                      {pair.challenge}
                    </h2>

                    <button type="button" className="minor" onClick={()=>{if(pairView==='words'){setPairView('qr');return}if(pair.manual_revealed){setPairView('words');return}void api(`/admin/pairings/${pair.id}/manual-token`,{method:'POST'}).then((result:any)=>{setPair((value:any)=>({...value,...result}));setPairView('words')}).catch((error:any)=>notice(error.message))}}>{pairView==='qr'?'Show pairing words':'Show QR code'}</button>

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
                        {device.mode==='attendance'?'Sign-in tablet':'Classroom tablet'} · {device.default_room||'No default room'}{device.mode==='attendance'?' · Sign-in only':''} · active · {device.last_active_at?new Date(device.last_active_at).toLocaleString():'Never active'}
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
              {!(data.data_requests||[]).length&&<div className="empty-state"><h2>No data requests are waiting.</h2><p>Parent requests for older records will appear here.</p></div>}
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

          {page==='Settings'&&<SettingsPage data={data} isAdmin={isAdmin} saved={async()=>{await load();notice('Settings saved')}}/>}

          {page==='Help'&&
            <Help demo={data.demo_mode}/>
          }
        </section>
      </div>
      {printing&&<EmergencyRoll data={data} onClose={()=>setPrinting(false)}/>}
    </main>
  );
}


export const classroomUrl=(roomId:string)=>`/classroom?room=${encodeURIComponent(roomId)}`;
export function openClassroom(roomId:string){location.assign(classroomUrl(roomId))}


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

export function DashboardActivity({timezone,notice,openAll,openRecord}:{timezone:string;notice:Notice;openAll:()=>void;openRecord:(item:any)=>void}){
  const[items,setItems]=useState<any[]>([]);
  const load=()=>api('/admin/activity?limit=10').then((result:any)=>setItems(result.items)).catch((error:any)=>notice(error.message));
  useEffect(()=>{void load()},[]);useLiveReconciliation(load);
  return <section className="dashboard-section"><div className="manager-toolbar"><h2>Recent activity</h2><button className="minor" onClick={openAll}>View all activity</button></div><div className="person-list">{items.map(item=><button className="person-row" key={`${item.source}-${item.id}`} onClick={()=>openRecord(item)}><span><b>{item.activity||item.type}</b><small>{activityContext(item)}{item.corrected?' · corrected':''}</small></span><small>{formatCentreDateTime(item.effective_at,timezone)}</small></button>)}</div></section>;
}

export function SafetyChecks({data,notice}:{data:any;notice:Notice}){
  const[history,setHistory]=useState<any[]>([]),[current,setCurrent]=useState<any>(),[selectedRoomId,setSelectedRoomId]=useState(''),[staffId,setStaffId]=useState(''),[pin,setPin]=useState(''),[observed,setObserved]=useState(0),[note,setNote]=useState(''),[reauthPin,setReauthPin]=useState('');
  const load=()=>api('/admin/safety-checks').then((rows:any[])=>{setHistory(rows);setCurrent((value:any)=>value?rows.find(row=>row.id===value.id)||value:rows.find(row=>row.status==='open'))}).catch((error:any)=>notice(error.message));
  useEffect(()=>{void load()},[]);
  const selected=current?.rooms?.find((room:any)=>room.room_id===selectedRoomId&&!room.checked_at);
  const allChecked=Boolean(current)&&current.rooms.every((room:any)=>room.checked_at);
  useEffect(()=>{if(selected){setObserved(selected.expected_count);setNote('');setReauthPin('')}},[selected?.room_id,selected?.expected_count]);
  const refreshCurrent=async(resetRoom=false)=>{const previous=current?.rooms?.find((room:any)=>room.room_id===selectedRoomId);const refreshed:any=await api('/admin/safety-checks/'+current.id);setCurrent(refreshed);setHistory(items=>items.map(item=>item.id===refreshed.id?refreshed:item));const refreshedRoom=refreshed.rooms?.find((room:any)=>room.room_id===selectedRoomId&&!room.checked_at);if(refreshedRoom&&(resetRoom||refreshedRoom.expected_count!==previous?.expected_count)){setObserved(refreshedRoom.expected_count);setNote('')}return refreshed};
  const start=async()=>{try{const result=await api('/admin/safety-checks',{method:'POST',body:JSON.stringify({staff_id:staffId,staff_pin:pin})});setPin('');setSelectedRoomId('');setCurrent(result);await load()}catch(error:any){setPin('');notice(error.message)}};
  const confirmRoom=async()=>{if(!selected)return;try{const result=await api('/admin/safety-checks/'+current.id+'/rooms/'+selected.room_id,{method:'POST',body:JSON.stringify({expected_count:selected.expected_count,observed_count:observed,note:note.trim()||null,staff_pin:current.reauth_required?reauthPin:null})});setNote('');setReauthPin('');setSelectedRoomId('');setCurrent(result);await load()}catch(error:any){
    notice(error.message);
    if(error.status===409&&error.message==='The system count changed while this Room was being checked. Please recount.'){
      setNote('');setReauthPin('');
      try{await refreshCurrent(true)}catch(refreshError:any){notice(refreshError.message)}
    }else if(error.status===403&&error.message==='Re-enter the checker PIN to continue this older safety check'){
      try{await refreshCurrent()}catch(refreshError:any){notice(refreshError.message)}
    }
  }};
  const complete=async()=>{try{const result=await api('/admin/safety-checks/'+current.id+'/complete',{method:'POST'});setCurrent(result);await load()}catch(error:any){notice(error.message)}};
  const timezone=data.centre?.timezone||'Pacific/Auckland';
  return <section className="safety-checks"><div className="manager-toolbar"><div><h2>Centre Safety Check</h2><p>Confirm physical head counts without changing Attendance.</p></div></div>{!current||current.status!=='open'?<section className="manager-editor safety-start"><h3>Start safety check</h3><label>Checker<select value={staffId} onChange={event=>setStaffId(event.target.value)}><option value="">Select active Staff</option>{data.staff.filter((staff:any)=>staff.active).map((staff:any)=><option value={staff.id} key={staff.id}>{staff.preferred_name||staff.first_name} {staff.last_name}</option>)}</select></label><label>Staff PIN<input type="password" inputMode="numeric" autoComplete="off" value={pin} onChange={event=>setPin(event.target.value.replace(/\D/g,'').slice(0,4))}/></label><button disabled={!staffId||pin.length!==4} onClick={()=>void start()}>Start safety check</button></section>:<section className="manager-editor safety-round"><header><div><h3>{current.checked_count} of {current.room_count} Rooms checked</h3><p>Checked by {current.checker}</p><p>Started {formatCentreDateTime(current.started_at,timezone)}</p></div><progress value={current.checked_count} max={current.room_count}/></header>{selected?<div className="safety-room"><button type="button" className="minor" onClick={()=>setSelectedRoomId('')}>← Choose another Room</button><h2>{selected.room_name}</h2><p>System expects: <b>{selected.expected_count}</b></p><div className="count-stepper"><button aria-label="Decrease observed count" onClick={()=>setObserved(Math.max(0,observed-1))}>−</button><label>Observed now<input aria-label="Observed count" type="number" min={0} value={observed} onChange={event=>setObserved(Math.max(0,Number(event.target.value)))}/></label><button aria-label="Increase observed count" onClick={()=>setObserved(observed+1)}>+</button></div><details><summary>View expected children</summary><ul>{selected.expected_children.map((child:any)=><li key={child.id}>{child.name}</li>)}</ul></details>{observed===selected.expected_count?<p className="safety-match">✓ Count matches</p>:<div className="safety-mismatch"><h3>⚠ Count mismatch</h3><p>Expected: {selected.expected_count} · Observed: {observed}</p><label>Investigation note<textarea value={note} onChange={event=>setNote(event.target.value)} required/></label><button className="minor" onClick={()=>setObserved(selected.expected_count)}>Recount</button></div>}{current.reauth_required&&<label className="reauth-pin">Original checker PIN<input type="password" inputMode="numeric" value={reauthPin} onChange={event=>setReauthPin(event.target.value.replace(/\D/g,'').slice(0,4))}/></label>}<button disabled={(observed!==selected.expected_count&&note.trim().length<3)||(current.reauth_required&&reauthPin.length!==4)} onClick={()=>void confirmRoom()}>{observed===selected.expected_count?'Confirm count':'Confirm mismatch'}</button></div>:allChecked?<button onClick={()=>void complete()}>Complete safety check</button>:<div className="safety-room-chooser"><h2>Choose a Room</h2>{current.rooms.map((room:any)=><button type="button" key={room.room_id} className={`person-row ${room.checked_at?'checked':''}`} disabled={Boolean(room.checked_at)} onClick={()=>setSelectedRoomId(room.room_id)}><span><b>{room.room_name}</b><small>{room.expected_count} expected</small></span><strong>{room.checked_at?'✓ Checked':'Not checked'}</strong></button>)}</div>}</section>}{current&&current.status==='completed'&&<SafetySummary value={current} timezone={timezone}/>}<section className="safety-history"><h3>Recent checks</h3>{history.filter(item=>item.status==='completed').map(item=><details key={item.id}><summary>{formatCentreDateTime(item.completed_at||item.started_at,timezone)} · {item.checker} · {item.has_mismatch?'⚠ Mismatch':'✓ Match'}</summary><SafetySummary value={item} timezone={timezone}/></details>)}{!history.length&&<p>No previous safety checks.</p>}</section></section>;
}

function SafetySummary({value,timezone}:{value:any;timezone:string}){return <div className="safety-summary"><p>Started: {formatCentreDateTime(value.started_at,timezone)}{value.completed_at&&<> · Completed: {formatCentreDateTime(value.completed_at,timezone)}</>}</p><p>Checked by: {value.checker}</p>{value.rooms.filter((room:any)=>room.checked_at).map((room:any)=><div className="person-row" key={room.room_id}><span><b>{room.room_name}</b><small>Checked {formatCentreDateTime(room.checked_at,timezone)} · Expected {room.expected_count} · Observed {room.observed_count}{room.note?' · '+room.note:''}</small></span><b>{room.match?'✓':'⚠'}</b></div>)}</div>}

export function RoomsManager({
  data,
  reload,
  notice
}:{
  data:any;
  reload:()=>Promise<void>;
  notice:Notice;
}){
  const[selected,setSelected]=useState<any>();
  const[adding,setAdding]=useState(false);

  return(
    <section>
      <div className="manager-toolbar">
        <div>
          <h2>Classrooms</h2>
          <p>
            Select a room to view or edit its settings.
          </p>
        </div>

        <div className="inline-actions">
          <button
              onClick={()=>{setAdding(true);setSelected(undefined)}}
            >
              + Add room
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
        {data.rooms.map((room:any)=><button
                key={room.id}
                type="button"
                className="room-card"
                style={{borderColor:room.accent,backgroundColor:`${room.accent}12`}}
                onClick={()=>{setSelected(selected?.id===room.id?undefined:room);setAdding(false)}}
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
              </button>)}
      </div>
      {selected&&<section className="room-editor-section"><h2>Edit {selected.name}</h2><RoomEditor key={selected.id} room={selected} reload={reload} notice={notice}/></section>}
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


export const filterAdminChildren=(children:any[],search:string,roomFilter:string,statusFilter:string,presenceFilter:string)=>{
  const query=search.trim().toLowerCase();
  return children.filter((child:any)=>(!query||[child.first_name,child.last_name,child.preferred_name,child.enrolled_room,child.physical_room,child.dob].filter(Boolean).join(' ').toLowerCase().includes(query))&&(!roomFilter||child.room_id===roomFilter)&&(!statusFilter||(statusFilter==='active'?child.active!==false:child.active===false))&&(!presenceFilter||(presenceFilter==='present'?child.present===true:child.present!==true)));
};

export function ChildrenManager({
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
  const[roomFilter,setRoomFilter]=useState('');
  const[statusFilter,setStatusFilter]=useState('');
  const[presenceFilter,setPresenceFilter]=useState('');
  const[selectedChildId,setSelectedChildId]=useState('');
  const selected=data.children.find((child:any)=>child.id===selectedChildId);

  const filtered=useMemo(()=>{
    return filterAdminChildren(data.children,search,roomFilter,statusFilter,presenceFilter);
  },[data.children,search,roomFilter,statusFilter,presenceFilter]);

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
          <ClearableSearch className="manager-search" label="Search children" placeholder="Search children…" value={search} onChange={setSearch}/>
          <select aria-label="Filter children by room" value={roomFilter} onChange={event=>setRoomFilter(event.target.value)}><option value="">All rooms</option>{data.rooms.map((room:any)=><option key={room.id} value={room.id}>{room.name}</option>)}</select>
          <select aria-label="Filter children by status" value={statusFilter} onChange={event=>setStatusFilter(event.target.value)}><option value="">All status</option><option value="active">Active</option><option value="archived">Archived</option></select>
          <select aria-label="Filter children by presence" value={presenceFilter} onChange={event=>setPresenceFilter(event.target.value)}><option value="">All presence</option><option value="present">Present</option><option value="absent">Absent</option></select>

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
          <ChildEditor child={selected} rooms={data.rooms} reload={reload} notice={notice} canDelete={data.account?.role==='admin'}/>
          <h4>Linked families</h4>
          <div className="person-list">{selected.families?.length?selected.families.map((family:any)=><div className="person-row" key={family.id}><span><b>{family.name}</b><small>{family.login}</small></span><small>{family.active?'Active':'Inactive'}</small></div>):<p>No family login linked.</p>}</div>
          <ChildHistory child={selected} timezone={data.centre.timezone} notice={notice} openHistory={openHistory} openRecord={openRecord}/>
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

function ChildHistory({child,timezone,notice,openHistory,openRecord}:{child:any;timezone:string;notice:Notice;openHistory:(id:string)=>void;openRecord:(item:any)=>void}){
  const[items,setItems]=useState<any[]>([]);
  useEffect(()=>{void api(`/admin/activity?child_id=${child.id}&limit=12`).then((result:any)=>setItems(result.items)).catch((error:any)=>notice(error.message))},[child.id]);
  return <section className="child-history"><div className="manager-toolbar"><h4>Recent activity</h4><button className="minor" onClick={()=>openHistory(child.id)}>View full history</button></div>{items.map(item=><button className="person-row" key={`${item.source}-${item.id}`} onClick={()=>openRecord(item)}><span><b>{item.activity||item.type}</b><small>{activityContext(item)}{item.corrected?' · corrected':''}</small></span><small>{formatCentreDateTime(item.effective_at,timezone)}</small></button>)}</section>;
}


function ChildEditor({
  child,
  rooms,
  reload,
  notice,
  cancel,
  canDelete=false
}:{
  child:any|null;
  rooms:any[];
  reload:()=>Promise<void>;
  notice:Notice;
  cancel?:()=>void;
  canDelete?:boolean;
}){
  const[firstName,setFirstName]=useState(
    child?.first_name||''
  );
  const[lastName,setLastName]=useState(
    child?.last_name||''
  );
  const[middleName,setMiddleName]=useState(child?.middle_name||'');
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
  const[confirming,setConfirming]=useState(false);
  const[accountPassword,setAccountPassword]=useState('');
  const[deleting,setDeleting]=useState(false);

  useEffect(()=>{
    setFirstName(child?.first_name||'');
    setLastName(child?.last_name||'');
    setMiddleName(child?.middle_name||'');
    setPreferredName(child?.preferred_name||'');
    setDob(child?.dob||'');
    setRoomId(child?.room_id||rooms[0]?.id||'');
    setActive(child?.active??true);
  },[child?.id,rooms[0]?.id]);

  const save=async()=>{
    if(child&&!confirming){setConfirming(true);return;}
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
            middle_name:middleName.trim()||null,
            last_name:lastName.trim(),
            preferred_name:
              preferredName.trim()||null,
            dob:dob||null,
            room_id:roomId||null,
            active,
            ...(child?{account_password:accountPassword}: {})
          })
        }
      );

      await reload();

      notice(
        child
          ?'Child updated'
          :'Child added'
      );
      setAccountPassword('');
      setConfirming(false);
    }catch(e:any){
      notice(e.message);
    }finally{
      setBusy(false);
    }
  };
  const destroy=async()=>{try{await api(`/admin/children/${child.id}/delete`,{method:'POST',body:JSON.stringify({admin_password:accountPassword,confirm:`${preferredName||firstName} ${lastName}`.trim()})});setDeleting(false);setAccountPassword('');await reload();notice('Child permanently deleted')}catch(error:any){notice(error.message)}};

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
          Middle name
          <input value={middleName} onChange={e=>setMiddleName(e.target.value)}/>
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
        {child&&canDelete&&<button className="danger minor" onClick={()=>setDeleting(true)}>Delete child</button>}
      </div>

      {!active&&
        <p className="warning-text">
          Archived children remain in
          historical records but are marked
          inactive.
        </p>
      }

      <ConfirmDialog open={confirming} title="Confirm child change" message={`${!active?'Archiving this Child removes them from normal active rosters but keeps historical records. ':''}Enter your current account password to save this child’s details.`} confirmLabel={busy?'Saving…':'Confirm and save'} disabled={!accountPassword||busy} onCancel={()=>{setConfirming(false);setAccountPassword('')}} onConfirm={()=>void save()}><label>Current account password<input autoFocus type="password" autoComplete="current-password" value={accountPassword} onChange={event=>setAccountPassword(event.target.value)}/></label></ConfirmDialog>
      <ConfirmDialog open={deleting} title="Permanently delete child?" message="Historical records will not be cascaded. This is only available if the child has never been used; otherwise archive the child instead." confirmLabel="Delete child" disabled={!accountPassword} onCancel={()=>{setDeleting(false);setAccountPassword('')}} onConfirm={()=>void destroy()}><label>Current Admin password<input autoFocus type="password" autoComplete="current-password" value={accountPassword} onChange={event=>setAccountPassword(event.target.value)}/></label><p>Type the child name exactly as shown by editing the fields before deleting.</p></ConfirmDialog>
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
  const[selected,setSelected]=useState<any>();
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
          <ClearableSearch className="manager-search" label="Search teachers" placeholder="Search teachers…" value={search} onChange={setSearch}/>

          <button
              onClick={()=>{setAdding(true);setSelected(undefined)}}
            >
              + Add teacher
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

      <div className="person-list">
        {filtered.map((staff:any)=><React.Fragment key={staff.id}><button className={`person-row ${staff.active?'':'inactive'}`} onClick={()=>{setSelected(selected?.id===staff.id?undefined:staff);setAdding(false)}}><span><b>{staff.preferred_name||staff.first_name} {staff.last_name}</b><small>{staff.employment_type}</small></span><small>{staff.active?'Active':'Inactive'} ›</small></button>{selected?.id===staff.id&&<StaffEditor staff={staff} reload={reload} notice={notice}/>}</React.Fragment>)}
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


export{Branding,centreTimezoneOptions,timezoneOffset}from'./SettingsPage';


function Help({demo}:{demo:boolean}){
  const topics=[
    [
      'Pairing',
      'Create a labeled 90-second QR pairing under Devices, confirm its room, then enter the separate three-digit challenge on the tablet.'
    ],
    ['Parent access and QR','Parents sign in separately with a Family login and PIN. The Parent QR only opens the sign-in page; a Family QR may safely prefill only its login identifier.'],
    ['Management','Children, Families and Teachers use one selected editor at a time. Search families to link children by first, last, preferred name or room. Archive records with history; permanent Delete is only for unused items.'],
    ['Attendance kiosk and late sign-in','The kiosk is device-only and requires signer name and signature. If care is selected for an absent child, confirm Mark present and continue; it records a late staff sign-in rather than inventing an arrival time.'],
    ['Alerts','Toileting can record nappy and clothing alerts. Open alerts remain visible to the Classroom and Parent until a Teacher resolves them.'],
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
    ],
    ['Activity, Audit and Data Requests','Activity expands below the selected row. Corrections keep the original, reason and Audit trail. Parent requests for older records appear in Data Requests.'],
    ['Example only — no record is saved','Sleep: Awake → Fell asleep → Woke & got up. Family: Search Mila → Add → Remove. Activity: Original → Correction → Audit history. These are local instructional examples and make no API request; this section can later host local looping media.']
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
