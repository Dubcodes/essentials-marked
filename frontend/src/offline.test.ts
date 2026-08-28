import {describe,expect,it} from 'vitest';
import {sanitizeForLocalStorage} from './offline';
describe('offline secret handling',()=>{
  it('removes PINs and other authentication fields recursively before local persistence',()=>{
    const item=sanitizeForLocalStorage({staff_pin:'1234',data:{note:'safe',pin:'1234',nested:{token:'secret'}}});
    expect(JSON.stringify(item)).not.toContain('1234');
    expect(JSON.stringify(item)).not.toContain('secret');
    expect(item).toEqual({data:{note:'safe',nested:{}}});
  });
});
