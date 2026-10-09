use std::sync::Mutex;
use tauri::{Manager,PhysicalPosition,PhysicalSize,WebviewUrl,WebviewWindowBuilder};
use serde_json::{json,Value};

pub struct Selection(pub Mutex<Option<String>>);
const COMPACT_WIDTH:f64=260.0;
const COMPACT_HEIGHT:f64=220.0;
const MIN_WIDTH:f64=230.0;
const MIN_HEIGHT:f64=180.0;

#[derive(Clone,Copy)]
struct WorkArea{x:i32,y:i32,w:u32,h:u32,scale:f64}

fn geometry_path(app:&tauri::AppHandle)->Option<std::path::PathBuf>{
    if std::env::var("BJLAB_DESKTOP_SMOKE").as_deref()==Ok("1"){
        if let Ok(path)=std::env::var("BJLAB_NATIVE_ADVISOR_GEOMETRY_FILE"){return Some(path.into())}
    }
    app.path().app_data_dir().ok().map(|p|p.join("advisor-geometry.json"))
}
pub fn save_geometry(app:&tauri::AppHandle){
    if let (Some(window),Some(path))=(app.get_webview_window("advisor"),geometry_path(app)){
        // Windows reports special off-screen coordinates when minimized.
        // Neither that sentinel nor a maximized panel replaces the normal size.
        if window.is_minimized().unwrap_or(false)||window.is_maximized().unwrap_or(false){return}
        if let (Ok(position),Ok(size))=(window.outer_position(),window.inner_size()){
            if let Some(parent)=path.parent(){let _=std::fs::create_dir_all(parent);}
            let scale=window.scale_factor().unwrap_or(1.0);
            let _=std::fs::write(path,json!({"version":2,"x":position.x,"y":position.y,
                "w":size.width as f64/scale,"h":size.height as f64/scale,
                "topmost":window.is_always_on_top().unwrap_or(false)}).to_string());
        }
    }
}
fn fit_geometry(mut x:i32,mut y:i32,w:f64,h:f64,frame:(u32,u32),monitors:&[WorkArea]) -> (i32,i32,u32,u32){
    let fallback=WorkArea{x:0,y:0,w:1920,h:1080,scale:1.0};
    let chosen=monitors.iter().find(|m|x>=m.x&&(x as i64)<m.x as i64+m.w as i64&&y>=m.y&&(y as i64)<m.y as i64+m.h as i64)
        .or_else(||monitors.first()).unwrap_or(&fallback);
    let scale=chosen.scale.clamp(0.5,4.0);
    let max_w=chosen.w.saturating_sub(frame.0).max(1);let max_h=chosen.h.saturating_sub(frame.1).max(1);
    let minimum_w=((MIN_WIDTH*scale).round() as u32).min(max_w);
    let minimum_h=((MIN_HEIGHT*scale).round() as u32).min(max_h);
    let width=((w.clamp(MIN_WIDTH,1600.0)*scale).round() as u32).clamp(minimum_w,max_w);
    let height=((h.clamp(MIN_HEIGHT,1800.0)*scale).round() as u32).clamp(minimum_h,max_h);
    x=x.clamp(chosen.x,chosen.x+chosen.w.saturating_sub(width+frame.0) as i32);
    y=y.clamp(chosen.y,chosen.y+chosen.h.saturating_sub(height+frame.1) as i32);
    (x,y,width,height)
}
fn saved_geometry(app:&tauri::AppHandle)->Value{
    geometry_path(app).and_then(|p|std::fs::read_to_string(p).ok()).and_then(|s|serde_json::from_str::<Value>(&s).ok()).unwrap_or(json!({}))
}
fn restore_geometry(app:&tauri::AppHandle,window:&tauri::WebviewWindow,reset:bool){
    let saved=if reset{json!({})}else{saved_geometry(app)};
    let monitors=window.available_monitors().unwrap_or_default().iter().map(|m|{
        let area=m.work_area();WorkArea{x:area.position.x,y:area.position.y,w:area.size.width,h:area.size.height,scale:m.scale_factor()}
    }).collect::<Vec<_>>();
    let frame=match(window.outer_size(),window.inner_size()){
        (Ok(outer),Ok(inner))=>(outer.width.saturating_sub(inner.width),outer.height.saturating_sub(inner.height)),_ => (16,39)
    };
    // Legacy geometry stored physical dimensions for the former large panel.
    // Preserve its monitor position while migrating once to the compact view.
    let current=saved["version"]==2;
    let (x,y,w,h)=fit_geometry(saved["x"].as_i64().unwrap_or(60).clamp(i32::MIN as i64,i32::MAX as i64) as i32,
        saved["y"].as_i64().unwrap_or(60).clamp(i32::MIN as i64,i32::MAX as i64) as i32,
        if current{saved["w"].as_f64().unwrap_or(COMPACT_WIDTH)}else{COMPACT_WIDTH},
        if current{saved["h"].as_f64().unwrap_or(COMPACT_HEIGHT)}else{COMPACT_HEIGHT},frame,&monitors);
    let _=window.set_size(PhysicalSize::new(w,h));let _=window.set_position(PhysicalPosition::new(x,y));
}
pub fn acknowledge(app:&tauri::AppHandle,request_id:Option<&str>,error:Option<String>){
    let window=app.get_webview_window("advisor");
    let selected=app.state::<Selection>().0.lock().ok().and_then(|s|s.clone());
    let message=json!({"event":"native_advisor_ack","request_id":request_id,"stream_id":selected,
        "visible":window.as_ref().map(|w|w.is_visible().unwrap_or(false)).unwrap_or(false),
        "topmost":window.as_ref().map(|w|w.is_always_on_top().unwrap_or(false)).unwrap_or(false),"error":error,
        "window":window.as_ref().map(|w|w.label()),"main_minimized":app.get_webview_window("main").map(|w|w.is_minimized().unwrap_or(false)),
        "minimized":window.as_ref().map(|w|w.is_minimized().unwrap_or(false)),
        "scale_factor":window.as_ref().and_then(|w|w.scale_factor().ok()),
        "geometry":window.as_ref().and_then(|w|match(w.outer_position(),w.inner_size()){
            (Ok(p),Ok(s))=>Some(json!({"x":p.x,"y":p.y,"w":s.width,"h":s.height})),_=>None}),
        "monitor_count":window.as_ref().map(|w|w.available_monitors().unwrap_or_default().len())});
    if let Ok(mut backend)=app.state::<super::Backend>().0.lock(){
        if let Some(child)=backend.as_mut(){let _=child.write((message.to_string()+"\n").as_bytes());}
    }
}
pub fn command(app:&tauri::AppHandle,base:&str,message:&Value){
    let id=message["request_id"].as_str();let operation=message["operation"].as_str().unwrap_or("");
    let result=(||->Result<(),String>{
        match operation{
            "open"=>{
                let selected=message["stream_id"].as_str().ok_or("No table association")?;
                if selected.len()>80||!selected.bytes().all(|c|c.is_ascii_alphanumeric()||c==b'_'||c==b'-'){return Err("Invalid stream identity".into())}
                let mut url=base.parse::<tauri::Url>().map_err(|e|e.to_string())?;
                url.query_pairs_mut().append_pair("advisor",selected);
                let previous=app.state::<Selection>().0.lock().map_err(|e|e.to_string())?.clone();
                *app.state::<Selection>().0.lock().map_err(|e|e.to_string())?=Some(selected.to_string());
                let title=format!("{} · Live advisor · research",message["table_name"].as_str().unwrap_or("Table"));
                let hidden=std::env::var("BJLAB_DESKTOP_SMOKE").as_deref()==Ok("1");
                let window=if let Some(window)=app.get_webview_window("advisor"){
                    save_geometry(app);
                    if previous.as_deref()!=Some(selected){window.navigate(url).map_err(|e|e.to_string())?;}
                    window
                }else{
                    WebviewWindowBuilder::new(app,"advisor",WebviewUrl::External(url)).title(&title)
                        .inner_size(COMPACT_WIDTH,COMPACT_HEIGHT).min_inner_size(MIN_WIDTH,MIN_HEIGHT).decorations(true)
                        .resizable(true).content_protected(true).visible(!hidden).build().map_err(|e|e.to_string())?
                };
                window.set_title(&title).map_err(|e|e.to_string())?;
                restore_geometry(app,&window,false);
                let topmost=if message["restore_topmost"].as_bool().unwrap_or(false){
                    saved_geometry(app)["topmost"].as_bool().unwrap_or(true)
                }else{message["topmost"].as_bool().unwrap_or(false)};
                window.set_always_on_top(topmost).map_err(|e|e.to_string())?;
                if !hidden{window.unminimize().map_err(|e|e.to_string())?;window.show().map_err(|e|e.to_string())?;window.set_focus().map_err(|e|e.to_string())?;}
                save_geometry(app);
                if std::env::var("BJLAB_NATIVE_ADVISOR_SMOKE").as_deref()==Ok("1"){
                    if let Some(main)=app.get_webview_window("main"){let _=main.minimize();}
                }
            },
            "hide"=>{if let Some(window)=app.get_webview_window("advisor"){window.close().map_err(|e|e.to_string())?;}},
            "topmost"=>{if let Some(window)=app.get_webview_window("advisor"){window.set_always_on_top(message["topmost"].as_bool().unwrap_or(false)).map_err(|e|e.to_string())?;save_geometry(app);}},
            "reset"=>{if let Some(window)=app.get_webview_window("advisor"){
                window.unmaximize().map_err(|e|e.to_string())?;window.unminimize().map_err(|e|e.to_string())?;
                restore_geometry(app,&window,true);save_geometry(app);
                if std::env::var("BJLAB_DESKTOP_SMOKE").as_deref()!=Ok("1"){
                    window.show().map_err(|e|e.to_string())?;window.set_focus().map_err(|e|e.to_string())?;
                }
            }else{return Err("Open an advisor window first".into())}},
            "minimize"=>{if let Some(window)=app.get_webview_window("advisor"){save_geometry(app);window.minimize().map_err(|e|e.to_string())?;}},
            _=>return Err("Unknown native advisor operation".into())
        }Ok(())
    })();
    acknowledge(app,id,result.err());
}

#[cfg(test)]
mod tests{
    use super::{fit_geometry,WorkArea};
    fn area(x:i32,y:i32,w:u32,h:u32,scale:f64)->WorkArea{WorkArea{x,y,w,h,scale}}
    #[test]fn removed_monitor_recovers_and_retains_visible_title(){
        assert_eq!(fit_geometry(8000,-300,260.0,220.0,(16,39),&[area(0,0,1920,1040,1.0)]),(1644,0,260,220));
    }
    #[test]fn negative_monitor_coordinates_and_dpi_physical_bounds(){
        assert_eq!(fit_geometry(-1200,100,260.0,220.0,(16,39),&[area(-1920,0,1920,1080,1.5),area(0,0,2560,1440,1.0)]),(-1200,100,390,330));
        assert_eq!(fit_geometry(1500,800,4000.0,3000.0,(16,39),&[area(0,0,1920,1040,1.5)]),(0,0,1904,1001));
    }
    #[test]fn compact_minimum_and_taskbar_are_respected(){
        assert_eq!(fit_geometry(1900,1000,1.0,1.0,(16,39),&[area(0,0,1920,1040,1.0)]),(1674,821,230,180));
    }
}
