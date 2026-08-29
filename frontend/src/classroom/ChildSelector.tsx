import React,{useMemo,useState}from'react';
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

export function ChildSelector({
  children,
  rooms,
  roomId,
  selected,
  setSelected,
  filter,
  eligibilityLabel,
  stateLabel,
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
  bulkLabel?:string;
}){
  const[q,setQ]=useState('');

  const names=Object.fromEntries(
    rooms.map(r=>[r.id,r.name])
  );

  const shown=useMemo(
    ()=>children.filter(
      c=>(c.first_name+' '+c.last_name)
          .toLowerCase()
          .includes(q.toLowerCase())
    ),
    [children,q]
  );

  const groups=[
    [
      'In this room',
      shown.filter(c=>isPhysicallyInRoom(c,roomId)&&c.room_id===roomId)
    ],
    [
      'Visiting this room',
      shown.filter(c=>isPhysicallyInRoom(c,roomId)&&c.room_id!==roomId)
    ],
    [
      'Enrolled here · absent/elsewhere',
      shown.filter(
        c=>c.room_id===roomId&&!isPhysicallyInRoom(c,roomId)
      )
    ],
    [
      'Other present children',
      shown.filter(
        c=>c.present &&
          c.room_id!==roomId &&
          !isPhysicallyInRoom(c,roomId)
      )
    ],
    [
      'Other rooms',
      q?shown.filter(
        c=>!c.present&&c.room_id!==roomId
      ):[]
    ]
  ] as [string,Child[]][];

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
          aria-label="Search children"
          value={q}
          placeholder="Search children"
          onChange={e=>setQ(e.target.value)}
        />

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
          <div key={label}>
            <h3>{label}</h3>

            <div className="childgrid">
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
