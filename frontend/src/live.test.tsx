// @vitest-environment jsdom
import React from'react';
import{act}from'react';
import{createRoot}from'react-dom/client';
import{afterEach,describe,expect,it,vi}from'vitest';
import{useLiveReconciliation}from'./live';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
class MockEventSource{
  static instances:MockEventSource[]=[];listeners:Record<string,Function[]>= {};closed=false;
  constructor(_url:string){MockEventSource.instances.push(this)}
  addEventListener(type:string,listener:Function){(this.listeners[type]??=[]).push(listener)}
  close(){this.closed=true}
  emit(type:string){for(const listener of this.listeners[type]||[])listener(new Event(type))}
}
function Probe({refresh}:{refresh:()=>void}){const state=useLiveReconciliation(refresh);return <span>{state}</span>}
afterEach(()=>{document.body.innerHTML='';MockEventSource.instances=[];vi.unstubAllGlobals();vi.useRealTimers()});
describe('live reconciliation',()=>{
  it('reconciles after reconnect and coalesces a burst of change signals',async()=>{vi.useFakeTimers();vi.stubGlobal('EventSource',MockEventSource);const refresh=vi.fn();const host=document.createElement('div');document.body.append(host);await act(async()=>createRoot(host).render(<Probe refresh={refresh}/>));const source=MockEventSource.instances[0];await act(async()=>source.emit('open'));await act(async()=>vi.advanceTimersByTimeAsync(300));expect(refresh).toHaveBeenCalledTimes(1);await act(async()=>{source.emit('change');source.emit('change');source.emit('reconcile');vi.advanceTimersByTime(300)});expect(refresh).toHaveBeenCalledTimes(2)});
  it('reconciles on visibility return, online recovery and the slow fallback',async()=>{vi.useFakeTimers();vi.stubGlobal('EventSource',MockEventSource);const refresh=vi.fn();const host=document.createElement('div');document.body.append(host);await act(async()=>createRoot(host).render(<Probe refresh={refresh}/>));Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});await act(async()=>{document.dispatchEvent(new Event('visibilitychange'));window.dispatchEvent(new Event('online'));vi.advanceTimersByTime(300)});expect(refresh).toHaveBeenCalledTimes(1);await act(async()=>vi.advanceTimersByTimeAsync(25000));expect(refresh).toHaveBeenCalledTimes(2)});
});
