export type PresenceChild={id:string;room_id:string;present?:boolean;visiting_room_id?:string|null};
export function isPhysicallyInRoom(child:PresenceChild,roomId:string){return Boolean(child.present&&((child.visiting_room_id||child.room_id)===roomId));}
export function currentRoomPresentIds(children:PresenceChild[],roomId:string){return children.filter(c=>isPhysicallyInRoom(c,roomId)).map(c=>c.id);}
export function physicalRoomStatus(child:PresenceChild,roomId:string,roomNames:Record<string,string>={}){
  if(!child.present)return 'Absent';
  if(child.visiting_room_id===roomId)return 'Visiting this room';
  if(isPhysicallyInRoom(child,roomId))return 'In this room';
  if(child.visiting_room_id)return `Visiting ${roomNames[child.visiting_room_id]||'another room'}`;
  return roomNames[child.room_id]?`Elsewhere · ${roomNames[child.room_id]}`:'Elsewhere';
}
