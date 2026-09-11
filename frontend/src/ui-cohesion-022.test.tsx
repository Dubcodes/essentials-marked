// @vitest-environment jsdom
import React,{useState}from'react';
import{act}from'react';
import{createRoot,Root}from'react-dom/client';
import{afterEach,describe,expect,it,vi}from'vitest';
import AdminConsole from'./admin/AdminConsole';
import{ConfirmDialog}from'./admin/ConfirmDialog';
import{QrDialog}from'./admin/FamiliesManager';
import{SettingsPage}from'./admin/SettingsPage';
import{attendanceRowDetail}from'./attendance/AttendanceKiosk';
import PairTablet from'./classroom/Pair';
import{WorkflowWorkspace}from'./classroom/WorkflowWorkspace';
import{ClearableSearch}from'./ui/ClearableSearch';
import{DismissibleOverlay}from'./ui/DismissibleOverlay';
import{EmergencyRoll}from'./ui/EmergencyRoll';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
class FakeEventSource{addEventListener(){}close(){}}
const json=(value:any)=>new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
const input=(element:HTMLInputElement,value:string)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(element,value);element.dispatchEvent(new Event('input',{bubbles:true}))};
let roots:Root[]=[];
async function render(node:React.ReactNode){const host=document.createElement('div');document.body.append(host);const root=createRoot(host);roots.push(root);await act(async()=>{root.render(node);await Promise.resolve();await Promise.resolve()});return host}
afterEach(async()=>{await act(async()=>roots.splice(0).forEach(root=>root.unmount()));document.body.innerHTML='';document.head.querySelectorAll('[data-emergency-orientation]').forEach(node=>node.remove());vi.unstubAllGlobals();vi.useRealTimers()});

describe('0.2.2 shared UI contracts',()=>{
  it('clears only non-empty searches, preserves focus, and never submits its form',async()=>{
    const submitted=vi.fn();function Example(){const[value,setValue]=useState('');return <form onSubmit={event=>{event.preventDefault();submitted()}}><ClearableSearch label="Search records" value={value} onChange={setValue}/></form>}
    const host=await render(<Example/>),field=host.querySelector('input')!;expect(host.querySelector('[aria-label="Clear search"]')).toBeNull();await act(async()=>input(field,'Mila'));const clear=host.querySelector('[aria-label="Clear search"]')as HTMLButtonElement;expect(clear.type).toBe('button');await act(async()=>{clear.click();await Promise.resolve()});expect(field.value).toBe('');expect(document.activeElement).toBe(field);expect(submitted).not.toHaveBeenCalled();
  });

  it('dismisses only from Escape or the backdrop and closes nested layers topmost first',async()=>{
    const outer=vi.fn(),inner=vi.fn();const host=await render(<DismissibleOverlay label="Outer" onClose={outer}><button>Inside</button><DismissibleOverlay label="Inner" onClose={inner}><button>Inner content</button></DismissibleOverlay></DismissibleOverlay>);
    await act(async()=>host.querySelector('section[aria-label="Inner"]')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));expect(inner).not.toHaveBeenCalled();expect(outer).not.toHaveBeenCalled();
    await act(async()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})));expect(inner).toHaveBeenCalledOnce();expect(outer).not.toHaveBeenCalled();
    const backdrops=host.querySelectorAll('[role="presentation"]');await act(async()=>backdrops[backdrops.length-1].dispatchEvent(new MouseEvent('click',{bubbles:true})));expect(inner).toHaveBeenCalledTimes(2);expect(outer).not.toHaveBeenCalled();
  });

  it('maps ConfirmDialog dismissal to Cancel and never Confirm',async()=>{
    const cancel=vi.fn(),confirm=vi.fn(),host=await render(<ConfirmDialog open title="Delete?" message="Careful" confirmLabel="Delete" onCancel={cancel} onConfirm={confirm}/>);await act(async()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'})));expect(cancel).toHaveBeenCalledOnce();expect(confirm).not.toHaveBeenCalled();await act(async()=>host.querySelector('[role="presentation"]')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));expect(cancel).toHaveBeenCalledTimes(2);expect(confirm).not.toHaveBeenCalled();
  });

  it('keeps Workflow Help above its workflow for Escape dismissal',async()=>{
    const close=vi.fn(),host=await render(<WorkflowWorkspace title="Sleep" close={close}><span>Sleep form</span></WorkflowWorkspace>);await act(async()=>{(host.querySelector('[aria-label="Help"]')as HTMLButtonElement).click()});expect(host.querySelector('[aria-label="Sleep help"]')).toBeTruthy();await act(async()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'})));expect(host.querySelector('[aria-label="Sleep help"]')).toBeNull();expect(close).not.toHaveBeenCalled();await act(async()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'})));expect(close).toHaveBeenCalledOnce();
  });

  it('uses the shared dismissal behavior for Family QR',async()=>{const close=vi.fn(),host=await render(<QrDialog value={{url:'https://example.test/parent',qr_data_url:'data:image/png;base64,x'}} close={close}/>);expect(host.querySelector('[role="dialog"]')?.getAttribute('aria-modal')).toBe('true');await act(async()=>host.querySelector('[role="presentation"]')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));expect(close).toHaveBeenCalledOnce()});
});

