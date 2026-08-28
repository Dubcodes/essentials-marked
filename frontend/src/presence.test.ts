import {describe,expect,it} from 'vitest';
import {currentRoomPresentIds,physicalRoomStatus} from './presence';
describe('current-room presence selection',()=>it('covers enrolled, elsewhere, visiting, absent, and visiting-away children',()=>{
  const children=[{id:'a',room_id:'a',present:true},{id:'b',room_id:'b',present:true},{id:'c',room_id:'b',present:true,visiting_room_id:'a'},{id:'d',room_id:'a',present:false},{id:'e',room_id:'a',present:true,visiting_room_id:'b'}];
  expect(currentRoomPresentIds(children,'a')).toEqual(['a','c']);
}));
describe('physical-room status',()=>it('uses the same physical-room semantics and handles an ended visit',()=>{
  const names={a:'Kōwhai',b:'Rimu'};
  expect(physicalRoomStatus({id:'a',room_id:'a',present:true},'a',names)).toBe('In this room');
  expect(physicalRoomStatus({id:'c',room_id:'b',present:true,visiting_room_id:'a'},'a',names)).toBe('Visiting this room');
  expect(physicalRoomStatus({id:'e',room_id:'a',present:true,visiting_room_id:'b'},'a',names)).toBe('Visiting Rimu');
  expect(physicalRoomStatus({id:'d',room_id:'a',present:false},'a',names)).toBe('Absent');
  expect(physicalRoomStatus({id:'a',room_id:'a',present:true,visiting_room_id:null},'a',names)).toBe('In this room');
}));
