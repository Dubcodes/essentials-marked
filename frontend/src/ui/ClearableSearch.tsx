import React,{useRef}from'react';

export function ClearableSearch({value,onChange,label,placeholder,className='',inputClassName='',inputRef}:{value:string;onChange:(value:string)=>void;label:string;placeholder?:string;className?:string;inputClassName?:string;inputRef?:React.RefObject<HTMLInputElement>}){
  const localRef=useRef<HTMLInputElement>(null),input=inputRef||localRef;
  return <span className={`clearable-search ${className}`}><input ref={input} type="search" className={inputClassName} aria-label={label} placeholder={placeholder||label} value={value} onChange={event=>onChange(event.target.value)}/>{value&&<button type="button" className="minor search-clear" aria-label="Clear search" onClick={()=>{onChange('');queueMicrotask(()=>input.current?.focus())}}>×</button>}</span>;
}
