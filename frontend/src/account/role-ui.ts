export const adminPages=[
  'Dashboard',
  'Rooms',
  'Children',
  'Families',
  'Teachers',
  'Devices',
  'Activity log',
  'Data requests',
  'Settings',
  'Help'
]as const;

export type AdminPage=(typeof adminPages)[number];

export function accountLandingForRole(role?:string){
  return role==='teacher'?'teacher':'operations';
}

export function managementPagesForRole(role?:string):AdminPage[]{
  if(role==='admin')return [...adminPages];
  if(role==='administration'){
    return adminPages.filter(
      page=>!['Rooms','Devices'].includes(page)
    );
  }
  return [];
}

export function quickNavForRole(role?:string,parentContext=false){
  if(parentContext)return [] as Array<[string,string]>;
  if(role==='admin')return [
    ['Operations','/'],['Classroom','/classroom'],
    ['Pair tablet','/classroom/pair']
  ] as Array<[string,string]>;
  if(role==='administration')return [
    ['Operations','/'],['Classroom','/classroom']
  ] as Array<[string,string]>;
  if(role==='teacher')return [
    ['Classroom','/classroom'],['My account','/']
  ] as Array<[string,string]>;
  return [['Classroom','/classroom']] as Array<[string,string]>;
}

export const settingsSections=[
  {title:'Accounts',open:false},
  {title:'Branding',open:false}
]as const;
