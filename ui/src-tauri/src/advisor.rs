use std::sync::Mutex;
use tauri::{Manager,PhysicalPosition,PhysicalSize,WebviewUrl,WebviewWindowBuilder};
use serde_json::{json,Value};

pub struct Selection(pub Mutex<Option<String>>);

fn geometry_path(app:&tauri::AppHandle)->Option<std::path::PathBuf>{
    app.path().app_data_dir().ok().map(|p|p.join("advisor-geometry.json"))
}
pub fn save_geometry(app:&tauri::AppHandle){
    if let (Some(window),Some(path))=(app.get_webview_window("advisor"),geometry_path(app)){
        if let (Ok(position),Ok(size))=(window.outer_position(),window.inner_size()){
            if let Some(parent)=path.parent(){let _=std::fs::create_dir_all(parent);}
            let _=std::fs::write(path,json!({"x":position.x,"y":position.y,"w":size.width,"h":size.height}).to_string());
        }
    }
}
fn fit_geometry(mut x:i32,mut y:i32,w:u32,h:u32,monitors:&[(i32,i32,u32,u32)]) -> (i32,i32,u32,u32){
    if monitors.is_empty(){return (x,y,w,h)}
    let chosen=monitors.iter().find(|&&(mx,my,mw,mh)|x+(w as i32)>mx+32&&x<mx+mw as i32-32&&y+(h as i32)>my+32&&y<my+mh as i32-32).unwrap_or(&monitors[0]);
    let &(mx,my,mw,mh)=chosen;let width=w.clamp(300,mw.max(300));let height=h.clamp(250,mh.max(250));
    x=x.clamp(mx,mx+(mw.saturating_sub(width)) as i32);y=y.clamp(my,my+(mh.saturating_sub(height)) as i32);
    (x,y,width,height)
}
fn restore_geometry(app:&tauri::AppHandle,window:&tauri::WebviewWindow){
    let saved=geometry_path(app).and_then(|p|std::fs::read_to_string(p).ok()).and_then(|s|serde_json::from_str::<Value>(&s).ok()).unwrap_or(json!({}));
    let monitors=window.available_monitors().unwrap_or_default().iter().map(|m|(m.position().x,m.position().y,m.size().width,m.size().height)).collect::<Vec<_>>();
    let (x,y,w,h)=fit_geometry(saved["x"].as_i64().unwrap_or(60) as i32,saved["y"].as_i64().unwrap_or(60) as i32,
        saved["w"].as_u64().unwrap_or(380).min(1600) as u32,saved["h"].as_u64().unwrap_or(540).min(1800) as u32,&monitors);
    let _=window.set_size(PhysicalSize::new(w,h));let _=window.set_position(PhysicalPosition::new(x,y));
}
pub fn acknowledge(app:&tauri::AppHandle,request_id:Option<&str>,error:Option<String>){
    let window=app.get_webview_window("advisor");
    let selected=app.state::<Selection>().0.lock().ok().and_then(|s|s.clone());
    let message=json!({"event":"native_advisor_ack","request_id":request_id,"stream_id":selected,
        "visible":window.as_ref().map(|w|w.is_visible().unwrap_or(false)).unwrap_or(false),
        "topmost":window.as_ref().map(|w|w.is_always_on_top().unwrap_or(false)).unwrap_or(false),"error":error,
        "window":window.as_ref().map(|w|w.label()),"main_minimized":app.get_webview_window("main").map(|w|w.is_minimized().unwrap_or(false)),
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
                    if previous.as_deref()!=Some(selected){window.navigate(url).map_err(|e|e.to_string())?;}
                    window
                }else{
                    WebviewWindowBuilder::new(app,"advisor",WebviewUrl::External(url)).title(&title)
                        .inner_size(380.0,540.0).min_inner_size(300.0,250.0).decorations(true)
                        .resizable(true).content_protected(true).visible(!hidden).build().map_err(|e|e.to_string())?
                };
                window.set_title(&title).map_err(|e|e.to_string())?;
                restore_geometry(app,&window);
                window.set_always_on_top(message["topmost"].as_bool().unwrap_or(false)).map_err(|e|e.to_string())?;
                if !hidden{window.show().map_err(|e|e.to_string())?;window.set_focus().map_err(|e|e.to_string())?;}
                if std::env::var("BJLAB_NATIVE_ADVISOR_SMOKE").as_deref()==Ok("1"){
                    if let Some(main)=app.get_webview_window("main"){let _=main.minimize();}
                }
            },
            "hide"=>{if let Some(window)=app.get_webview_window("advisor"){window.close().map_err(|e|e.to_string())?;}},
            "topmost"=>{if let Some(window)=app.get_webview_window("advisor"){window.set_always_on_top(message["topmost"].as_bool().unwrap_or(false)).map_err(|e|e.to_string())?;}},
            _=>return Err("Unknown native advisor operation".into())
        }Ok(())
    })();
    acknowledge(app,id,result.err());
}

#[cfg(test)]
mod tests{
    use super::fit_geometry;
    #[test]fn removed_monitor_recovers_and_retains_visible_title(){
        assert_eq!(fit_geometry(8000,-300,380,540,&[(0,0,1920,1080)]),(1540,0,380,540));
    }
    #[test]fn negative_monitor_coordinates_and_dpi_physical_bounds(){
        assert_eq!(fit_geometry(-1200,100,380,540,&[(-1920,0,1920,1080),(0,0,2560,1440)]),(-1200,100,380,540));
        assert_eq!(fit_geometry(1500,800,4000,3000,&[(0,0,1920,1080)]),(0,0,1920,1080));
    }
}
