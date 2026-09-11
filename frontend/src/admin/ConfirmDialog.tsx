import React from'react';
import{DismissibleOverlay}from'../ui/DismissibleOverlay';

export function ConfirmDialog({open,title,message,confirmLabel='Confirm',disabled=false,onCancel,onConfirm,children}:{open:boolean;title:string;message:string;confirmLabel?:string;disabled?:boolean;onCancel:()=>void;onConfirm:()=>void;children?:React.ReactNode}){
  if(!open)return null;
  return <DismissibleOverlay onClose={onCancel} title={title} panelClass="confirmation-dialog"><p>{message}</p>{children}<div className="inline-actions"><button type="button" className="minor" onClick={onCancel}>Cancel</button><button type="button" disabled={disabled} onClick={onConfirm}>{confirmLabel}</button></div></DismissibleOverlay>;
}
