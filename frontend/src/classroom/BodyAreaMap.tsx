import React from'react';

export const bodyAreaLabels:Record<string,string>={head:'Head',face:'Face',neck:'Neck',chest:'Chest',back:'Back',abdomen:'Abdomen',left_arm:'Left arm',right_arm:'Right arm',left_hand:'Left hand',right_hand:'Right hand',left_leg:'Left leg',right_leg:'Right leg',left_foot:'Left foot',right_foot:'Right foot',other:'Other'};
export const readableBodyAreas=(areas:string[])=>areas.map(area=>bodyAreaLabels[area]||area.replaceAll('_',' ')).join(', ');

function Region({area,selected,toggle,children}:{area:string;selected:boolean;toggle:(area:string)=>void;children:React.ReactNode}){
  const activate=()=>toggle(area);
  return <g className={`body-region ${selected?'selected':''}`} role="button" tabIndex={0} aria-label={bodyAreaLabels[area]} aria-pressed={selected} data-area={area} onClick={activate} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}}}>{children}<title>{bodyAreaLabels[area]}</title></g>;
}

export function BodyAreaMap({value,onChange}:{value:string[];onChange:(areas:string[])=>void}){
  const toggle=(area:string)=>onChange(value.includes(area)?value.filter(item=>item!==area):[...value,area]);
  const region=(area:string,shape:React.ReactNode)=><Region area={area} selected={value.includes(area)} toggle={toggle}>{shape}</Region>;
  return <div className="body-area-map">
    <div className="body-figure"><h3>Front</h3><p className="body-side-key">Child’s right <span>R</span> · <span>L</span> Child’s left</p><svg viewBox="0 0 180 390" aria-label="Front body areas">
      {region('head',<path d="M72 16 Q90 2 108 16 L108 35 Q90 24 72 35Z"/>)}
      {region('face',<ellipse cx="90" cy="45" rx="18" ry="20"/>)}
      {region('neck',<rect x="82" y="64" width="16" height="18" rx="5"/>)}
      {region('chest',<path d="M58 84 Q90 72 122 84 L116 150 L64 150Z"/>)}
      {region('abdomen',<path d="M64 152 L116 152 L110 210 L70 210Z"/>)}
      {region('right_arm',<path d="M55 88 L36 98 L22 215 L42 218 L64 120Z"/>)}
      {region('left_arm',<path d="M125 88 L144 98 L158 215 L138 218 L116 120Z"/>)}
      {region('right_hand',<ellipse cx="30" cy="235" rx="13" ry="20"/>)}
      {region('left_hand',<ellipse cx="150" cy="235" rx="13" ry="20"/>)}
      {region('right_leg',<path d="M70 212 L89 212 L84 340 L58 340Z"/>)}
      {region('left_leg',<path d="M91 212 L110 212 L122 340 L96 340Z"/>)}
      {region('right_foot',<path d="M58 342 L84 342 L84 374 L45 374 Q43 358 58 342Z"/>)}
      {region('left_foot',<path d="M96 342 L122 342 Q137 358 135 374 L96 374Z"/>)}
      <text x="18" y="90">R</text><text x="154" y="90">L</text>
    </svg></div>
    <div className="body-figure"><h3>Back</h3><p className="body-side-key">Child’s left <span>L</span> · <span>R</span> Child’s right</p><svg viewBox="0 0 180 390" aria-label="Back body areas">
      <g className="body-outline" aria-hidden="true"><circle cx="90" cy="42" r="24"/><rect x="82" y="65" width="16" height="18" rx="5"/><path d="M58 84 Q90 72 122 84 L110 210 L70 210Z"/><path d="M55 88 L36 98 L22 235 M125 88 L144 98 L158 235 M78 210 L66 355 M102 210 L114 355"/></g>
      {region('back',<path d="M60 87 Q90 76 120 87 L112 180 Q90 194 68 180Z"/>)}
      <text x="18" y="90">L</text><text x="154" y="90">R</text>
    </svg></div>
    <button type="button" className={value.includes('other')?'body-other selected':'body-other minor'} aria-pressed={value.includes('other')} onClick={()=>toggle('other')}>Other</button>
  </div>;
}