describe('0.2.2 settings, attendance and roll presentation',()=>{
  const data:any={centre:{display_name:'Demo',secondary_text:'Centre',timezone:'Pacific/Auckland',parent_history_days:7,sleep_check_minutes:10,attendance_relationship_required:true,emergency_print:{columns:3,sort:'room_then_name',show_room:true,orientation:'landscape',name_size:'large'}},account:{role:'admin'}};
  it('renders seven consistently collapsed settings panels with separate timezone and print rows',async()=>{
    const requests:any[]=[];vi.stubGlobal('fetch',vi.fn(async(_url:any,init:any)=>{requests.push(JSON.parse(init.body));return json({})}));const host=await render(<SettingsPage data={data} isAdmin saved={()=>{}}/>),panels=[...host.querySelectorAll('details.settings-panel')]as HTMLDetailsElement[];
    expect(panels.map(panel=>panel.querySelector('summary')?.textContent)).toEqual(['My sign-in','Accounts','Centre & branding','Centre timezone','Parent experience','Sleep & care','Emergency roll / printing']);expect(panels.every(panel=>!panel.open)).toBe(true);
    const branding=panels[2],timezone=panels[3],emergency=panels[6];expect(branding.querySelector('[aria-label="Centre timezone"]')).toBeNull();expect(timezone.querySelector('[aria-label="Centre timezone"]')).toBeTruthy();expect(timezone.querySelector('select')?.closest('label')?.scrollWidth).toBeLessThanOrEqual((timezone.querySelector('select')?.closest('label')?.scrollWidth||0));expect(emergency.querySelector('.emergency-settings-grid')?.contains(emergency.querySelector('.emergency-room-toggle'))).toBe(false);
    await act(async()=>timezone.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));expect(requests.at(-1)).toEqual({timezone:'Pacific/Auckland'});
  });

  it('shows the current Centre-local arrival and never substitutes an old pending time',()=>{
    const current={present:true,current_arrived_at:'2026-01-01T00:41:00Z',pending_attendance_confirmation:{arrived_at:'2025-12-28T00:00:00Z',phase:'sign_in'}};expect(attendanceRowDetail(current,'Pacific/Auckland')).toMatch(/Signed in at 1:41\s*pm/i);expect(attendanceRowDetail(current,'Pacific/Auckland')).not.toContain('28');expect(attendanceRowDetail({present:true,pending_attendance_confirmation:current.pending_attendance_confirmation},'Pacific/Auckland')).toBe('Sign-in signature needed');
  });

  it('applies shared Emergency Roll settings and preserves Classroom scope and warnings',async()=>{
    const rollData:any={centre:{display_name:'Demo',emergency_print:{columns:2,sort:'alphabetical',show_room:false,orientation:'landscape',name_size:'large'}},last_confirmed_at:'2020-01-01T00:00:00Z',rooms:[{id:'r',name:'Harakeke'},{id:'s',name:'Kōwhai'}],children:[{id:'a',first_name:'Mila',last_name:'Chen',room_id:'r',present:true},{id:'b',first_name:'Theo',last_name:'Banks',room_id:'s',present:true}]};const host=await render(<EmergencyRoll data={rollData} currentRoomId="r" classroom offline onClose={()=>{}}/>),dialog=host.querySelector('[role="dialog"]')!;expect(dialog.className).toContain('emergency-landscape');expect(dialog.className).toContain('names-large');expect(host.textContent).toContain('OFFLINE');expect(host.textContent).toContain('STALE');expect(host.textContent).toContain('Mila Chen');expect(host.textContent).not.toContain('Theo Banks');expect(document.head.querySelector('[data-emergency-orientation]')?.textContent).toContain('landscape');await act(async()=>{([...host.querySelectorAll('button')].find(button=>button.textContent==='Whole centre')as HTMLButtonElement).click()});expect(host.textContent).toContain('Theo Banks');expect(host.textContent).not.toContain('Harakeke');
  });

  it('describes and accepts the three-word Pair page while preserving the challenge',async()=>{vi.stubGlobal('fetch',vi.fn(async()=>json({})));const host=await render(<PairTablet/>),code=host.querySelector('input[placeholder="river lamp garden"]')as HTMLInputElement;expect(code).toBeTruthy();expect(host.textContent).toContain('Spaces, hyphens, and letter case are accepted');expect(host.textContent).toContain('3-digit challenge');await act(async()=>input(code,'River Lamp Garden'));expect(code.value).toBe('River Lamp Garden')});
});

