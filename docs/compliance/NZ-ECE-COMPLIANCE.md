# NZ ECE implementation review

Verified: 28 August 2026. This is an implementation review, **not legal certification**. Each centre must verify its own obligations and policies before a production trial.

| Topic | System behaviour reviewed | Official source |
| --- | --- | --- |
| Medicines | Medication records require selected-staff PIN confirmation, retain performed/recorded attribution and are finalised rather than bulk-corrected. Centres must configure their own authority and administration process. | [Education (Early Childhood Services) Regulations 2008, Schedule 4](https://www.legislation.govt.nz/regulation/public/2008/0204/latest/DLM1412639.html) |
| Accidents, injuries and illness | Incident entries require PIN confirmation and are preserved as finalised records. Parent acknowledgement/signature workflow remains a production hardening item. | [Licensing criteria: health and safety practices](https://www.education.govt.nz/early-childhood/operating-an-ece-service/health-and-safety) |
| Sleep | Start/end and check events include effective time, staff attribution and free-text observation. Centres must configure monitoring intervals appropriate to their sleep policy. | [Ministry of Education: Sleep](https://www.education.govt.nz/early-childhood/operating-an-ece-service/health-and-safety/sleep) |
| Attendance | Actual arrival/departure is separate from room visits and enrolment room, preserving operational attendance history. | [ECE regulations](https://www.legislation.govt.nz/regulation/public/2008/0204/latest/DLM1412501.html) |
| Privacy | Tenant-scoped server queries, parent object-access checks, secure cookie sessions, hashed credentials and no analytics by default minimise access and collection. Operators remain responsible for Privacy Act duties, access requests, retention and breach response. | [Office of the Privacy Commissioner: Privacy Act 2020](https://www.privacy.org.nz/privacy-for-agencies/privacy-act-2020/) |

Sources and regulator guidance may change. Recheck the links and obtain legal/compliance review before handling live centre data.
