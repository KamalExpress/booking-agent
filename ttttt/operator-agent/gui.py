import os
import sys
import time
import logging
import threading
import customtkinter as ctk

import config_manager
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

        self.title("Kamal Express Appointment Monitor")
        self.geometry("900x600")

        # Set up grid layout (1 row, 2 columns)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar Frame
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Kamal Express\nMonitor", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_dashboard = ctk.CTkButton(self.sidebar_frame, text="Dashboard", command=self.show_dashboard)
        self.btn_dashboard.grid(row=1, column=0, padx=20, pady=10)

        self.btn_accounts = ctk.CTkButton(self.sidebar_frame, text="Accounts", command=self.show_accounts)
        self.btn_accounts.grid(row=2, column=0, padx=20, pady=10)

        self.btn_settings = ctk.CTkButton(self.sidebar_frame, text="Settings", command=self.show_settings)
        self.btn_settings.grid(row=3, column=0, padx=20, pady=10)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark", "System"], command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 20))

        # Main Content Frames
        self.frames = {}

        # --- Dashboard Frame ---
        self.dashboard_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.dashboard_frame.grid_rowconfigure(1, weight=1)
        self.dashboard_frame.grid_columnconfigure(0, weight=1)
        
        self.controls_frame = ctk.CTkFrame(self.dashboard_frame)
        self.controls_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        self.btn_start = ctk.CTkButton(self.controls_frame, text="Start Monitor", fg_color="green", hover_color="darkgreen", command=self.start_monitor)
        self.btn_start.pack(side="left", padx=20, pady=20)
        
        self.btn_stop = ctk.CTkButton(self.controls_frame, text="Stop Monitor", fg_color="red", hover_color="darkred", state="disabled", command=self.stop_monitor)
        self.btn_stop.pack(side="left", padx=20, pady=20)

        self.btn_copy_logs = ctk.CTkButton(self.controls_frame, text="Copy Logs", command=self.copy_logs)
        self.btn_copy_logs.pack(side="left", padx=20, pady=20)

        self.status_label = ctk.CTkLabel(self.controls_frame, text="Status: IDLE", text_color="gray")
        self.status_label.pack(side="right", padx=20, pady=20)

        self.log_textbox = ctk.CTkTextbox(self.dashboard_frame, wrap="word", state="disabled")
        self.log_textbox.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        # --- Accounts Frame ---
        self.accounts_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.accounts_frame.grid_rowconfigure(0, weight=1)
        self.accounts_frame.grid_columnconfigure(0, weight=1)

        self.acc_list_frame = ctk.CTkFrame(self.accounts_frame)
        self.acc_list_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.acc_list_frame.grid_rowconfigure(0, weight=1)
        self.acc_list_frame.grid_columnconfigure(0, weight=1)
        
        self.acc_textbox = ctk.CTkTextbox(self.acc_list_frame, state="disabled")
        self.acc_textbox.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.acc_inputs_frame = ctk.CTkFrame(self.accounts_frame)
        self.acc_inputs_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        self.acc_email_entry = ctk.CTkEntry(self.acc_inputs_frame, placeholder_text="Email / Username", width=200)
        self.acc_email_entry.grid(row=0, column=0, padx=10, pady=10)
        
        self.acc_pass_entry = ctk.CTkEntry(self.acc_inputs_frame, placeholder_text="Password", show="*", width=200)
        self.acc_pass_entry.grid(row=0, column=1, padx=10, pady=10)
        
        self.btn_add_acc = ctk.CTkButton(self.acc_inputs_frame, text="Add Account", command=self.add_account)
        self.btn_add_acc.grid(row=0, column=2, padx=10, pady=10)

        self.btn_clear_acc = ctk.CTkButton(self.acc_inputs_frame, text="Clear All", fg_color="red", hover_color="darkred", command=self.clear_accounts)
        self.btn_clear_acc.grid(row=0, column=3, padx=10, pady=10)

        # --- Settings Frame ---
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        
        self.settings_container = ctk.CTkScrollableFrame(self.settings_frame)
        self.settings_container.pack(fill="both", expand=True, padx=20, pady=20)

        self.settings_inputs = {}
        self.holiday_checkboxes = {}
        
        # 1. Dates
        lbl_date_from = ctk.CTkLabel(self.settings_container, text="Start Date (DD/MM/YYYY)")
        lbl_date_from.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ent_date_from = ctk.CTkEntry(self.settings_container, width=300, placeholder_text="e.g. 01/09/2026")
        ent_date_from.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        self.settings_inputs["APPOINTMENT_DATE_FROM"] = ent_date_from
        
        lbl_date_to = ctk.CTkLabel(self.settings_container, text="End Date (DD/MM/YYYY)")
        lbl_date_to.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ent_date_to = ctk.CTkEntry(self.settings_container, width=300, placeholder_text="e.g. 15/09/2026")
        ent_date_to.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        self.settings_inputs["APPOINTMENT_DATE_TO"] = ent_date_to
        
        # 2. Holidays Checkboxes
        lbl_holidays = ctk.CTkLabel(self.settings_container, text="Holidays / Off Days")
        lbl_holidays.grid(row=2, column=0, padx=10, pady=10, sticky="nw")
        
        holidays_frame = ctk.CTkFrame(self.settings_container, fg_color="transparent")
        holidays_frame.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        
        days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        for idx, day in enumerate(days):
            var = ctk.StringVar(value="")
            chk = ctk.CTkCheckBox(holidays_frame, text=day, variable=var, onvalue=day, offvalue="")
            chk.grid(row=idx//4, column=idx%4, padx=5, pady=5, sticky="w")
            self.holiday_checkboxes[day] = var
            
        # 3. Captcha Settings
        lbl_strategy = ctk.CTkLabel(self.settings_container, text="Captcha Strategy")
        lbl_strategy.grid(row=3, column=0, padx=10, pady=10, sticky="w")
        ent_strategy = ctk.CTkOptionMenu(self.settings_container, values=["MANUAL", "AUTO", "MOCK"])
        ent_strategy.grid(row=3, column=1, padx=10, pady=10, sticky="w")
        self.settings_inputs["CAPTCHA_STRATEGY"] = ent_strategy
        
        lbl_provider = ctk.CTkLabel(self.settings_container, text="Captcha Provider")
        lbl_provider.grid(row=4, column=0, padx=10, pady=10, sticky="w")
        ent_provider = ctk.CTkEntry(self.settings_container, width=300)
        ent_provider.insert(0, "CapSolver")
        ent_provider.configure(state="disabled") # Disabled as per user request
        ent_provider.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        self.settings_inputs["CAPTCHA_PROVIDER"] = ent_provider
        
        lbl_apikey = ctk.CTkLabel(self.settings_container, text="CapSolver API Key (If AUTO)")
        lbl_apikey.grid(row=5, column=0, padx=10, pady=10, sticky="w")
        ent_apikey = ctk.CTkEntry(self.settings_container, width=300)
        ent_apikey.grid(row=5, column=1, padx=10, pady=10, sticky="w")
        self.settings_inputs["CAPTCHA_API_KEY"] = ent_apikey
        
        # 4. Monitor Interval
        lbl_interval = ctk.CTkLabel(self.settings_container, text="Monitor Interval (Minutes)")
        lbl_interval.grid(row=6, column=0, padx=10, pady=10, sticky="w")
        ent_interval = ctk.CTkEntry(self.settings_container, width=300)
        ent_interval.grid(row=6, column=1, padx=10, pady=10, sticky="w")
        self.settings_inputs["MONITOR_INTERVAL_MINUTES"] = ent_interval
        
        # 5. Demo Mode
        lbl_demo = ctk.CTkLabel(self.settings_container, text="Demo Mode (Fake Slots & Alarms)")
        lbl_demo.grid(row=7, column=0, padx=10, pady=10, sticky="w")
        
        self.demo_var = ctk.StringVar(value="False")
        chk_demo = ctk.CTkSwitch(self.settings_container, text="Enable Demo Mode", variable=self.demo_var, onvalue="True", offvalue="False")
        chk_demo.grid(row=7, column=1, padx=10, pady=10, sticky="w")
        
        self.btn_save_settings = ctk.CTkButton(self.settings_container, text="Save Settings", command=self.save_settings)
        self.btn_save_settings.grid(row=8, column=1, padx=10, pady=30, sticky="w")

        # Final Setup
        self.frames["Dashboard"] = self.dashboard_frame
        self.frames["Accounts"] = self.accounts_frame
        self.frames["Settings"] = self.settings_frame

        # Initialize Data & View
        self.monitor_engine = None
        self.setup_logging()
        self.refresh_accounts_view()
        self.load_settings_into_ui()
        self.show_dashboard()
        self.appearance_mode_optionemenu.set("Dark")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def show_frame(self, frame_name):
        for f in self.frames.values():
            f.grid_forget()
            
        self.frames[frame_name].grid(row=0, column=1, sticky="nsew")

    def show_dashboard(self): self.show_frame("Dashboard")
    def show_accounts(self): self.show_frame("Accounts")
    def show_settings(self): self.show_frame("Settings")

    def copy_logs(self):
        try:
            self.clipboard_clear()
            logs = self.log_textbox.get("1.0", ctk.END)
            self.clipboard_append(logs)
            self.update()
            logging.info("Logs successfully copied to clipboard!")
        except Exception as e:
            logging.error(f"Failed to copy logs: {e}")

    def setup_logging(self):
        # Configure logging to also output to our Textbox
        handler = TextboxLogHandler(self.log_textbox)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        # Avoid duplicate handlers if setup_logging is called multiple times
        if not any(isinstance(h, TextboxLogHandler) for h in logger.handlers):
            logger.addHandler(handler)

    # --- Accounts Logic ---
    def refresh_accounts_view(self):
        accounts = config_manager.load_accounts()
        self.acc_textbox.configure(state="normal")
        self.acc_textbox.delete("1.0", ctk.END)
        if not accounts:
            self.acc_textbox.insert(ctk.END, "No accounts configured.\n")
        else:
            for i, acc in enumerate(accounts):
                self.acc_textbox.insert(ctk.END, f"[{i+1}] {acc['username']} | Password: {'*' * len(acc['password'])}\n")
        self.acc_textbox.configure(state="disabled")

    def add_account(self):
        email = self.acc_email_entry.get().strip()
        password = self.acc_pass_entry.get().strip()
        if email and password:
            accounts = config_manager.load_accounts()
            accounts.append({"username": email, "password": password})
            config_manager.save_accounts(accounts)
            self.acc_email_entry.delete(0, ctk.END)
            self.acc_pass_entry.delete(0, ctk.END)
            self.refresh_accounts_view()
            logging.info(f"Added account: {email}")

    def clear_accounts(self):
        config_manager.save_accounts([])
        self.refresh_accounts_view()
        logging.info("Cleared all accounts.")

    # --- Settings Logic ---
    def load_settings_into_ui(self):
        settings = config_manager.load_settings()
        for key, entry in self.settings_inputs.items():
            val = settings.get(key, "")
            if isinstance(entry, ctk.CTkOptionMenu):
                entry.set(str(val))
            else:
                entry.configure(state="normal")
                entry.delete(0, ctk.END)
                entry.insert(0, str(val))
                if key == "CAPTCHA_PROVIDER":
                    entry.configure(state="disabled")
                    
        # Parse holidays and set checkboxes
        holidays_str = settings.get("HOLIDAYS", "")
        active_holidays = [h.strip().upper() for h in holidays_str.split(",") if h.strip()]
        for day, var in self.holiday_checkboxes.items():
            if day in active_holidays:
                var.set(day)
            else:
                var.set("")
                
        # Parse Demo Mode
        demo_val = settings.get("DEMO_MODE", "False")
        self.demo_var.set(demo_val)

    def save_settings(self):
        settings = config_manager.load_settings()
        for key, entry in self.settings_inputs.items():
            if key != "CAPTCHA_PROVIDER": # Skip disabled field
                settings[key] = entry.get()
                
        # Aggregate checkboxes
        selected_holidays = [var.get() for var in self.holiday_checkboxes.values() if var.get()]
        settings["HOLIDAYS"] = ",".join(selected_holidays)
        
        # Save Demo Mode
        settings["DEMO_MODE"] = self.demo_var.get()
        
        config_manager.save_settings(settings)
        logging.info("Settings saved successfully!")

    # --- Monitor Control Logic ---
    def start_monitor(self):
        if self.monitor_engine is not None and self.monitor_engine.is_alive():
            logging.warning("Monitor is already running.")
            return

        logging.info("Initializing Monitor Engine...")
        self.monitor_engine = SlotMonitorEngine()
        self.monitor_engine.start()
        
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_label.configure(text="Status: RUNNING", text_color="green")

    def stop_monitor(self):
        if self.monitor_engine is not None and self.monitor_engine.is_alive():
            self.monitor_engine.stop()
            self.btn_stop.configure(state="disabled")
            self.status_label.configure(text="Status: STOPPING...", text_color="orange")
            
            # Start a polling thread to update UI when it actually stops
            threading.Thread(target=self._wait_for_stop, daemon=True).start()

    def _wait_for_stop(self):
        self.monitor_engine.join()
        self.after(0, self._on_stopped)

    def _on_stopped(self):
        self.btn_start.configure(state="normal")
        self.status_label.configure(text="Status: IDLE", text_color="gray")
        logging.info("Monitor fully stopped.")

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable, point playwright to the bundled local-browsers folder
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(sys._MEIPASS, "playwright", "driver", "package", ".local-browsers")
    else:
        # Running locally from python script, use local browser folder
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
        
    app = KamalExpressMonitorApp()
    app.mainloop()
