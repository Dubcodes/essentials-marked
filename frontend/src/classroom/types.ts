export type Child={id:string;first_name:string;last_name:string;room_id:string;present?:boolean;visiting_room_id?:string|null};
export type Staff={id:string;name:string};
export type Room={id:string;name:string;accent:string;icon:string};
export type Bootstrap={device_id:string;default_room_id:string;rooms:Room[];staff:Staff[];children:Child[];unread_notes:number};
export type WorkflowProps={data:Bootstrap;roomId:string;staffId:string;close:()=>void;refresh:()=>Promise<void>;notice:(message:string)=>void};
export const operationId=(prefix:string)=>`${prefix}-${crypto.randomUUID()}`;
export const isoOrNow=(value:string)=>value?new Date(value).toISOString():new Date().toISOString();
