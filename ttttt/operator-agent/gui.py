import os
import sys
import time
import logging
import threading
import customtkinter as ctk

from slot_monitor import SlotMonitorEngine

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TextboxLogHandler(logging.Handler):
    """Custom logging handler to pipe logs to a CustomTkinter Textbox."""
    def __init__(self, textbox):
        super().__init__()
        self.textbox = textbox

    def emit(self, record):
        msg = self.format(record)
        # Use after() to safely update GUI from a background thread
        self.textbox.after(0, self.append_text, msg)

    def append_text(self, msg):
        self.textbox.configure(state="normal")
        self.textbox.insert(ctk.END, msg + "\n")
        self.textbox.see(ctk.END)
        self.textbox.configure(state="disabled")

class KamalExpressMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Kamal Express Worker Node")
        self.geometry("900x600")

        # Set up grid layout (1 row, 2 columns)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar Frame
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Kamal Express\nWorker Node", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_dashboard = ctk.CTkButton(self.sidebar_frame, text="Execution Logs", command=self.show_dashboard)
        self.btn_dashboard.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_test_mode = ctk.CTkButton(self.sidebar_frame, text="Test Mode (E2E)", command=self.show_test_mode)
        self.btn_test_mode.grid(row=2, column=0, padx=20, pady=10)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark", "System"], command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 20))

        # --- Main Frames Container ---
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # --- Dashboard Frame ---
        self.dashboard_frame = ctk.CTkFrame(self.main_container, corner_radius=0, fg_color="transparent")
        self.dashboard_frame.grid_rowconfigure(1, weight=1)
        self.dashboard_frame.grid_columnconfigure(0, weight=1)
        
        self.controls_frame = ctk.CTkFrame(self.dashboard_frame)
        self.controls_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        # SaaS URL
        self.url_label = ctk.CTkLabel(self.controls_frame, text="SaaS URL:")
        self.url_label.pack(side="left", padx=(20, 5), pady=20)
        self.url_entry = ctk.CTkEntry(self.controls_frame, width=300)
        self.url_entry.insert(0, "https://keagent.alamiaconnect.com")
        self.url_entry.pack(side="left", padx=5, pady=20)
        
        self.btn_start = ctk.CTkButton(self.controls_frame, text="Connect & Start", fg_color="green", hover_color="darkgreen", command=self.start_monitor)
        self.btn_start.pack(side="left", padx=20, pady=20)
        
        self.btn_stop = ctk.CTkButton(self.controls_frame, text="Stop Worker", fg_color="red", hover_color="darkred", state="disabled", command=self.stop_monitor)
        self.btn_stop.pack(side="left", padx=20, pady=20)
        
        self.btn_copy = ctk.CTkButton(self.controls_frame, text="Copy Logs", fg_color="gray", hover_color="darkgray", command=self.copy_logs)
        self.btn_copy.pack(side="left", padx=10, pady=20)
        
        self.btn_clear = ctk.CTkButton(self.controls_frame, text="Clear Logs", fg_color="gray", hover_color="darkgray", command=self.clear_logs)
        self.btn_clear.pack(side="left", padx=10, pady=20)

        self.status_label = ctk.CTkLabel(self.controls_frame, text="Status: IDLE", text_color="gray")
        self.status_label.pack(side="right", padx=20, pady=20)

        self.log_textbox = ctk.CTkTextbox(self.dashboard_frame, wrap="word", state="disabled")
        self.log_textbox.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        # --- Test Mode Frame ---
        self.test_mode_frame = ctk.CTkFrame(self.main_container, corner_radius=0, fg_color="transparent")
        self.test_mode_frame.grid_columnconfigure(0, weight=1)
        
        self.test_title = ctk.CTkLabel(self.test_mode_frame, text="End-to-End Test Mode", font=ctk.CTkFont(size=24, weight="bold"))
        self.test_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        self.test_desc = ctk.CTkLabel(self.test_mode_frame, text="Simulate worker events to test the Cloud SaaS pipeline and push notifications.", text_color="gray")
        self.test_desc.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        self.test_controls = ctk.CTkFrame(self.test_mode_frame)
        self.test_controls.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.btn_test_slots = ctk.CTkButton(self.test_controls, text="Simulate Slot Found", fg_color="purple", hover_color="darkmagenta", command=self.test_slot_found, width=200, height=40)
        self.btn_test_slots.pack(side="left", padx=20, pady=20)
        
        self.btn_test_no_slots = ctk.CTkButton(self.test_controls, text="Simulate No Slots", fg_color="orange", hover_color="darkorange", command=self.test_no_slots, width=200, height=40)
        self.btn_test_no_slots.pack(side="left", padx=20, pady=20)

        # Initialize Data & View
        self.monitor_engine = None
        self.setup_logging()
        self.appearance_mode_optionemenu.set("Dark")
        self.show_dashboard()

    def show_dashboard(self):
        self.test_mode_frame.grid_forget()
        self.dashboard_frame.grid(row=0, column=0, sticky="nsew")
        self.btn_dashboard.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        self.btn_test_mode.configure(fg_color="transparent", text_color=["gray10", "gray90"])

    def show_test_mode(self):
        self.dashboard_frame.grid_forget()
        self.test_mode_frame.grid(row=0, column=0, sticky="nsew")
        self.btn_test_mode.configure(fg_color=["#3B8ED0", "#1F6AA5"], text_color=["gray90", "gray10"])
        self.btn_dashboard.configure(fg_color="transparent", text_color=["gray10", "gray90"])

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        
    def copy_logs(self):
        self.clipboard_clear()
        self.clipboard_append(self.log_textbox.get("0.0", "end"))
        
    def clear_logs(self):
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("0.0", "end")
        self.log_textbox.configure(state="disabled")

    def setup_logging(self):
        handler = TextboxLogHandler(self.log_textbox)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        if not any(isinstance(h, TextboxLogHandler) for h in logger.handlers):
            logger.addHandler(handler)

    def start_monitor(self):
        if self.monitor_engine is not None and self.monitor_engine.is_alive():
            logging.warning("Worker is already running.")
            return

        base_url = self.url_entry.get().strip()
        if not base_url:
            logging.error("SaaS URL cannot be empty.")
            return

        logging.info("Initializing Worker Engine...")
        self.monitor_engine = SlotMonitorEngine(base_url)
        self.monitor_engine.start()
        
        self.url_entry.configure(state="disabled")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_label.configure(text="Status: RUNNING", text_color="green")

    def stop_monitor(self):
        if self.monitor_engine is not None and self.monitor_engine.is_alive():
            self.monitor_engine.stop()
            self.btn_stop.configure(state="disabled")
            self.status_label.configure(text="Status: STOPPING...", text_color="orange")
            
            threading.Thread(target=self._wait_for_stop, daemon=True).start()

    def _wait_for_stop(self):
        self.monitor_engine.join()
        self.after(0, self._on_stopped)

    def _on_stopped(self):
        self.url_entry.configure(state="normal")
        self.btn_start.configure(state="normal")
        self.status_label.configure(text="Status: IDLE", text_color="gray")
        logging.info("Worker fully stopped.")
        
    def _run_test_event(self, event_type: str, log_msg: str):
        base_url = self.url_entry.get().strip()
        if not base_url:
            logging.error("SaaS URL cannot be empty to run tests.")
            return
            
        def _send():
            try:
                logging.info(f"Test Mode: Sending '{event_type}' to {base_url}...")
                from api_client import SaaSClient
                api = SaaSClient(base_url)
                if not api.worker_id or not api.secret:
                    # Attempt to register just for testing if no creds
                    logging.info("Test Mode: Registering temporary worker credentials...")
                    if not api.register("gui-tester", "local"):
                        logging.error("Test Mode: Failed to register worker for test event.")
                        return
                
                api.log_event(None, event_type, "info", {"test_mode": True})
                logging.info(f"Test Mode: Successfully sent '{event_type}'. {log_msg}")
            except Exception as e:
                logging.error(f"Test Mode Error: {e}")
                
        threading.Thread(target=_send, daemon=True).start()

    def test_slot_found(self):
        self._run_test_event("SLOT_FOUND", "SaaS should pause assignments and push a notification.")
        
    def test_no_slots(self):
        self._run_test_event("NO_SLOTS_FOUND", "SaaS should push a 'No Slots' notification.")

if __name__ == "__main__":
    app = KamalExpressMonitorApp()
    app.mainloop()