describe('0.2.2 Admin pairing and dashboard',()=>{
  it('starts with QR, reveals words once, toggles locally, and opens the shared roll from the header',async()=>{
    vi.useFakeTimers();vi.stubGlobal('EventSource',FakeEventSource as any);const calls:string[]=[];const bootstrap={centre:{name:'Demo',display_name:'Demo',timezone:'Pacific/Auckland',emergency_print:{columns:3,sort:'room_then_name',show_room:true,orientation:'portrait',name_size:'standard'}},account:{role:'admin'},rooms:[{id:'r',name:'Harakeke'}],children:[],staff:[],devices:[],families:[],needs_attention:[]};
    vi.stubGlobal('fetch',vi.fn(async(url:any,init:any={})=>{const path=String(url);calls.push(`${init.method||'GET'} ${path}`);if(path.endsWith('/admin/bootstrap'))return json(bootstrap);if(path.endsWith('/admin/events'))return json([]);if(path.endsWith('/admin/pairings')&&init.method==='POST')return json({id:'p',token:'river-lamp-garden',challenge:'123',qr_data_url:'data:image/png;base64,qr',expires_at:'2099-01-01T00:00:00Z'});if(path.endsWith('/admin/pairings/p/manual-token'))return json({expires_at:'2099-01-01T00:03:00Z',manual_revealed:true});if(path.endsWith('/admin/pairings/p'))return json({id:'p'});return json({items:[]})}));
    const host=await render(<AdminConsole/>);await act(async()=>{([...host.querySelectorAll('button')].find(button=>button.textContent==='Devices')as HTMLButtonElement).click()});
    const create=[...host.querySelectorAll('button')].find(button=>button.textContent==='Pair new tablet')as HTMLButtonElement;expect(create).toBeTruthy();await act(async()=>{create.click();await Promise.resolve();await Promise.resolve()});expect(host.querySelector('img[alt="Pairing QR code"]')).toBeTruthy();expect(host.textContent).not.toContain('river lamp garden');const reveal=[...host.querySelectorAll('button')].find(button=>button.textContent==='Show pairing words')as HTMLButtonElement;await act(async()=>{reveal.click();await Promise.resolve();await Promise.resolve()});expect(host.querySelector('img[alt="Pairing QR code"]')).toBeNull();expect(host.textContent).toContain('river lamp garden');expect(calls.filter(call=>call.includes('manual-token'))).toHaveLength(1);await act(async()=>{([...host.querySelectorAll('button')].find(button=>button.textContent==='Show QR code')as HTMLButtonElement).click()});await act(async()=>{([...host.querySelectorAll('button')].find(button=>button.textContent==='Show pairing words')as HTMLButtonElement).click()});expect(calls.filter(call=>call.includes('manual-token'))).toHaveLength(1);
    expect(host.textContent).not.toContain('Quick actions');await act(async()=>{([...host.querySelectorAll('header button')].find(button=>button.textContent==='Emergency roll')as HTMLButtonElement).click()});expect(host.querySelector('.emergency-roll[role="dialog"]')).toBeTruthy();
  });
});
