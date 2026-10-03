/** Server TTL is tied to the captured frame, never to a view redraw. */
export function evidenceExpiry(ttl:number,requestBegan:number,received:number){return received+Math.max(0,ttl-(received-requestBegan))}
