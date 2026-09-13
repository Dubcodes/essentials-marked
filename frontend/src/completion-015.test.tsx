// @vitest-environment jsdom
import React,{useState}from'react';
import{act}from'react';
import{createRoot}from'react-dom/client';
import{afterEach,describe,expect,it,vi}from'vitest';
import{WorkflowWorkspace}from'./classroom/WorkflowWorkspace';
import{SleepWorkflow}from'./classroom/Sleep';
import AttendanceKiosk,{attendanceRoster}from'./attendance/AttendanceKiosk';
import{sortEmergencyChildren}from'./classroom/Classroom';
import{attendancePresentation}from'./parent/Parent';
import{ParentNotes}from'./classroom/ParentNotes';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
afterEach(()=>{document.body.innerHTML='';vi.unstubAllGlobals()});

it('keeps the contextual Help shortcut typing-safe while supporting ? and Escape elsewhere',async()=>{
  const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
  await act(async()=>root.render(<WorkflowWorkspace title="Food" close={()=>{}}><textarea aria-label="Optional note"/></WorkflowWorkspace>));
  const note=host.querySelector('textarea')as HTMLTextAreaElement,typed=new KeyboardEvent('keydown',{key:'?',bubbles:true,cancelable:true});
  await act(async()=>note.dispatchEvent(typed));expect(typed.defaultPrevented).toBe(false);expect(host.querySelector('[aria-label="Food help"]')).toBeNull();
  await act(async()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:'?',bubbles:true,cancelable:true})));expect(host.querySelector('[aria-label="Food help"]')).not.toBeNull();
  await act(async()=>note.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true})));expect(host.querySelector('[aria-label="Food help"]')).toBeNull();
  await act(async()=>root.unmount());
});

