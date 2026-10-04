//! Skoiv MTK Workbench desktop shell (Tauri 2).
//!
//! The shell owns the Python worker lifecycle and bridges structured JSON
//! messages between the React UI and the worker's stdio (IPC v1).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod worker;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(worker::WorkerState::default())
        .invoke_handler(tauri::generate_handler![
            worker::worker_start,
            worker::worker_stop,
            worker::worker_status,
            worker::worker_request,
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(err) = worker::spawn_worker(&handle).await {
                    tauri::Emitter::emit(
                        &handle,
                        "worker-event",
                        serde_json::json!({
                            "v": 1,
                            "type": "event",
                            "event": "worker-health",
                            "data": {"status": "error", "message": err}
                        }),
                    )
                    .ok();
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running the Skoiv MTK Workbench application");
}
