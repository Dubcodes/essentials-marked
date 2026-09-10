import React from'react';
const topics=[
  ['Classroom','Choose the current Room and Teacher at the top. The room colour confirms the working room. Action cards open the care workflow; live state refreshes the roster after another authorised tablet records a change.'],
  ['Attendance / Presence','This is a teacher room tool. Current Room comes first, then visitors, recent visitors, then other rooms. Mark an absent child present in this room, bring a present child into this room, end a visit, or depart the centre.'],
  ['Toileting','Select one or more children, choose Nappy or Toilet and record the outcome. An absent child can be marked present after confirmation. Supply and clothing alerts remain until resolved. Ordinary care queues during a retryable outage.'],
  ['Food','Select children and record the meal, serving and enjoyment. Extra servings stay with the serving controls. Save creates one atomic batch; a retryable outage queues the exact batch for sync.'],
  ['Sleep','Put down, Fell asleep, Wake and Got up describe one lifecycle. A child who is elsewhere or absent can be moved/marked present for sleep after confirmation; never depart a child with an open sleep.'],
  ['Sleep Check','Only sleeping children appear here. Record warmth, breathing and wellbeing, then save. Individual check timing signals when a check is due; if nobody is asleep there is nothing to record.'],
  ['Sunscreen, medicine and incidents','Sunscreen is ordinary care. Medication administration needs a live staff PIN check. Incidents stay drafts until explicitly reviewed and finalised.'],
  ['Emergency roll','Emergency Roll opens for this Room by default and includes enrolled children plus visitors. Use Whole centre when needed. Offline/stale warnings mean check another source before relying on the printout.'],
  ['Keyboard and sync','Alt+1–8 open workflows, / focuses child search, ? opens help, and Escape closes ordinary workflows. Shortcuts do not run while typing. Open Sync to see queued ordinary-care records.']
];
export function ClassroomHelp(){return <section className="help-page">{topics.map(([title,body])=><article key={title}><h3>{title}</h3><p>{body}</p></article>)}</section>}
