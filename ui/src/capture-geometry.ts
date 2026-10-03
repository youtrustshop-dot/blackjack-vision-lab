export type Region=[number,number,number,number];
export type Layout=Record<string,Region>;

export function captureGeometry(width:number,height:number,region:Region=[0,0,1,1],maxEdge:number|null=1920,maxPixels=5_000_000){
 if(!Number.isFinite(width)||!Number.isFinite(height)||width<1||height<1||region.some(v=>!Number.isFinite(v))||region[0]<0||region[1]<0||region[2]<=0||region[3]<=0||region[0]+region[2]>1.000000001||region[1]+region[3]>1.000000001)throw new Error('Select a valid region inside the video.');
 const x=Math.floor(region[0]*width+1e-9),y=Math.floor(region[1]*height+1e-9);
 const w=Math.min(width-x,Math.ceil((region[0]+region[2])*width-1e-9)-x),h=Math.min(height-y,Math.ceil((region[1]+region[3])*height-1e-9)-y);
 const scale=Math.min(1,maxEdge?maxEdge/Math.max(w,h):1,Math.sqrt(maxPixels/(w*h)));
 return {source_size:[width,height],source_rect:[x,y,w,h],upload_size:[Math.max(1,Math.floor(w*scale)),Math.max(1,Math.floor(h*scale))],scale,native:scale===1};
}

export function cropLayout(layout:Layout,width:number,height:number):Layout{
 const {source_rect:[x,y,w,h]}=captureGeometry(width,height,layout.table,null);
 return Object.fromEntries(Object.entries(layout).map(([key,[rx,ry,rw,rh]])=>[key,key==='table'?[0,0,1,1]:[(rx*width-x)/w,(ry*height-y)/h,rw*width/w,rh*height/h]]));
}

export function sourceDetectionBox(box:number[],geometry?:{source_rect:number[];upload_size:number[]}){
 if(!geometry)return box;
 const [x,y,w,h]=geometry.source_rect,[uw,uh]=geometry.upload_size;
 return [x+box[0]*w/uw,y+box[1]*h/uh,box[2]*w/uw,box[3]*h/uh];
}

/** object-fit:contain: blank bands are outside the video, never source pixels. */
export function previewPoint(clientX:number,clientY:number,box:{left:number;top:number;width:number;height:number},width:number,height:number):[number,number]|null{
 const scale=Math.min(box.width/width,box.height/height),w=width*scale,h=height*scale;
 const x=(clientX-box.left-(box.width-w)/2)/w,y=(clientY-box.top-(box.height-h)/2)/h;
 return x>=0&&x<=1&&y>=0&&y<=1?[x,y]:null;
}
