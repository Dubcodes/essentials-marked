import React,{useEffect,useMemo,useRef,useState}from'react';
import{api}from'../api';
import{groupedChildren,rosterGroupInfo}from'./ChildSelector';
import{isPhysicallyInRoom,physicalRoomStatus}from'../presence';
import{WorkflowWorkspace}from'./WorkflowWorkspace';
import{ChildRosterIdentity}from'./ChildRosterIdentity';
import type{WorkflowProps,Child}from'./types';

export function Presence(props:WorkflowProps){
 const[q,setQ]=useState(''),[presentOnly,setPresentOnly]=useState(false),searchRef=useRef<HTMLInputElement>(null);useEffect(()=>{const focus=()=>searchRef.current?.focus();window.addEventListener('classroom-focus-search',focus);return()=>window.removeEventListener('classroom-focus-search',focus)},[]);const names=Object.fromEntries(props.data.rooms.map(r=>[r.id,r.name]));
 const groups=useMemo(()=>groupedChildren(props.data.children,props.data.rooms,props.roomId,props.data.recent_visitors?.[props.roomId]||[],q,presentOnly),[props.data.children,props.data.rooms,props.roomId,props.data.recent_visitors,q,presentOnly]);
 const act=async(child:Child,action:string)=>{try{await api('/classroom/presence',{method:'POST',body:JSON.stringify({child_id:child.id,room_id:props.roomId,staff_id:props.staffId,action})});props.notice(`${child.first_name}: ${action.replaceAll('_',' ')}`);await props.refresh()}catch(e:any){props.notice(e.message)}};
 const roomName=names[props.roomId]||'this room';
 const actionFor=(child:Child)=>!child.present?['arrive',`Mark present in ${roomName}`]:child.visiting_room_id===props.roomId?['end_visit','End visit']:isPhysicallyInRoom(child,props.roomId)?['depart','Depart centre']:child.present?['visit',`Bring into ${roomName}`]:null;
 return <WorkflowWorkspace title="Attendance / Presence" close={props.close}><div className="picker-tools"><input ref={searchRef} aria-label="Search children" placeholder="Search children" value={q} onChange={e=>setQ(e.target.value)}/><button type="button" className={presentOnly?'active':'minor'} onClick={()=>setPresentOnly(value=>!value)}>Present</button></div>{groups.map(([heading,children])=>children.length?<section className="roster-group" key={heading}>{(()=>{const info=rosterGroupInfo(heading,props.data.rooms,props.roomId);return <h3 className={info.className} style={{'--room-accent':info.accent} as any}><span>{info.icon}</span>{heading}</h3>})()}<div className="child-roster">{children.map(child=>{const action=actionFor(child);return <div className="presence-row" key={`${heading}-${child.id}`}><ChildRosterIdentity child={child} state={physicalRoomStatus(child,props.roomId,names)}/>{action?<button className={action[0]==='depart'?'danger':''} onClick={()=>void act(child,action[0])}>{action[1]}</button>:<small>Absent</small>}</div>})}</div></section>:null)}</WorkflowWorkspace>;
}
