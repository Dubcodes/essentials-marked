# Public and local origins

`PUBLIC_ORIGIN` is the HTTPS address used by Parents and administration. It is
also the allowed browser origin for production write requests.

`LOCAL_ORIGIN` may be documented for a future internal Classroom address. A
future `CLASSROOM_LOCAL_ONLY=false` switch can make that policy explicit, but
it is intentionally not enforced yet.

Local origin is defence in depth only. Device pairing and Account/Parent
authentication remain required; a raw Host header or LAN IP is not
authentication. Do not weaken Secure cookies just to make a plain-HTTP tablet
address convenient. The preferred future deployment is an internal HTTPS
hostname, ideally using split DNS, while retaining the public HTTPS origin.
