export const formatCentreDateTime=(value:string|Date,timezone='Pacific/Auckland')=>new Intl.DateTimeFormat('en-NZ',{timeZone:timezone,dateStyle:'medium',timeStyle:'short'}).format(new Date(value));
export const formatCentreTime=(value:string|Date,timezone='Pacific/Auckland')=>new Intl.DateTimeFormat('en-NZ',{timeZone:timezone,hour:'numeric',minute:'2-digit'}).format(new Date(value));
