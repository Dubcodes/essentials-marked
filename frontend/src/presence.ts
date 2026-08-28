export type PresenceChild={id:string;room_id:string;present?:boolean;visiting_room_id?:string|null};
export function isPhysicallyInRoom(child:PresenceChild,roomId:string){return Boolean(child.present&&((child.visiting_room_id||child.room_id)===roomId));}
export function currentRoomPresentIds(children:PresenceChild[],roomId:string){return children.filter(c=>isPhysicallyInRoom(c,roomId)).map(c=>c.id);}
