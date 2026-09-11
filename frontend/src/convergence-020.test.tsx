// @vitest-environment jsdom
import React from'react';
import{act}from'react';
import{createRoot}from'react-dom/client';
import{afterEach,describe,expect,it,vi}from'vitest';
import ActivityLog,{activityContext,auditChanges}from'./admin/ActivityLog';
import{Branding,centreTimezoneOptions,DashboardActivity,pairingShowsChallenge,SafetyChecks}from'./admin/AdminConsole';
import{QrDialog}from'./admin/FamiliesManager';
import AttendanceKiosk,{selectedRelationshipValue}from'./attendance/AttendanceKiosk';
import ParentView,{attendanceDisplayTime}from'./parent/Parent';
import{formatCentreDateTime}from'./centre-time';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
class FakeEventSource{addEventListener(){}close(){}}
const json=(value:any)=>new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
const enter=(input:HTMLInputElement,value:string)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,value);input.dispatchEvent(new Event('input',{bubbles:true}))};

afterEach(()=>{document.body.innerHTML='';vi.unstubAllGlobals();vi.useRealTimers()});

describe('0.2 settings and audit UX',()=>{
  it('offers IANA timezones with current UTC offsets and organised operational settings',async()=>{
    const options=centreTimezoneOptions('Pacific/Auckland');expect(options.find(option=>option.value==='Pacific/Auckland')?.label).toMatch(/Auckland, New Zealand — UTC[+-]\d{2}:\d{2}/);
    const host=document.createElement('div');document.body.append(host);
    const data:any={centre:{display_name:'Demo',secondary_text:'Centre',timezone:'Pacific/Auckland',parent_history_days:7,sleep_check_minutes:10,attendance_relationship_required:true,emergency_print:{columns:3,sort:'room_then_name',show_room:true}}};
    await act(async()=>createRoot(host).render(<Branding data={data} saved={()=>{}}/>));
    expect((host.querySelector('[aria-label="Centre timezone"]')as HTMLSelectElement).value).toBe('Pacific/Auckland');
    expect(host.textContent).toContain('Parent history window');expect(host.textContent).toContain('Sleep check interval');expect(host.textContent).toContain('Show room names on printed roll');expect(host.textContent).toContain('Require relationship on Parent sign-in');
  });

  it('removes the Child dropdown and automatically debounces Activity search',async()=>{
    vi.useFakeTimers();vi.stubGlobal('EventSource',FakeEventSource as any);const fetcher=vi.fn(async(_url:any)=>json({items:[]}));vi.stubGlobal('fetch',fetcher);
    const host=document.createElement('div');document.body.append(host);const data:any={centre:{timezone:'Pacific/Auckland'},children:[{id:'c',first_name:'Mila',last_name:'Chen'}],rooms:[],staff:[]};
    await act(async()=>createRoot(host).render(<ActivityLog data={data} isAdmin notice={()=>{}}/>));
    expect(host.textContent).not.toContain('All children');expect(host.textContent).not.toContain('Apply');
    await act(async()=>vi.advanceTimersByTimeAsync(300));fetcher.mockClear();
    const search=host.querySelector('[aria-label="Search activity"]')as HTMLInputElement;
    await act(async()=>enter(search,'Mila'));expect(fetcher).not.toHaveBeenCalled();
    await act(async()=>vi.advanceTimersByTimeAsync(260));expect(fetcher.mock.calls.some(call=>String(call[0]).includes('search=Mila'))).toBe(true);
  });

  it('hides consumed pairing evidence until Pair another tablet is chosen',()=>{
    expect(pairingShowsChallenge({id:'one',challenge:'123'})).toBe(true);
    expect(pairingShowsChallenge({id:'one',challenge:'123',consumed_at:'2026-09-11T00:00:00Z'})).toBe(false);
  });

  it('renders resolved audit changes and shared Dashboard context without fake placeholders',async()=>{
    const uuid='37746242-e97f-4da0-8cd7-000000000001';
    expect(auditChanges({}, {room_id:'Harakeke',mode:'classroom'})).toEqual(['Room: — → Harakeke','Device use: — → Classroom tablet']);
    expect(activityContext({source:'attendance',self_signed:true,child_name:'Ella Ross',room:'Pōhutukawa'})).toBe('Ella Ross · Pōhutukawa · Self signed');
    vi.stubGlobal('EventSource',FakeEventSource as any);vi.stubGlobal('fetch',vi.fn(async()=>json({items:[{id:'a',source:'audit',type:'created',activity:'Pairing created',room:'Harakeke',actor:'admin',effective_at:'2026-09-11T00:00:00Z',data:{room_id:uuid,mode:'classroom'},before:{},display_data:{room_id:'Harakeke',mode:'classroom'},display_before:{}},{id:'b',source:'attendance',type:'attendance',activity:'Attendance',child_name:'Ella Ross',room:'Pōhutukawa',self_signed:true,effective_at:'2026-09-11T00:00:00Z'}]})));
    const host=document.createElement('div');document.body.append(host);await act(async()=>{createRoot(host).render(<DashboardActivity timezone="Pacific/Auckland" notice={()=>{}} openAll={()=>{}} openRecord={()=>{}}/>);await Promise.resolve();await Promise.resolve()});
    expect(host.textContent).toContain('Harakeke · Classroom tablet · Created by admin');expect(host.textContent).toContain('Ella Ross · Pōhutukawa · Self signed');expect(host.textContent).not.toContain('No teacher');expect(host.textContent).not.toContain('No room');
  });

  it('shows resolved Pairing changes but keeps the raw Room UUID only in Technical details',async()=>{
    vi.useFakeTimers();vi.stubGlobal('EventSource',FakeEventSource as any);const uuid='37746242-e97f-4da0-8cd7-000000000001';
    vi.stubGlobal('fetch',vi.fn(async()=>json({items:[{id:'a',source:'audit',type:'created',activity:'Pairing created',room:'Harakeke',actor:'admin',effective_at:'2026-09-11T00:00:00Z',recorded_at:'2026-09-11T00:00:00Z',data:{room_id:uuid,label:'Classroom tablet',mode:'classroom'},before:{},display_data:{room_id:'Harakeke',label:'Classroom tablet',mode:'classroom'},display_before:{}}]})));
    const host=document.createElement('div');document.body.append(host);await act(async()=>createRoot(host).render(<ActivityLog data={{centre:{timezone:'Pacific/Auckland'},children:[],rooms:[],staff:[]}} isAdmin notice={()=>{}}/>));await act(async()=>vi.advanceTimersByTimeAsync(300));
    await act(async()=>{(host.querySelector('.person-row')as HTMLButtonElement).click()});const detail=host.querySelector('.activity-detail')!;const changed=[...detail.children].filter(node=>node.tagName==='P').map(node=>node.textContent).join(' ');
    expect(changed).toContain('Room: — → Harakeke');expect(changed).not.toContain(uuid);expect(detail.querySelector('pre')?.textContent).toContain(uuid);
  });

  it('offers departure correction only when Attendance is already closed',async()=>{
    vi.useFakeTimers();vi.stubGlobal('EventSource',FakeEventSource as any);
    for(const departed_at of [null,'2026-09-11T02:00:00Z']){
      vi.stubGlobal('fetch',vi.fn(async(url:any)=>json(String(url).includes('/corrections')?[]:{items:[{id:'a',source:'attendance',type:'attendance',activity:'Attendance',child_name:'Ella Ross',effective_at:'2026-09-11T00:00:00Z',recorded_at:'2026-09-11T00:00:00Z',data:{arrived_at:'2026-09-11T00:00:00Z',departed_at}}]})));
      const host=document.createElement('div');document.body.append(host);await act(async()=>createRoot(host).render(<ActivityLog data={{centre:{timezone:'Pacific/Auckland'},children:[],rooms:[],staff:[]}} isAdmin notice={()=>{}}/>));await act(async()=>vi.advanceTimersByTimeAsync(300));await act(async()=>{(host.querySelector('.person-row')as HTMLButtonElement).click()});await act(async()=>{([...host.querySelectorAll('button')].find(button=>button.textContent==='Correct record')as HTMLButtonElement).click()});
      expect(host.textContent?.includes('Departure time')).toBe(Boolean(departed_at));host.remove();
    }
  });

  it('formats supplied instants in the Centre timezone',()=>{
    const auckland=formatCentreDateTime('2026-01-01T00:00:00Z','Pacific/Auckland'),utc=formatCentreDateTime('2026-01-01T00:00:00Z','UTC');
    expect(auckland).not.toBe(utc);expect(auckland).toMatch(/1:00\s*pm/i);expect(utc).toMatch(/12:00\s*am/i);
  });
});

