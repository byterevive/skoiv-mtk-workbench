//! Python worker lifecycle and request/response bridge (IPC v1 over stdio).

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{mpsc, Mutex};
use std::time::Duration;

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const RESPONSE_TIMEOUT: Duration = Duration::from_secs(130);

#[derive(Default)]
pub struct WorkerState {
    child: Mutex<Option<CommandChild>>,
    pending: Mutex<HashMap<String, mpsc::Sender<Result<Value, String>>>>,
    running: Mutex<bool>,
}

static REQ_COUNTER: AtomicU64 = AtomicU64::new(1);

fn next_request_id() -> String {
    let n = REQ_COUNTER.fetch_add(1, Ordering::Relaxed);
    format!("req-{n}")
}

fn emit_event(app: &AppHandle, event: &str, data: Value) {
    let _ = app.emit(
        "worker-event",
        json!({ "v": 1, "type": "event", "event": event, "data": data }),
    );
}

/// Parse one JSON line from the worker and route it.
fn handle_worker_line(app: &AppHandle, line: &str) {
    let parsed: Value = match serde_json::from_str(line) {
        Ok(v) => v,
        Err(err) => {
            emit_event(
                app,
                "log",
                json!({"level": "warn", "message": format!("unparseable worker line: {err}")}),
            );
            return;
        }
    };

    if parsed.get("type").and_then(Value::as_str) == Some("response") {
        let id = parsed.get("id").and_then(Value::as_str).unwrap_or_default().to_string();
        let outcome: Result<Value, String> = if parsed.get("ok").and_then(Value::as_bool) == Some(true) {
            Ok(parsed.get("result").cloned().unwrap_or(Value::Object(Default::default())))
        } else {
            let err = parsed
                .get("error")
                .map(|e| {
                    e.get("message")
                        .and_then(Value::as_str)
                        .unwrap_or("worker error")
                        .to_string()
                })
                .unwrap_or_else(|| "worker error".to_string());
            Err(err)
        };

        let sender = {
            let mut pending = app.state::<WorkerState>().pending.lock().unwrap();
            pending.remove(&id)
        };
        if let Some(sender) = sender {
            let _ = sender.send(outcome);
        }
        return;
    }

    // Everything else (events, logs, health) is forwarded to the UI verbatim.
    let _ = app.emit("worker-event", parsed);
}

/// Spawn the worker sidecar and start the stdout reader loop.
pub async fn spawn_worker(app: &AppHandle) -> Result<(), String> {
    {
        let state = app.state::<WorkerState>();
        let mut child = state.child.lock().unwrap();
        if child.is_some() {
            return Ok(());
        }
    }

    let command = match std::env::var("SKOIV_WORKER_BIN") {
        Ok(bin) => {
            let args: Vec<String> = std::env::var("SKOIV_WORKER_ARGS")
                .unwrap_or_default()
                .split_whitespace()
                .map(str::to_string)
                .collect();
            app.shell().command(bin).args(args)
        }
        Err(_) => app
            .shell()
            .sidecar("skoiv-worker")
            .map_err(|err| format!("worker sidecar not found: {err}"))?,
    };

    let (mut rx, child) = command
        .spawn()
        .map_err(|err| format!("failed to start worker: {err}"))?;

    {
        let state = app.state::<WorkerState>();
        *state.child.lock().unwrap() = Some(child);
        *state.running.lock().unwrap() = true;
    }
    emit_event(app, "worker-health", json!({"status": "starting"}));

    let reader_app = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut buffer = String::new();
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(data) => {
                    buffer.push_str(&String::from_utf8_lossy(&data));
                    while let Some(pos) = buffer.find('\n') {
                        let line = buffer[..pos].trim().to_string();
                        buffer.drain(..=pos);
                        if !line.is_empty() {
                            handle_worker_line(&reader_app, &line);
                        }
                    }
                }
                CommandEvent::Stderr(data) => {
                    let text = String::from_utf8_lossy(&data).trim().to_string();
                    if !text.is_empty() {
                        emit_event(
                            &reader_app,
                            "log",
                            json!({"level": "warn", "message": format!("worker stderr: {text}")}),
                        );
                    }
                }
                CommandEvent::Terminated(payload) => {
                    {
                        let state = reader_app.state::<WorkerState>();
                        *state.child.lock().unwrap() = None;
                        *state.running.lock().unwrap() = false;
                    }
                    emit_event(
                        &reader_app,
                        "worker-health",
                        json!({"status": "exited", "code": payload.code}),
                    );
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(())
}

#[tauri::command]
pub async fn worker_start(app: AppHandle) -> Result<bool, String> {
    spawn_worker(&app).await?;
    Ok(true)
}

#[tauri::command]
pub fn worker_stop(state: State<'_, WorkerState>) -> Result<bool, String> {
    let child = state.child.lock().unwrap().take();
    if let Some(child) = child {
        child.kill().map_err(|err| format!("failed to stop worker: {err}"))?;
    }
    *state.running.lock().unwrap() = false;
    Ok(true)
}

#[tauri::command]
pub fn worker_status(state: State<'_, WorkerState>) -> Value {
    let running = *state.running.lock().unwrap();
    json!({ "running": running })
}

/// Send a request to the worker and wait for its matching response.
#[tauri::command]
pub fn worker_request(
    state: State<'_, WorkerState>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    let id = next_request_id();
    let (tx, rx) = mpsc::channel::<Result<Value, String>>();
    state.pending.lock().unwrap().insert(id.clone(), tx);

    let line = json!({
        "v": 1,
        "type": "request",
        "id": id,
        "method": method,
        "params": params,
    })
    .to_string()
        + "\n";

    {
        let mut child_guard = state.child.lock().unwrap();
        match child_guard.as_mut() {
            Some(child) => {
                child
                    .write(line.as_bytes())
                    .map_err(|err| format!("failed to write to worker: {err}"))?;
            }
            None => {
                state.pending.lock().unwrap().remove(&id);
                return Err("worker is not running".to_string());
            }
        }
    }

    match rx.recv_timeout(RESPONSE_TIMEOUT) {
        Ok(outcome) => outcome,
        Err(_) => {
            state.pending.lock().unwrap().remove(&id);
            Err("worker request timed out".to_string())
        }
    }
}
