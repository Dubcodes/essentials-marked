import React from'react';
import type{Child}from'./types';

export function ChildRosterIdentity({child,state,detail}:{child:Child;state:string;detail?:string}){
  const name=`${child.first_name} ${child.last_name||''}`.trim();
  return <span className="child-roster-identity"><span className="child-avatar" aria-hidden="true">{child.first_name[0]}{child.last_name?.[0]||''}</span><span className="child-identity-text"><span className="child-identity-line"><span className="child-name">{name}</span><span className="child-identity-separator" aria-hidden="true">—</span><span className="child-state">{state}</span></span>{detail&&<span className="eligibility-reason">{detail}</span>}</span></span>;
}