describe('0.2 kiosk and modal UX',()=>{
  it('records Other without custom text and formats carried attendance with its date',()=>{
    expect(selectedRelationshipValue('Other','')).toBe('Other');expect(selectedRelationshipValue('Other','Grandmother')).toBe('Grandmother');
    expect(attendanceDisplayTime('2026-09-10T21:55:00Z','2026-09-11','Pacific/Auckland')).toMatch(/9:55/);
    expect(attendanceDisplayTime('2026-09-09T21:55:00Z','2026-09-11','Pacific/Auckland')).toMatch(/10 Sept|10 Sep/);
  });

  it('themes the kiosk, clears Search, and separates signature actions',async()=>{
    vi.stubGlobal('fetch',vi.fn(async(url:any)=>json(String(url).includes('/relationships/')?['Mother','Other']:{centre:{display_name:'Demo'},assigned_room:{id:'a',name:'Harakeke',accent:'#123456',icon:'🌿'},relationship_required:false,default_room_id:'a',children:[{id:'c',first_name:'Mila',last_name:'Chen',room_id:'a',room_name:'Harakeke',present:false}]})));
    const host=document.createElement('div');document.body.append(host);await act(async()=>{createRoot(host).render(<AttendanceKiosk/>);await Promise.resolve()});
    expect((host.querySelector('.attendance-kiosk')as HTMLElement).style.getPropertyValue('--room-accent')).toBe('#123456');expect(host.textContent).toContain('🌿');
    const search=host.querySelector('[aria-label="Search children"]')as HTMLInputElement;await act(async()=>enter(search,'Mila'));const clear=host.querySelector('[aria-label="Clear search"]')as HTMLButtonElement;expect(clear).toBeTruthy();await act(async()=>clear.click());expect(search.value).toBe('');
    await act(async()=>{([...(host.querySelectorAll('button'))].find(button=>button.textContent?.includes('Mila Chen'))as HTMLButtonElement).click();await Promise.resolve()});
    const actions=host.querySelector('.kiosk-action-row')!;expect(actions.firstElementChild?.textContent).toBe('Clear signature');expect(actions.lastElementChild?.textContent).toBe('Confirm sign in');expect(host.textContent).not.toContain('Attendance recorded.');
  });

  it('requires an explicit DST occurrence and sends the selected second occurrence',async()=>{
    const requests:any[]=[];let correctionCalls=0;
    vi.stubGlobal('fetch',vi.fn(async(url:any,init:any)=>{const value=String(url);if(value.includes('/attendance/bootstrap'))return json({centre:{display_name:'Demo',timezone:'Pacific/Auckland'},assigned_room:{id:'a',name:'Harakeke',accent:'#123456',icon:'🌿'},relationship_required:false,default_room_id:'a',children:[{id:'c',attendance_id:'old',arrived_at:'2026-04-04T00:00:00Z',first_name:'Mila',last_name:'Chen',room_id:'a',room_name:'Harakeke',present:true,stale_attendance:true}]});if(value.includes('/relationships/'))return json([]);if(value.includes('/missing-sign-out')){requests.push(JSON.parse(init.body));correctionCalls+=1;return correctionCalls===1?new Response(JSON.stringify({detail:'That local time occurs twice because of a daylight-saving clock change; choose first or second occurrence'}),{status:422,headers:{'Content-Type':'application/json'}}):json({id:'old'})}return json({})}));
    const host=document.createElement('div');document.body.append(host);await act(async()=>{createRoot(host).render(<AttendanceKiosk/>);await Promise.resolve()});await act(async()=>{([...host.querySelectorAll('button')].find(button=>button.textContent?.includes('Mila Chen'))as HTMLButtonElement).click();await Promise.resolve()});
    const fields=host.querySelectorAll('input');const date=[...fields].find(input=>input.type==='date')!,time=[...fields].find(input=>input.type==='time')!;await act(async()=>{enter(date,'2026-04-05');enter(time,'02:30')});
    const canvas=host.querySelector('canvas')! as any;canvas.setPointerCapture=()=>{};canvas.getContext=()=>({beginPath(){},moveTo(){},lineTo(){},stroke(){},clearRect(){}});canvas.toDataURL=()=> 'data:image/png;base64,signature';await act(async()=>{canvas.dispatchEvent(new MouseEvent('pointerdown',{bubbles:true,clientX:1,clientY:1}));canvas.dispatchEvent(new MouseEvent('pointermove',{bubbles:true,clientX:2,clientY:2}))});
    let confirm=[...host.querySelectorAll('button')].find(button=>button.textContent==='Confirm previous pickup')as HTMLButtonElement;expect(confirm.disabled).toBe(false);await act(async()=>{confirm.click();await Promise.resolve();await Promise.resolve()});
    const occurrence=host.querySelector('[aria-label="Choose occurrence"]')as HTMLSelectElement;expect(occurrence).toBeTruthy();expect(occurrence.value).toBe('');confirm=[...host.querySelectorAll('button')].find(button=>button.textContent==='Confirm previous pickup')as HTMLButtonElement;expect(confirm.disabled).toBe(true);
    await act(async()=>{Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value')!.set!.call(occurrence,'1');occurrence.dispatchEvent(new Event('change',{bubbles:true}))});expect(confirm.disabled).toBe(false);await act(async()=>{confirm.click();await Promise.resolve();await Promise.resolve()});expect(requests.at(-1).fold).toBe(1);
  });

  it('keeps bounded QR content open for inside clicks and closes on backdrop or Escape',async()=>{
    const close=vi.fn(),value={title:'Ross Family',url:'https://example.test/parent?login=ross',qr_data_url:'data:image/png;base64,qr'};
    const host=document.createElement('div');document.body.append(host);const root=createRoot(host);await act(async()=>root.render(<QrDialog value={value} close={close}/>));
    await act(async()=>host.querySelector('.family-qr-card')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));expect(close).not.toHaveBeenCalled();
    await act(async()=>host.querySelector('.modal-backdrop')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));expect(close).toHaveBeenCalledTimes(1);close.mockClear();
    await act(async()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'})));expect(close).toHaveBeenCalledTimes(1);
  });
});

describe('0.2 Parent and Safety Check UX',()=>{
  it('collapses relationships and Help, then opens a compact evidence-rich signature modal',async()=>{
    vi.stubGlobal('EventSource',FakeEventSource as any);
    vi.stubGlobal('fetch',vi.fn(async(url:any)=>{const value=String(url);if(value.includes('/parent/me'))return json({children:[{id:'c',first_name:'Mila',last_name:'Chen'}],centre:'Demo',timezone:'Pacific/Auckland',today:'2026-09-11',oldest_online_date:'2026-09-05'});if(value.includes('/relationships'))return json([{id:'r',label:'Caregiver',active:true}]);if(value.includes('/signature'))return json({signature_data:'data:image/png;base64,signature',relationship:'Caregiver',signed_at:'2026-09-11T00:00:00Z'});return json({date:'2026-09-11',attendance:[{id:'a',arrived_at:'2026-09-10T22:00:00Z',room:'Harakeke',source:'parent_kiosk',device:'Harakeke Sign-in tablet',sign_in_relationship:'Caregiver',sign_in_signature_available:true}],sleep_sessions:[],events:[],alerts:[]})}));
    const host=document.createElement('div');document.body.append(host);await act(async()=>{createRoot(host).render(<ParentView/>);await Promise.resolve();await Promise.resolve();await Promise.resolve()});
    const relationships=host.querySelector('.parent-relationships')as HTMLDetailsElement,help=host.querySelector('.parent-help')as HTMLDetailsElement;expect(relationships.open).toBe(false);expect(help.open).toBe(false);expect(help.textContent).toContain('sign-out was missed');
    const view=[...host.querySelectorAll('button')].find(button=>button.textContent==='View signature')as HTMLButtonElement;await act(async()=>{view.click();await Promise.resolve()});
    expect(host.querySelector('.parent-signature-modal')).toBeTruthy();expect(host.textContent).toContain('Relationship: Caregiver');expect(host.textContent).toContain('Room: Harakeke');
  });

  it('shows a PIN-authenticated mobile count workflow and recent history',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>json([])));const host=document.createElement('div');document.body.append(host);
    await act(async()=>{createRoot(host).render(<SafetyChecks data={{staff:[{id:'s',first_name:'Sarah',last_name:'Teacher',active:true}]}} notice={()=>{}}/>);await Promise.resolve()});
    expect(host.textContent).toContain('Centre Safety Check');expect(host.textContent).toContain('Select active Staff');expect(host.querySelector('input[type="password"]')).toBeTruthy();expect(host.textContent).toContain('Recent checks');
  });

  it('reloads and resets the Room count after an expected-count conflict',async()=>{
    const room=(expected_count:number)=>({room_id:'room',room_name:'Kōwhai',expected_count,observed_count:expected_count,expected_children:Array.from({length:expected_count},(_,index)=>({id:`c${index}`,name:`Child ${index+1}`})),checked_at:null,match:null,note:null});
    const check=(expected_count:number)=>({id:'check',status:'open',staff_id:'s',checker:'Sarah T.',started_at:'2026-09-11T00:00:00Z',completed_at:null,checked_count:0,room_count:1,has_mismatch:false,rooms:[room(expected_count)]});
    const requests:any[]=[];const notice=vi.fn();
    vi.stubGlobal('fetch',vi.fn(async(url:any,init:any={})=>{requests.push({url:String(url),init});if(init.method==='POST')return new Response(JSON.stringify({detail:'The system count changed while this Room was being checked. Please recount.'}),{status:409,headers:{'Content-Type':'application/json'}});return json(String(url)==='/api/admin/safety-checks/check'?check(2):[check(1)])}));
    const host=document.createElement('div');document.body.append(host);await act(async()=>{createRoot(host).render(<SafetyChecks data={{centre:{timezone:'Pacific/Auckland'},staff:[{id:'s',first_name:'Sarah',last_name:'Teacher',active:true}]}} notice={notice}/>);await Promise.resolve();await Promise.resolve()});
    await act(async()=>{(host.querySelector('[aria-label="Decrease observed count"]')as HTMLButtonElement).click()});const note=host.querySelector('textarea')as HTMLTextAreaElement;await act(async()=>{Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')!.set!.call(note,'stale note');note.dispatchEvent(new Event('input',{bubbles:true}))});await act(async()=>{([...host.querySelectorAll('button')].find(button=>button.textContent==='Recount')as HTMLButtonElement).click()});
    await act(async()=>{([...host.querySelectorAll('button')].find(button=>button.textContent==='Confirm count')as HTMLButtonElement).click();await Promise.resolve();await Promise.resolve();await Promise.resolve()});
    const posted=JSON.parse(requests.find(request=>request.init.method==='POST').init.body);expect(posted.expected_count).toBe(1);expect(notice).toHaveBeenCalledWith('The system count changed while this Room was being checked. Please recount.');expect(host.textContent).toContain('System expects: 2');expect((host.querySelector('[aria-label="Observed count"]')as HTMLInputElement).value).toBe('2');
    await act(async()=>{(host.querySelector('[aria-label="Decrease observed count"]')as HTMLButtonElement).click()});expect((host.querySelector('textarea')as HTMLTextAreaElement).value).toBe('');
  });
});
