import {describe,expect,it} from 'vitest';
import {currentRoomPresentIds} from './presence';
describe('current-room presence selection',()=>it('selects only children physically in the selected room',()=>{
  const children=[{id:'a',room_id:'a',present:true},{id:'b',room_id:'b',present:true},{id:'c',room_id:'b',present:true,visiting_room_id:'a'},{id:'d',room_id:'a',present:false}];
  expect(currentRoomPresentIds(children,'a')).toEqual(['a','c']);
}));