describe('0.1.5 completion UI',()=>{
  it('uses the assigned room as the empty-search roster and searches all active children',()=>{
    const children=[{id:'a',first_name:'Ava',last_name:'One',room_id:'room-a'},{id:'b',first_name:'Mila',last_name:'Two',room_id:'room-b'}];
    expect(attendanceRoster(children,'   ','room-a').map(child=>child.id)).toEqual(['a']);
    expect(attendanceRoster(children,'mila','room-a').map(child=>child.id)).toEqual(['b']);
  });

  it('sorts the emergency roll by child name or displayed physical room',()=>{
    const children=[{id:'z',first_name:'Zoe',last_name:'Able',physical:'A Room'},{id:'a',first_name:'Amy',last_name:'Zulu',physical:'Z Room'}],location=(child:any)=>child.physical;
    expect(sortEmergencyChildren(children,'alphabetical',location).map(child=>child.id)).toEqual(['a','z']);
    expect(sortEmergencyChildren(children,'room_then_name',location).map(child=>child.id)).toEqual(['z','a']);
  });

  it('opens contextual help without remounting or clearing workflow state',async()=>{
    const host=document.createElement('div');document.body.append(host);
    function Form(){const[value,setValue]=useState('draft note');return <WorkflowWorkspace title="Food" close={()=>{}}><input aria-label="Draft" value={value} onChange={e=>setValue(e.target.value)}/></WorkflowWorkspace>}
    await act(async()=>createRoot(host).render(<Form/>));
    await act(async()=>{(host.querySelector('button') as HTMLButtonElement).click()});
    expect(host.textContent).toContain('Food Help');expect(host.textContent).toContain('atomic batch');expect((host.querySelector('[aria-label="Draft"]')as HTMLInputElement).value).toBe('draft note');
    await act(async()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})));
    expect(host.textContent).not.toContain('Food Help');expect((host.querySelector('[aria-label="Draft"]')as HTMLInputElement).value).toBe('draft note');
  });

  it('explains Presence and Sleep edge cases in their own help',async()=>{
    const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>root.render(<WorkflowWorkspace title="Attendance / Presence" close={()=>{}}>x</WorkflowWorkspace>));await act(async()=>{(host.querySelector('button')as HTMLButtonElement).click()});expect(host.textContent).toContain('Recent');expect(host.textContent).toContain('End visit');
    await act(async()=>root.render(<WorkflowWorkspace title="Sleep" close={()=>{}}>x</WorkflowWorkspace>));await act(async()=>{(host.querySelector('button')as HTMLButtonElement).click()});expect(host.textContent).toContain('active sleep in another room');expect(host.textContent).toContain('Wake and got up');
  });

  it('uses explicit incident and medicine help contexts without clearing mounted state',async()=>{
    const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    for(const [title,helpContext,expected] of [['Incident / Injury','incident','Finalisation requires connectivity'],['Review incident','incident','Finalisation requires connectivity'],['Medicine','medicine','live connection and PIN'],['Receive medication','medicine','live connection and PIN'],['Administer medication','medicine','live connection and PIN']]){
      function Stateful(){const[value,setValue]=useState(`${title} state`);return <WorkflowWorkspace title={title} helpContext={helpContext} close={()=>{}}><input aria-label="Preserved state" value={value} onChange={event=>setValue(event.target.value)}/></WorkflowWorkspace>}
      await act(async()=>root.render(<Stateful/>));await act(async()=>{(host.querySelector('.workflow-header-actions .minor')as HTMLButtonElement).click()});
      expect(host.textContent).toContain(expected);expect((host.querySelector('[aria-label="Preserved state"]')as HTMLInputElement).value).toBe(`${title} state`);
      await act(async()=>{(host.querySelector('[aria-label="Close help"]')as HTMLButtonElement).click()});
    }
  });

  it('confirms a present-elsewhere child before preparing sleep and keeps the form open',async()=>{
    const calls:string[]=[];vi.stubGlobal('fetch',vi.fn(async(url:any)=>{calls.push(String(url));return new Response(JSON.stringify(String(url).includes('sleep-status')?{sessions:[]}:{ok:true}),{status:200,headers:{'Content-Type':'application/json'}})}));
    const host=document.createElement('div');document.body.append(host);const data:any={rooms:[{id:'a',name:'Harakeke',accent:'#000',icon:''},{id:'b',name:'Kōwhai',accent:'#000',icon:''}],children:[{id:'c',first_name:'Mila',last_name:'Chen',room_id:'b',present:true}],staff:[],recent_vis_visitors:{}};
    await act(async()=>createRoot(host).render(<SleepWorkflow data={data} roomId="a" staffId="s" close={()=>{}} refresh={async()=>{}} notice={()=>{}}/>));await act(async()=>{await Promise.resolve()});
    const mila=[...host.querySelectorAll('button')].find(x=>x.textContent?.includes('Mila Chen'))as HTMLButtonElement;await act(async()=>mila.click());expect(host.textContent).toContain('Mila Chen is currently in Kōwhai');expect(calls.some(x=>x.includes('sleep/prepare'))).toBe(false);
    const confirm=[...host.querySelectorAll('button')].find(x=>x.textContent==='Move to Harakeke and continue')as HTMLButtonElement;await act(async()=>{confirm.click();await Promise.resolve();await Promise.resolve()});expect(calls.some(x=>x.includes('sleep/prepare'))).toBe(true);expect(host.textContent).toContain('Sleep');
  });

  it('requires a drawn kiosk signature and disables confirmation again after Clear',async()=>{
    const context={beginPath:vi.fn(),moveTo:vi.fn(),lineTo:vi.fn(),stroke:vi.fn(),clearRect:vi.fn()};
    Object.defineProperty(HTMLCanvasElement.prototype,'getContext',{configurable:true,value:()=>context});
    Object.defineProperty(HTMLCanvasElement.prototype,'toDataURL',{configurable:true,value:()=>`data:image/png;base64,${'x'.repeat(200)}`});
    Object.defineProperty(HTMLCanvasElement.prototype,'setPointerCapture',{configurable:true,value:vi.fn()});
    Object.defineProperty(HTMLCanvasElement.prototype,'getBoundingClientRect',{configurable:true,value:()=>({left:0,top:0,width:700,height:220})});
    vi.stubGlobal('fetch',vi.fn(async(url:any)=>new Response(JSON.stringify(String(url).includes('/relationships/')?['Mother']:{centre:{display_name:'Demo'},assigned_room:'Harakeke',default_room_id:'a',children:[{id:'c',first_name:'Mila',last_name:'Chen',room_id:'a',room_name:'Harakeke',present:false}]}),{status:200,headers:{'Content-Type':'application/json'}})));
    const host=document.createElement('div');document.body.append(host);
    await act(async()=>{createRoot(host).render(<AttendanceKiosk/>);await Promise.resolve()});
    await act(async()=>{([...(host.querySelectorAll('button'))].find(button=>button.textContent?.includes('Mila Chen'))as HTMLButtonElement).click();await Promise.resolve()});
    await act(async()=>{([...(host.querySelectorAll('button'))].find(button=>button.textContent==='Mother')as HTMLButtonElement).click()});
    const confirm=()=>[...host.querySelectorAll('button')].find(button=>button.textContent==='Confirm sign in')as HTMLButtonElement;
    expect(confirm().disabled).toBe(true);
    const canvas=host.querySelector('canvas')as HTMLCanvasElement;
    const pointer=(name:string,x:number)=>{const event=new Event(name,{bubbles:true});Object.assign(event,{clientX:x,clientY:x,pointerId:1});canvas.dispatchEvent(event)};
    await act(async()=>{pointer('pointerdown',10);pointer('pointermove',30)});
    expect(confirm().disabled).toBe(false);
    await act(async()=>{([...(host.querySelectorAll('button'))].find(button=>button.textContent==='Clear signature')as HTMLButtonElement).click()});
    expect(confirm().disabled).toBe(true);
  });

  it('resets kiosk attribution between children, ignores stale choices, and avoids sign-out into wording',async()=>{
    let resolveA!:(response:Response)=>void,resolveB!:(response:Response)=>void;
    const requestA=new Promise<Response>(resolve=>{resolveA=resolve}),requestB=new Promise<Response>(resolve=>{resolveB=resolve});
    vi.stubGlobal('fetch',vi.fn((url:any)=>{const value=String(url);if(value.includes('/relationships/a'))return requestA;if(value.includes('/relationships/b'))return requestB;return Promise.resolve(new Response(JSON.stringify({centre:{display_name:'Demo'},assigned_room:'Harakeke',default_room_id:'a',children:[{id:'a',first_name:'Ava',last_name:'One',room_id:'a',room_name:'Harakeke',present:false},{id:'b',first_name:'Bea',last_name:'Two',room_id:'b',room_name:'Kōwhai',present:true}]}),{status:200,headers:{'Content-Type':'application/json'}}))}));
    const host=document.createElement('div');document.body.append(host);
    await act(async()=>{createRoot(host).render(<AttendanceKiosk/>);await Promise.resolve()});
    await act(async()=>{([...(host.querySelectorAll('button'))].find(button=>button.textContent?.includes('Ava One'))as HTMLButtonElement).click()});
    await act(async()=>{([...(host.querySelectorAll('button'))].find(button=>button.textContent==='← Back')as HTMLButtonElement).click()});
    await act(async()=>{const search=host.querySelector('[aria-label="Search children"]')as HTMLInputElement;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(search,'Bea');search.dispatchEvent(new Event('input',{bubbles:true}))});
    await act(async()=>{([...(host.querySelectorAll('button'))].find(button=>button.textContent?.includes('Bea Two'))as HTMLButtonElement).click()});
    await act(async()=>{resolveA(new Response(JSON.stringify(['Grandparent']),{status:200,headers:{'Content-Type':'application/json'}}));await Promise.resolve()});
    expect(host.textContent).not.toContain('Grandparent');
    await act(async()=>{resolveB(new Response(JSON.stringify(['Caregiver']),{status:200,headers:{'Content-Type':'application/json'}}));await Promise.resolve()});
    expect(host.textContent).toContain('Caregiver');expect(host.textContent).toContain('Bea is enrolled in Kōwhai.');expect(host.textContent).not.toContain('Sign Bea into');
  });

  it('presents drop-off and pick-up attribution from their own attendance phase',()=>{
    const parent:any={id:'attendance',source:'parent_kiosk',staff:null,sign_in_relationship:'Mother',sign_out_relationship:'Caregiver',sign_in_signature_available:true,sign_out_signature_available:true};
    expect(attendancePresentation('Drop off',parent)).toMatchObject({source:'Parent sign-in',relationship:'Mother',staff:null,signatureAvailable:true,purpose:'kiosk_sign_in'});
    expect(attendancePresentation('Pick up',parent)).toMatchObject({source:'Parent sign-out',relationship:'Caregiver',staff:null,signatureAvailable:true,purpose:'kiosk_sign_out'});
    const teacherThenParent:any={...parent,source:'classroom',late_sign_in:true,staff:'Sarah'};
    expect(attendancePresentation('Drop off',teacherThenParent)).toMatchObject({source:'Teacher late sign-in',staff:'Sarah'});
    expect(attendancePresentation('Pick up',teacherThenParent)).toMatchObject({source:'Parent sign-out',staff:null});
  });

  it('moves an active sleep without selecting the child for a second lifecycle action',async()=>{
    const calls:{url:string;method:string}[]=[];let moved=false;
    vi.stubGlobal('fetch',vi.fn(async(url:any,init?:RequestInit)=>{const value=String(url);calls.push({url:value,method:init?.method||'GET'});if(value.includes('sleep-status'))return new Response(JSON.stringify({sessions:[{id:'sleep-1',child_id:'c',room_id:moved?'a':'b',state:'sleeping',stale:false}]}),{status:200,headers:{'Content-Type':'application/json'}});if(value.includes('sleep/move'))moved=true;return new Response(JSON.stringify({ok:true}),{status:200,headers:{'Content-Type':'application/json'}})}));
    const host=document.createElement('div');document.body.append(host);const data:any={rooms:[{id:'a',name:'Harakeke',accent:'#000',icon:''},{id:'b',name:'Kōwhai',accent:'#000',icon:''}],children:[{id:'c',first_name:'Mila',last_name:'Chen',room_id:'b',present:true}],staff:[],recent_visitors:{}};
    await act(async()=>{createRoot(host).render(<SleepWorkflow data={data} roomId="a" staffId="s" close={()=>{}} refresh={async()=>{}} notice={()=>{}}/>);await Promise.resolve()});
    await act(async()=>{([...(host.querySelectorAll('.child-roster button'))].find(button=>button.textContent?.includes('Mila Chen'))as HTMLButtonElement).click()});
    await act(async()=>{([...(host.querySelectorAll('button'))].find(button=>button.textContent==='Move sleep to Harakeke')as HTMLButtonElement).click();await Promise.resolve();await Promise.resolve()});
    expect(calls.some(call=>call.url.includes('sleep/move'))).toBe(true);expect(host.querySelector('.child-roster button')?.classList.contains('selected')).toBe(false);
    expect(([...host.querySelectorAll('button')].find(button=>button.textContent==='Record put down')as HTMLButtonElement).disabled).toBe(true);
    expect(calls.filter(call=>call.url.endsWith('/api/classroom/sleep')&&call.method==='POST')).toHaveLength(0);
  });

  it('gives Parent Notes the Notes Help context',async()=>{
    const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify([]),{status:200,headers:{'Content-Type':'application/json'}})));
    const props:any={data:{},roomId:'a',staffId:'s',close:()=>{},refresh:async()=>{},notice:()=>{}};
    await act(async()=>{root.render(<ParentNotes {...props}/>);await Promise.resolve()});
    await act(async()=>{(host.querySelector('[aria-label="Help"]')as HTMLButtonElement).click()});
    expect(host.querySelector('[aria-label="Parent notes help"]')).not.toBeNull();expect(host.textContent).toContain('mark them read');
  });
});
