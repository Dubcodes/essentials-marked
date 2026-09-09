import React from'react';

export function ConfirmDialog({open,title,message,confirmLabel='Confirm',disabled=false,onCancel,onConfirm,children}:{open:boolean;title:string;message:string;confirmLabel?:string;disabled?:boolean;onCancel:()=>void;onConfirm:()=>void;children?:React.ReactNode}){
  if(!open)return null;
  return <dialog open className="confirmation-dialog" aria-labelledby="confirmation-title"><h3 id="confirmation-title">{title}</h3><p>{message}</p>{children}<div className="inline-actions"><button className="minor" onClick={onCancel}>Cancel</button><button disabled={disabled} onClick={onConfirm}>{confirmLabel}</button></div></dialog>;
}
