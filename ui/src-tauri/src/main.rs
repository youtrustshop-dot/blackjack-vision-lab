#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};

struct Backend(Mutex<Option<CommandChild>>);

fn stop_backend(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<Backend>() {
        if let Ok(mut child) = state.0.lock() {
            if let Some(mut process) = child.take() {
                // Let the one-file bootloader clean its extracted directory.
                // Abruptly killing its parent would strand the unpacked assets.
                if process.write(b"shutdown\n").is_err() { let _ = process.kill(); }
            }
        }
    }
}

fn main() {
    let application = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let smoke_hidden = std::env::var("BJLAB_DESKTOP_SMOKE").as_deref() == Ok("1");
            WebviewWindowBuilder::new(app, "startup", WebviewUrl::App("splash.html".into()))
                .title("Blackjack Vision Lab").inner_size(460.0, 220.0)
                .resizable(false).visible(!smoke_hidden).build()?;
            let command = app.shell().sidecar("bjlab-backend")?
                .args(["--port", "0", "--parent-pid", &std::process::id().to_string()]);
            let (mut output, child) = command.spawn()?;
            app.manage(Backend(Mutex::new(Some(child))));
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let mut opened = false;
                while let Some(event) = output.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            let line = String::from_utf8_lossy(&bytes);
                            if let Ok(message) = serde_json::from_str::<serde_json::Value>(line.trim()) {
                                if !opened && message["event"] == "backend_ready" {
                                    if let Some(address) = message["url"].as_str() {
                                        if let Ok(url) = address.parse() {
                                            let result = WebviewWindowBuilder::new(&handle, "main", WebviewUrl::External(url))
                                                .title("Blackjack Vision Lab")
                                                .inner_size(1440.0, 940.0).min_inner_size(1000.0, 720.0)
                                                .visible(!smoke_hidden)
                                                .build();
                                            if result.is_ok() {
                                                opened = true;
                                                if let Ok(path) = std::env::var("BJLAB_NATIVE_READY_FILE") {
                                                    let proof = serde_json::json!({"event": "native_ready",
                                                        "pid": std::process::id(), "backend_pid": message["pid"],
                                                        "url": address, "window": "main", "hidden": smoke_hidden});
                                                    let _ = std::fs::write(path, proof.to_string());
                                                }
                                                if let Some(splash) = handle.get_webview_window("startup") { let _ = splash.close(); }
                                            }
                                            else { stop_backend(&handle); handle.exit(1); }
                                        }
                                    }
                                }
                            }
                        },
                        CommandEvent::Terminated(_) => {
                            if !opened { handle.exit(1); }
                        },
                        _ => {}
                    }
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if window.label() == "main" { stop_backend(window.app_handle()); }
                else if window.label() == "startup" && window.app_handle().get_webview_window("main").is_none() {
                    stop_backend(window.app_handle()); window.app_handle().exit(0);
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Unable to launch Blackjack Vision Lab desktop");
    application.run(|handle, event| {
        if let tauri::RunEvent::Exit = event { stop_backend(handle); }
    });
}
