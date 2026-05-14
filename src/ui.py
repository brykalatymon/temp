import os
import sys
import time
import shutil
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw

from core import TempCore

class TempApp(ctk.CTk):
    def __init__(self, silent_start=False):
        super().__init__()
        self.core = TempCore()

        # --- WINDOW CONFIGURATION ---
        self.title("Temp // File Management")
        self.geometry("1100x700")
        
        icon_path = Path(__file__).parent.parent / "assets" / "logo.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))
        
        self.bg_base = "#111111"
        self.bg_topbar = "#1e1e1e"
        self.bg_header = "#252525"
        self.bg_row = "#1c1c1c"
        self.accent_blue = "#0078D7"
        self.text_dim = "#a0a0a0"
        self.danger_red = "#8A0303"
        
        self.configure(fg_color=self.bg_base)
        
        self.current_tab = "inbox"
        self.selected_files = set()
        self.current_displayed_files = [] 
        self.row_checkboxes = [] 

        self.build_layout()
        self.switch_tab("inbox")

        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        cleaner_thread = threading.Thread(target=self.core.run_auto_cleaner, daemon=True)
        cleaner_thread.start()

        if silent_start:
            self.withdraw()
            self.spawn_tray_icon()

    def build_layout(self):
        # 1. TOP TOOLBAR
        self.topbar = ctk.CTkFrame(self, fg_color=self.bg_topbar, corner_radius=0, height=55)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)

        self.tabs_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.tabs_frame.pack(side="left", fill="y", padx=10)

        self.btn_inbox = self.create_tab_btn("Inbox", "inbox")
        self.btn_managed = self.create_tab_btn("Managed {#}", "managed")
        self.btn_quarantine = self.create_tab_btn("Quarantine", "quarantine")
        self.btn_settings = self.create_tab_btn("Settings", "settings")

        self.actions_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.actions_frame.pack(side="right", fill="y", padx=10)

        # 2. TABLE HEADER
        self.header_frame = ctk.CTkFrame(self, fg_color=self.bg_header, corner_radius=0, height=30)
        self.header_frame.pack(side="top", fill="x", padx=10, pady=(10, 0))
        self.header_frame.pack_propagate(False)

        # Master Checkbox - domyślnie widoczny
        self.select_all_var = ctk.IntVar()
        self.master_checkbox = ctk.CTkCheckBox(
            self.header_frame, text="", width=30, corner_radius=0, 
            checkbox_width=18, checkbox_height=18, fg_color=self.accent_blue,
            variable=self.select_all_var, command=self.toggle_select_all
        )

        # Kontener na dynamiczne etykiety nagłówka
        self.header_labels_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.header_labels_frame.pack(side="left", fill="both", expand=True)

        # 3. MAIN LIST CONTAINER
        self.list_container = ctk.CTkScrollableFrame(self, fg_color=self.bg_base, corner_radius=0)
        self.list_container.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

    def update_header_labels(self):
        # Brutalne czyszczenie kontenera etykiet
        for widget in self.header_labels_frame.winfo_children():
            widget.destroy()
        
        if self.current_tab == "settings":
            # Całkowicie ukrywamy checkbox, żeby zwolnić miejsce
            self.master_checkbox.pack_forget()
            
            ctk.CTkLabel(self.header_labels_frame, text="Monitored Folder Path", anchor="w").pack(side="left", padx=15)
            ctk.CTkLabel(self.header_labels_frame, text="Action", anchor="center", width=80).pack(side="right", padx=(0, 32))
        else:
            # Przywracamy checkbox na swoje miejsce
            self.master_checkbox.pack(side="left", padx=5, before=self.header_labels_frame)
            
            ctk.CTkLabel(self.header_labels_frame, text="Name", anchor="w", width=450).pack(side="left", padx=10)
            ctk.CTkLabel(self.header_labels_frame, text="Status", anchor="w", width=150).pack(side="left", padx=10)
            ctk.CTkLabel(self.header_labels_frame, text="Path / Size", anchor="w").pack(side="left", padx=10)

    def create_tab_btn(self, text, tab_id):
        btn = ctk.CTkButton(
            self.tabs_frame, text=text, corner_radius=0, width=120, height=35,
            fg_color="transparent", border_color="#333", border_width=1, hover_color="#333",
            command=lambda: self.switch_tab(tab_id)
        )
        btn.pack(side="left", padx=2, pady=10)
        return btn

    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        self.selected_files.clear()
        self.select_all_var.set(0)
        
        for name, btn in [("inbox", self.btn_inbox), ("managed", self.btn_managed), 
                          ("quarantine", self.btn_quarantine), ("settings", self.btn_settings)]:
            btn.configure(fg_color=self.accent_blue if tab_name == name else "transparent", 
                          border_width=0 if tab_name == name else 1)

        self.update_header_labels()
        self.build_action_buttons()
        self.refresh_list()

    def build_action_buttons(self):
        for widget in self.actions_frame.winfo_children():
            widget.destroy()

        if self.current_tab == "settings":
            ctk.CTkButton(self.actions_frame, text="Add Folder", corner_radius=0, width=120, 
                          fg_color=self.accent_blue, command=self.action_add_folder_dialog).pack(side="left", padx=5, pady=10)
            return

        tag_values = ["{0}", "{1}", "{2}", "{4}", "{12}"]
        if self.current_tab in ["inbox", "managed"]:
            self.tag_var = ctk.StringVar(value="{1}")
            ctk.CTkOptionMenu(self.actions_frame, values=tag_values, variable=self.tag_var, width=80, corner_radius=0, fg_color="#333", button_color="#444").pack(side="left", padx=5, pady=10)
            
            btn_txt = "Apply Tag" if self.current_tab == "inbox" else "Change Tag"
            ctk.CTkButton(self.actions_frame, text=btn_txt, corner_radius=0, width=100, fg_color=self.accent_blue, command=self.action_update_tags).pack(side="left", padx=5, pady=10)
            ctk.CTkButton(self.actions_frame, text="Quarantine", corner_radius=0, width=100, fg_color="#444", command=self.action_quarantine_selected).pack(side="left", padx=5, pady=10)
            ctk.CTkButton(self.actions_frame, text="Delete", corner_radius=0, width=80, fg_color=self.danger_red, command=self.action_delete_selected).pack(side="left", padx=5, pady=10)
        elif self.current_tab == "quarantine":
            ctk.CTkButton(self.actions_frame, text="Restore", corner_radius=0, width=100, fg_color="#00C851", hover_color="#007E33", command=self.action_restore_selected).pack(side="left", padx=5, pady=10)
            ctk.CTkButton(self.actions_frame, text="Delete", corner_radius=0, width=100, fg_color=self.danger_red, command=self.action_delete_selected).pack(side="left", padx=5, pady=10)

    def refresh_list(self):
        for widget in self.list_container.winfo_children():
            widget.destroy()

        if self.current_tab == "settings":
            for folder in self.core.config["monitored_folders"]:
                self.create_folder_row(folder)
            return

        self.row_checkboxes.clear()
        
        files = []
        if self.current_tab == "inbox":
            files = self.core.get_new_files()
        elif self.current_tab == "managed":
            files = self.core.scan_for_tagged_files()
        elif self.current_tab == "quarantine":
            files = self.get_quarantine_files()
        
        self.current_displayed_files = files
        
        if not files:
            ctk.CTkLabel(self.list_container, text="Folder is empty.", text_color=self.text_dim).pack(pady=40)
            return

        for f in files:
            self.create_file_row(f)

    def create_folder_row(self, path):
        row = ctk.CTkFrame(self.list_container, fg_color=self.bg_row, corner_radius=0, height=40)
        row.pack(side="top", fill="x", pady=1)
        row.pack_propagate(False)
        
        ctk.CTkLabel(row, text=path, anchor="w", font=("Segoe UI", 12)).pack(side="left", padx=15)
        ctk.CTkButton(row, text="Remove", width=80, height=24, fg_color=self.danger_red, corner_radius=0,
                      command=lambda p=path: [self.core.remove_monitored_folder(p), self.refresh_list()]).pack(side="right", padx=15)

    def create_file_row(self, file_info):
        row = ctk.CTkFrame(self.list_container, fg_color=self.bg_row, corner_radius=0, height=40, cursor="hand2")
        row.pack(side="top", fill="x", pady=1)
        row.pack_propagate(False)

        chk_var = ctk.IntVar(value=1 if file_info['full_path'] in self.selected_files else 0)
        def toggle(e=None):
            p = file_info['full_path']
            if p in self.selected_files: 
                self.selected_files.remove(p)
                chk_var.set(0)
            else: 
                self.selected_files.add(p)
                chk_var.set(1)
            
            if len(self.selected_files) == len(self.current_displayed_files) and len(self.current_displayed_files) > 0:
                self.select_all_var.set(1)
            else:
                self.select_all_var.set(0)
        
        chk = ctk.CTkCheckBox(row, text="", width=30, corner_radius=0, checkbox_width=18, checkbox_height=18, 
                              fg_color=self.accent_blue, hover_color="#005A9E", variable=chk_var, command=toggle)
        chk.pack(side="left", padx=5)
        self.row_checkboxes.append(chk)

        lbl_n = ctk.CTkLabel(row, text=file_info['name'], anchor="w", width=450, cursor="hand2")
        lbl_n.pack(side="left", padx=10)

        if self.current_tab == "inbox":
            txt, col, det = "New", self.accent_blue, f"{file_info.get('size_mb', '?')} MB"
        elif self.current_tab == "managed":
            txt = "Expired" if file_info['is_expired'] else f"{file_info['days_left']} days left"
            col = "#ff4444" if file_info['is_expired'] else "#00C851"
            det = str(Path(file_info['full_path']).parent)
        else:
            txt, col, det = "Hidden", self.text_dim, f"{file_info.get('size_mb', '?')} MB"

        lbl_s = ctk.CTkLabel(row, text=txt, text_color=col, anchor="w", width=150, cursor="hand2")
        lbl_s.pack(side="left", padx=10)
        
        lbl_d = ctk.CTkLabel(row, text=det, text_color=self.text_dim, anchor="w", cursor="hand2")
        lbl_d.pack(side="left", padx=10)
        
        row.bind("<Button-1>", toggle)
        lbl_n.bind("<Button-1>", toggle)
        lbl_s.bind("<Button-1>", toggle)
        lbl_d.bind("<Button-1>", toggle)

    def action_add_folder_dialog(self):
        folder = filedialog.askdirectory()
        if folder:
            self.core.add_monitored_folder(folder)
            self.refresh_list()

    def action_update_tags(self):
        tag = self.tag_var.get()
        for path in list(self.selected_files):
            self.core.update_file_tag(path, tag)
        self.selected_files.clear()
        self.refresh_list()

    def action_quarantine_selected(self):
        for path in list(self.selected_files):
            self.core.move_to_quarantine(path)
        self.selected_files.clear()
        self.refresh_list()

    def action_delete_selected(self):
        for path in list(self.selected_files):
            self.core.delete_permanently(path)
        self.selected_files.clear()
        self.refresh_list()

    def action_restore_selected(self):
        dest = Path.home() / "Downloads"
        for path in list(self.selected_files):
            if Path(path).exists(): shutil.move(path, str(dest / Path(path).name))
        self.selected_files.clear()
        self.refresh_list()

    def get_quarantine_files(self):
        files = []
        if self.core.quarantine_folder.exists():
            for f in self.core.quarantine_folder.iterdir():
                if f.is_file():
                    files.append({"name": f.name, "full_path": str(f), "size_mb": round(f.stat().st_size/(1024*1024),2)})
        return files

    def toggle_select_all(self):
        if self.select_all_var.get():
            for f in self.current_displayed_files: self.selected_files.add(f['full_path'])
            for c in self.row_checkboxes: c.select()
        else:
            self.selected_files.clear()
            for c in self.row_checkboxes: c.deselect()

    def hide_to_tray(self):
        self.withdraw()
        self.spawn_tray_icon()

    def spawn_tray_icon(self):
        icon_path = Path(__file__).parent.parent / "assets" / "logo.png"
        img = Image.open(str(icon_path)) if icon_path.exists() else Image.new('RGB', (64, 64), color="#0078D7")
        menu = pystray.Menu(pystray.MenuItem('Open', self.restore_from_tray), pystray.MenuItem('Quit', self.quit_app))
        self.tray_icon = pystray.Icon("TempApp", img, "Temp", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def restore_from_tray(self, icon=None, item=None):
        if hasattr(self, 'tray_icon'): self.tray_icon.stop()
        self.after(0, self.deiconify)
        self.after(0, self.refresh_list)

    def quit_app(self, icon=None, item=None):
        if hasattr(self, 'tray_icon'): self.tray_icon.stop()
        self.destroy()
        os._exit(0)