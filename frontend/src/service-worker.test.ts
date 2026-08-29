import{describe,expect,it}from'vitest';import source from'../public/sw.js?raw';
describe('service worker privacy boundary',()=>{it('bypasses every API request and rotates old application caches',()=>{expect(source).toContain("url.pathname.startsWith('/api/')");expect(source).toContain("key.startsWith(PREFIX)&&key!==CACHE");expect(source).not.toMatch(/cache\.put\([^)]*api/i)})});
