// @vitest-environment jsdom
import React from'react';
import{act}from'react';
import{createRoot}from'react-dom/client';
import{afterEach,describe,expect,it}from'vitest';
import TeacherLanding from'./TeacherLanding';
import{accountLandingForRole,managementPagesForRole,quickNavForRole,settingsSections}from'./role-ui';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
afterEach(()=>{document.body.innerHTML=''});

describe('role-aware account UI',()=>{
  it('keeps structural Settings controls exclusive to Admin',()=>{
    expect(managementPagesForRole('admin')).toContain('Settings');
    expect(managementPagesForRole('admin')).toContain('Teachers');
    expect(managementPagesForRole('admin')).not.toContain('Staff');
    expect(managementPagesForRole('administration')).toEqual([
      'Dashboard','Children','Families','Teachers','Records',
      'Audit log','Data requests','Help'
    ]);
    expect(managementPagesForRole('teacher')).toEqual([]);
  });

  it('does not offer unrelated cross-context navigation',()=>{
    expect(quickNavForRole('teacher')).toEqual([
      ['Classroom','/classroom'],['My account','/']
    ]);
    expect(quickNavForRole('administration')).toEqual([
      ['Operations','/'],['Classroom','/classroom']
    ]);
    expect(quickNavForRole('admin')).toEqual([
      ['Operations','/'],['Classroom','/classroom'],
      ['Pair tablet','/classroom/pair']
    ]);
    expect(quickNavForRole('admin',true)).toEqual([]);
  });

  it('routes Teachers to the restricted account landing',async()=>{
    expect(accountLandingForRole('teacher')).toBe('teacher');
    expect(accountLandingForRole('administration')).toBe('operations');
    const host=document.createElement('div');
    document.body.append(host);
    await act(async()=>createRoot(host).render(React.createElement(TeacherLanding,{account:{email:'teacher@test',centre_name:'Centre'}})));
    expect(host.textContent).toContain('Teacher account');
    expect(host.querySelector('a[href="/classroom"]')?.textContent).toBe('Open Classroom');
    expect(host.textContent).toContain('My account');
    expect(host.textContent).toContain('Sign out');
    expect(host.textContent).not.toContain('Operations');
  });

  it('opens account management before the optional branding panel',()=>{
    expect(settingsSections).toEqual([
      {title:'Accounts',open:true},{title:'Branding',open:false}
    ]);
  });
});
