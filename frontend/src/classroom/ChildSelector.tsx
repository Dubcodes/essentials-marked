import React,{useEffect,useMemo,useRef,useState}from'react';
import{
  currentRoomPresentIds,
  isPhysicallyInRoom,
  physicalRoomStatus
}from'../presence';
import type{Child,Room}from'./types';

export const selectAllPhysical=(
  children:Child[],
  roomId:string,
  filter?:(child:Child)=>boolean
)=>{
  const eligible=filter?children.filter(filter):children;
  return currentRoomPresentIds(eligible,roomId);
};

export const groupedChildren=(children:Child[],rooms:Room[],roomId:string,recentVisitorIds:string[]=[],query='',presentOnly=false):[string,Child[]][]=>{
  const names=Object.fromEntries(rooms.map(room=>[room.id,room.name]));
  const shown=children.filter(c=>(c.first_name+' '+c.last_name).toLowerCase().includes(query.toLowerCase())).filter(c=>!presentOnly||!!c.present);
  const visiting=shown.filter(c=>isPhysicallyInRoom(c,roomId)&&c.room_id!==roomId);
  const visitingIds=new Set(visiting.map(c=>c.id));
  return [[names[roomId]||'Current room',shown.filter(c=>c.room_id===roomId)],['Visiting',visiting],['Recent',recentVisitorIds.map(id=>shown.find(c=>c.id===id)).filter((c):c is Child=>!!c&&!visitingIds.has(c.id))],...rooms.filter(room=>room.id!==roomId).map(room=>[room.name,shown.filter(c=>c.room_id===room.id)] as [string,Child[]])];
};

export const rosterGroupInfo=(label:string,rooms:Room[],roomId:string)=>{
  const room=rooms.find(item=>item.name===label);
  if(room)return {icon:room.icon,accent:room.accent,className:`roster-heading room-heading ${room.id===roomId?'current-room':''}`};
  return {icon:label==='Visiting'?'↔':'◷',accent:'',className:`roster-heading ${label==='Visiting'?'visiting-heading':'recent-heading'}`};
};

export function ChildSelector({
  children,
  rooms,
  roomId,
  selected,
  setSelected,
  filter,
  eligibilityLabel,
  stateLabel,
  recentVisitorIds=[],
  bulkLabel='Select all present in this room'
}:{
  children:Child[];
  rooms:Room[];
  roomId:string;
  selected:string[];
  setSelected:(ids:string[])=>void;
  filter?:(child:Child)=>boolean;
  eligibilityLabel?:(child:Child)=>string;
  stateLabel?:(child:Child)=>string;
  recentVisitorIds?:string[];
  bulkLabel?:string;
}){
  const[q,setQ]=useState('');
  const[presentOnly,setPresentOnly]=useState(false);
  const searchRef=useRef<HTMLInputElement>(null);
  useEffect(()=>{const focus=()=>searchRef.current?.focus();window.addEventListener('classroom-focus-search',focus);return()=>window.removeEventListener('classroom-focus-search',focus)},[]);

  const names=Object.fromEntries(rooms.map(r=>[r.id,r.name]));
  const groups=useMemo(()=>groupedChildren(children,rooms,roomId,recentVisitorIds,q,presentOnly),[children,rooms,roomId,recentVisitorIds,q,presentOnly]);

  const toggle=(child:Child)=>{
    if(filter&&!filter(child))return;
    setSelected(
      selected.includes(child.id)
        ? selected.filter(x=>x!==child.id)
        : [...selected,child.id]
    );
  };

  return (
    <section className="picker">
      <div className="picker-tools">
        <input
          ref={searchRef}
          aria-label="Search children"
          value={q}
          placeholder="Search children"
          onChange={e=>setQ(e.target.value)}
        />

        <button type="button" className={presentOnly?'active':'minor'} onClick={()=>setPresentOnly(value=>!value)}>Present</button>

        <button
          type="button"
          className="minor"
          onClick={()=>
            setSelected(
              selectAllPhysical(children,roomId,filter)
            )
          }
        >
          {bulkLabel}
        </button>

        <button
          type="button"
          className="minor"
          onClick={()=>setSelected([])}
        >
          Clear
        </button>
      </div>

      {groups.map(([label,items])=>
        items.length ? (
          <div key={label} className="roster-group">
            {(()=>{const info=rosterGroupInfo(label,rooms,roomId);return <h3 className={info.className} style={{'--room-accent':info.accent} as any}><span>{info.icon}</span>{label}</h3>})()}

            <div className="child-roster">
              {items.map(c=>(
                <button
                  type="button"
                  key={c.id}
                  className={`${selected.includes(c.id)?'selected':''} ${filter&&!filter(c)?'ineligible':''}`}
                  aria-disabled={filter&&!filter(c)}
                  onClick={()=>toggle(c)}
                >
                  <b>
                    {c.first_name[0]}
                    {c.last_name?.[0]||''}
                  </b>

                  <span>
                    {c.first_name}
                    <small>
                      {stateLabel?.(c)||physicalRoomStatus(c,roomId,names)}
                    </small>
                    {filter&&!filter(c)&&<small className="eligibility-reason">{eligibilityLabel?.(c)||'Unavailable for this action'}</small>}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : null
      )}
    </section>
  );
}
