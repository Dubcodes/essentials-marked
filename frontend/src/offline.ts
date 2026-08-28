const DB='essentials-marked', STORE='queue';
function open():Promise<IDBDatabase>{return new Promise((ok,bad)=>{const r=indexedDB.open(DB,1);r.onupgradeneeded=()=>r.result.createObjectStore(STORE,{keyPath:'client_id'});r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error)})}
export async function queued(){const d=await open();return new Promise<any[]>((ok,bad)=>{const r=d.transaction(STORE).objectStore(STORE).getAll();r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error)})}
export async function save(item:any){const d=await open();await new Promise((ok,bad)=>{const r=d.transaction(STORE,'readwrite').objectStore(STORE).put(item);r.onsuccess=()=>ok(null);r.onerror=()=>bad(r.error)})}
export async function remove(id:string){const d=await open();await new Promise((ok,bad)=>{const r=d.transaction(STORE,'readwrite').objectStore(STORE).delete(id);r.onsuccess=()=>ok(null);r.onerror=()=>bad(r.error)})}
export async function sync(){for(const item of await queued()){try{const r=await fetch('/api/classroom/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});if(r.ok) await remove(item.client_id)}catch{break}}return (await queued()).length}
