import React,{useEffect,useRef,useState}from'react';
import{api}from'../api';

export const attendanceRoster=(children:any[],search:string,defaultRoomId?:string|null)=>{const query=search.trim().toLowerCase();return children.filter(child=>query?`${child.first_name} ${child.last_name}`.toLowerCase().includes(query):child.room_id===defaultRoomId)};

export default function AttendanceKiosk(){
  const[data,setData]=useState<any>(),[search,setSearch]=useState(''),[selected,setSelected]=useState<any>(),[relationship,setRelationship]=useState(''),[custom,setCustom]=useState(''),[choices,setChoices]=useState<string[]>([]),[relationshipsLoading,setRelationshipsLoading]=useState(false),[hasSignature,setHasSignature]=useState(false),[message,setMessage]=useState('');
  const canvas=useRef<HTMLCanvasElement>(null),drawing=useRef(false),relationshipRequest=useRef(0);
  const load=()=>api('/attendance/bootstrap').then(setData).catch((error:any)=>{setMessage(error.message);if(error.status===403)location.assign('/attendance')});
  const clearSignature=()=>{drawing.current=false;canvas.current?.getContext('2d')?.clearRect(0,0,canvas.current.width,canvas.current.height);setHasSignature(false)};
  const resetConfirmation=()=>{relationshipRequest.current+=1;setRelationship('');setCustom('');setChoices([]);setRelationshipsLoading(false);clearSignature()};
  const chooseChild=(child:any)=>{resetConfirmation();setSelected(child)};
  const leaveChild=()=>{setSelected(undefined);resetConfirmation()};
  useEffect(()=>{void load()},[]);
  useEffect(()=>{
    if(!selected)return;
    const request=++relationshipRequest.current;
    setRelationshipsLoading(true);
    void api(`/attendance/relationships/${selected.id}`).then((result:string[])=>{if(request===relationshipRequest.current){setChoices(result);setRelationshipsLoading(false)}}).catch((error:any)=>{if(request===relationshipRequest.current){setMessage(error.message);setRelationshipsLoading(false)}});
    return()=>{if(request===relationshipRequest.current)relationshipRequest.current+=1};
  },[selected]);
  const point=(event:React.PointerEvent<HTMLCanvasElement>)=>{const node=canvas.current!;const box=node.getBoundingClientRect();return{x:(event.clientX-box.left)*node.width/box.width,y:(event.clientY-box.top)*node.height/box.height}};
  const start=(event:React.PointerEvent<HTMLCanvasElement>)=>{drawing.current=true;event.currentTarget.setPointerCapture(event.pointerId);const ctx=canvas.current!.getContext('2d')!;const p=point(event);ctx.beginPath();ctx.moveTo(p.x,p.y)};
  const move=(event:React.PointerEvent<HTMLCanvasElement>)=>{if(!drawing.current)return;const ctx=canvas.current!.getContext('2d')!;const p=point(event);ctx.lineWidth=3;ctx.lineCap='round';ctx.strokeStyle='#17312d';ctx.lineTo(p.x,p.y);ctx.stroke();setHasSignature(true)};
  const stop=()=>{drawing.current=false};
  const selectedRelationship=relationship==='Other'?custom.trim():relationship;
  const submit=async()=>{if(!selected||!selectedRelationship||!hasSignature)return;const signature=canvas.current?.toDataURL('image/png')||'';try{await api('/attendance/kiosk',{method:'POST',body:JSON.stringify({child_id:selected.id,room_id:selected.room_id,action:selected.present?'sign_out':'sign_in',relationship:selectedRelationship,signature_data:signature})});leaveChild();setMessage('Attendance recorded.');await load()}catch(error:any){setMessage(error.message)}};
  if(!data)return <main className="loading">Opening attendance…</main>;
  const children=attendanceRoster(data.children,search,data.default_room_id);
  return <main className="attendance-kiosk"><header><strong>{data.centre.display_name||'Essentials Marked'}</strong><span>Parent sign-in · {data.assigned_room}</span></header>{!selected?<section><h1>Sign in or sign out</h1><input aria-label="Search children" placeholder="Search children" value={search} onChange={event=>setSearch(event.target.value)}/><div className="person-list">{children.map((child:any)=><button className="presence-row" key={child.id} onClick={()=>chooseChild(child)}><span><b>{child.first_name} {child.last_name}</b><small>{child.room_name} · {child.present?'Signed in':'Not signed in'}</small></span><small>{child.present?'Sign out':'Sign in'}</small></button>)}</div></section>:<section className="kiosk-confirm"><button className="minor" onClick={leaveChild}>← Back</button><h1>{selected.present?'Sign out':'Sign in'} {selected.first_name} {selected.last_name}</h1>{selected.room_name!==data.assigned_room&&<p>{selected.present?<>{selected.first_name} is enrolled in <b>{selected.room_name}</b>.</>:<>Sign {selected.first_name} into <b>{selected.room_name}</b>?</>}</p>}<label>Signature<canvas ref={canvas} width="700" height="220" className="signature-pad" onPointerDown={start} onPointerMove={move} onPointerUp={stop} onPointerCancel={stop} onPointerLeave={stop}/></label><fieldset><legend>Relationship</legend>{relationshipsLoading?<p>Loading relationships…</p>:<div className="choices">{choices.map(choice=><button type="button" className={relationship===choice?'selected':''} onClick={()=>setRelationship(choice)} key={choice}>{choice}</button>)}</div>}{relationship==='Other'&&<input aria-label="Other relationship" value={custom} onChange={event=>setCustom(event.target.value)} placeholder="Relationship (optional)"/>}</fieldset><button className="minor" onClick={clearSignature}>Clear signature</button><button disabled={!selectedRelationship||!hasSignature||relationshipsLoading} onClick={()=>void submit()}>Confirm {selected.present?'sign out':'sign in'}</button></section>}{message&&<p role="status">{message}</p>}</main>;
}
