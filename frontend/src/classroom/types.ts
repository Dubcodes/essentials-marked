export type Child={
  id:string;
  first_name:string;
  last_name:string;
  room_id:string;
  present?:boolean;
  visiting_room_id?:string|null;
  arrived_at?:string|null;
};

export type Staff={
  id:string;
  name:string;
};

export type Room={
  id:string;
  name:string;
  accent:string;
  icon:string;
};

export type Bootstrap={
  device_id:string;
  default_room_id:string;
  rooms:Room[];
  staff:Staff[];
  children:Child[];
  unread_notes:number;
  incident_drafts?:number;
  recent_visitors?:Record<string,string[]>;
  last_confirmed_at?:string;
  centre?:{display_name?:string;secondary_text?:string;logo_url?:string|null;timezone?:string};
};

export type WorkflowProps={
  data:Bootstrap;
  roomId:string;
  staffId:string;
  close:()=>void;
  refresh:()=>Promise<void>;
  notice:(message:string)=>void;
};

function fallbackUuid():string {
  const cryptoApi = globalThis.crypto;

  if (!cryptoApi?.getRandomValues) {
    throw new Error(
      'Secure random ID generation is unavailable in this browser.'
    );
  }

  const bytes = new Uint8Array(16);
  cryptoApi.getRandomValues(bytes);

  // RFC 4122 version 4 UUID bits.
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(
    bytes,
    value => value.toString(16).padStart(2,'0')
  ).join('');

  return [
    hex.slice(0,8),
    hex.slice(8,12),
    hex.slice(12,16),
    hex.slice(16,20),
    hex.slice(20)
  ].join('-');
}

export const operationId=(prefix:string)=>{
  const cryptoApi = globalThis.crypto;

  const uuid =
    typeof cryptoApi?.randomUUID === 'function'
      ? cryptoApi.randomUUID()
      : fallbackUuid();

  return `${prefix}-${uuid}`;
};

export const isoOrNow=(value:string)=>
  value
    ? new Date(value).toISOString()
    : new Date().toISOString();
