// @vitest-environment jsdom
import React from'react';
import{act}from'react';
import{createRoot}from'react-dom/client';
import{afterEach,describe,expect,it}from'vitest';
import{ChildSelector}from'./classroom/ChildSelector';
import{Presence}from'./classroom/Presence';
import{WorkflowWorkspace}from'./classroom/WorkflowWorkspace';
import{ChildrenManager,filterAdminChildren}from'./admin/AdminConsole';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
afterEach(()=>{document.body.innerHTML=''});
const rooms=[{id:'harakeke',name:'Harakeke',accent:'#176b5b',icon:'🌿'},{id:'kowhai',name:'Kōwhai',accent:'#b88a1b',icon:'🌼'}];
const classroomChildren=[{id:'noah',first_name:'Noah',last_name:'Bell',room_id:'harakeke',present:true},{id:'mila',first_name:'Mila',last_name:'Chen',room_id:'kowhai',present:true,visiting_room_id:null}];

describe('0.1.5.1 child identity and workflow header',()=>{
  it('renders Presence full name and state together, with separate initials',async()=>{
    const host=document.createElement('div');document.body.append(host);const data:any={rooms,children:classroomChildren,staff:[],recent_visitors:{}};
    await act(async()=>createRoot(host).render(<Presence data={data} roomId="harakeke" staffId="staff" close={()=>{}} refresh={async()=>{}} notice={()=>{}}/>));
    const name=[...host.querySelectorAll('.child-name')].find(node=>node.textContent==='Noah Bell');
    expect(name).toBeTruthy();expect(name?.closest('.child-identity-line')?.textContent).toContain('Noah Bell—In this room');
    expect(name?.closest('.child-roster-identity')?.querySelector('.child-avatar')?.textContent).toBe('NB');
    expect(name?.classList.contains('child-avatar')).toBe(false);
  });

  it('uses the same identity pattern in ChildSelector-backed workflows',async()=>{
    const host=document.createElement('div');document.body.append(host);
    await act(async()=>createRoot(host).render(<ChildSelector children={classroomChildren} rooms={rooms} roomId="harakeke" selected={[]} setSelected={()=>{}}/>));
    const row=[...host.querySelectorAll('.child-roster button')].find(node=>node.textContent?.includes('Mila Chen'))!;
    expect(row.querySelector('.child-roster-identity')).toBeTruthy();expect(row.querySelector('.child-name')?.textContent).toBe('Mila Chen');expect(row.querySelector('.child-avatar')?.textContent).toBe('MC');expect(row.querySelector('.child-state')?.textContent).toContain('Elsewhere');
  });

  it('groups separate accessible Help and Close controls with a visible question mark',async()=>{
    const host=document.createElement('div');document.body.append(host);
    await act(async()=>createRoot(host).render(<WorkflowWorkspace title="Food" close={()=>{}}>Details</WorkflowWorkspace>));
    const actions=host.querySelector('.workflow-header-actions')!,help=actions.querySelector('[aria-label="Help"]')as HTMLButtonElement,close=actions.querySelector('[aria-label="Close"]')as HTMLButtonElement;
    expect(help.textContent).toBe('?');expect(help.title).toBe('Help');expect(close).toBeTruthy();expect(help).not.toBe(close);expect(actions.children).toHaveLength(2);
  });

  it('adds a separate Admin presence filter and combines it with status and room',async()=>{
    const children=[{id:'1',first_name:'Noah',last_name:'Bell',room_id:'harakeke',enrolled_room:'Harakeke',active:true,present:true},{id:'2',first_name:'Jack',last_name:'Moon',room_id:'harakeke',enrolled_room:'Harakeke',active:true,present:false},{id:'3',first_name:'Finn',last_name:'Lane',room_id:'kowhai',enrolled_room:'Kōwhai',active:false,present:false},{id:'4',first_name:'Mila',last_name:'Chen',room_id:'harakeke',enrolled_room:'Harakeke',active:false,present:true}];
    expect(filterAdminChildren(children,'','harakeke','active','absent').map(child=>child.id)).toEqual(['2']);
    expect(filterAdminChildren(children,'','kowhai','archived','absent').map(child=>child.id)).toEqual(['3']);
    expect(filterAdminChildren(children,'','harakeke','archived','present').map(child=>child.id)).toEqual(['4']);
    const host=document.createElement('div');document.body.append(host);const data:any={children,rooms,account:{role:'admin'}};
    await act(async()=>createRoot(host).render(<ChildrenManager data={data} reload={async()=>{}} notice={()=>{}} openHistory={()=>{}} openRecord={()=>{}}/>));
    const select=host.querySelector('[aria-label="Filter children by presence"]')as HTMLSelectElement;
    expect([...select.options].map(option=>option.textContent)).toEqual(['All presence','Present','Absent']);
  });
});
