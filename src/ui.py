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
        else:
            print(f"Warning: Icon not found at {icon_path}")
        
        # Color Palette
        self.bg_base = "#111111"
        self.bg_topbar = "#1e1e1e"
        self.bg_header = "#252525"
        self.bg_row = "#1c1c1c"
        self.accent_blue = "#0078D7"
        self.text_dim = "#a0a0a0"
        self.danger_red = "#8A0303"
        
        self.configure(fg_color=self.bg_base)
        
        # App State
        self.current_tab = "inbox"
        self.selected_files = set()
        self.current_displayed_files = [] 
        self.row_checkboxes = [] 

        self.build_layout()
        self.switch_tab("inbox")

        # --- TRAY ICON & BACKGROUND THREAD SETUP ---
        # Przechwytujemy kliknięcie "X" w rogu okna
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        # Uruchomienie automatycznego sprzątania w tle
        cleaner_thread = threading.Thread(target=self.core.run_auto_cleaner, daemon=True)
        cleaner_thread.start()

        # Jeśli uruchomiono z flagą cichą (np. przy starcie systemu)
        if silent_start:
            self.withdraw() # Ukrywa okno od razu
            self.spawn_tray_icon()

    def build_layout(self):
        # 1. TOP TOOLBAR
        self.topbar = ctk.CTkFrame(self, fg_color=self.bg_topbar, corner_radius=0, height=55)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)

        self.tabs_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.tabs_frame.pack(side="left", fill="y", padx=10)

        self.btn_inbox = self.create_tab_btn("Inbox", "inbox")
        self.btn_managed = self.create_tab_btn("Managed ({#})", "managed")
        self.btn_quarantine = self.create_tab_btn("Quarantine", "quarantine")
        self.btn_settings = self.create_tab_btn("Settings", "settings")

        self.actions_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.actions_frame.pack(side="right", fill="y", padx=10)

        # 2. TABLE HEADER
        self.header_frame = ctk.CTkFrame(self, fg_color=self.bg_header, corner_radius=0, height=30)
        self.header_frame.pack(side="top", fill="x", padx=10, pady=(10, 0))
        self.header_frame.pack_propagate(False)

        # Master Checkbox ("Select All")
        self.select_all_var = ctk.IntVar()
        self.master_checkbox = ctk.CTkCheckBox(
            self.header_frame, text="", width=30, corner_radius=0, 
            checkbox_width=18, checkbox_height=18, fg_color=self.accent_blue, hover_color="#005A9E",
            variable=self.select_all_var, command=self.toggle_select_all
        )
        self.master_checkbox.pack(side="left", padx=5)

        ctk.CTkLabel(self.header_frame, text="Name", anchor="w", width=450).pack(side="left", padx=10)
        ctk.CTkLabel(self.header_frame, text="Status", anchor="w", width=150).pack(side="left", padx=10)
        ctk.CTkLabel(self.header_frame, text="Path / Size", anchor="w").pack(side="left", padx=10)

        # 3. MAIN LIST CONTAINER
        self.list_container = ctk.CTkScrollableFrame(self, fg_color=self.bg_base, corner_radius=0)
        self.list_container.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

    def create_tab_btn(self, text, tab_id):
        btn = ctk.CTkButton(
            self.tabs_frame, text=text, corner_radius=0, width=130, height=35,
            fg_color="transparent", border_color="#333", border_width=1, hover_color="#333",
            command=lambda: self.switch_tab(tab_id)
        )
        btn.pack(side="left", padx=2, pady=10)
        return btn

    # --- TAB LOGIC ---
    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        self.selected_files.clear()
        self.select_all_var.set(0)
        
        for name, btn in [("inbox", self.btn_inbox), ("managed", self.btn_managed), 
                          ("quarantine", self.btn_quarantine), ("settings", self.btn_settings)]:
            if tab_name == name:
                btn.configure(fg_color=self.accent_blue, border_width=0)
            else:
                btn.configure(fg_color="transparent", border_width=1)

        self.build_action_buttons()
        self.refresh_list()

    def build_action_buttons(self):
        for widget in self.actions_frame.winfo_children():
            widget.destroy()

        # Wspólne wartości dla tagów (teraz z opcją {0})
        tag_values = ["{0}", "{1}", "{2}", "{4}", "{12}"]

        if self.current_tab in ["inbox", "managed"]:
            # Dropdown do wyboru tagu
            self.tag_var = ctk.StringVar(value="{1}")
            tag_menu = ctk.CTkOptionMenu(
                self.actions_frame, values=tag_values, variable=self.tag_var,
                width=80, corner_radius=0, fg_color="#333", button_color="#444"
            )
            tag_menu.pack(side="left", padx=5, pady=10)
            
            # Przycisk zmieniający tag (lub nadający nowy)
            btn_text = "Apply Tag" if self.current_tab == "inbox" else "Change Tag"
            ctk.CTkButton(
                self.actions_frame, text=btn_text, corner_radius=0, width=100, 
                fg_color=self.accent_blue, command=self.action_update_tags
            ).pack(side="left", padx=5, pady=10)

            # Pozostałe przyciski
            ctk.CTkButton(self.actions_frame, text="Quarantine", corner_radius=0, width=100, fg_color="#444", command=self.action_quarantine_selected).pack(side="left", padx=5, pady=10)
            ctk.CTkButton(self.actions_frame, text="Delete", corner_radius=0, width=80, fg_color=self.danger_red, command=self.action_delete_selected).pack(side="left", padx=5, pady=10)

        elif self.current_tab == "quarantine":
            ctk.CTkButton(self.actions_frame, text="Restore", corner_radius=0, width=100, fg_color="#00C851", hover_color="#007E33", command=self.action_restore_selected).pack(side="left", padx=5, pady=10)
            ctk.CTkButton(self.actions_frame, text="Delete", corner_radius=0, width=100, fg_color=self.danger_red, command=self.action_delete_selected).pack(side="left", padx=5, pady=10)

    # --- SELECTION & LIST LOGIC ---
    def toggle_select_all(self):
        is_selected = self.select_all_var.get() == 1
        if is_selected:
            for f in self.current_displayed_files:
                self.selected_files.add(f['full_path'])
            for chk in self.row_checkboxes:
                chk.select()
        else:
            self.selected_files.clear()
            for chk in self.row_checkboxes:
                chk.deselect()

    def refresh_list(self):
        for widget in self.list_container.winfo_children():
            widget.destroy()
        
        if self.current_tab == "settings":
            self.build_settings_view()
            return

        self.row_checkboxes.clear()
        self.select_all_var.set(0) # Reset master checkbox on refresh

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

    def get_quarantine_files(self):
        q_files = []
        p = self.core.quarantine_folder
        if p.exists():
            for file in p.iterdir():
                if file.is_file():
                    q_files.append({
                        "name": file.name,
                        "full_path": str(file),
                        "is_expired": False,
                        "days_left": "In quarantine",
                        "size_mb": round(file.stat().st_size / (1024 * 1024), 2)
                    })
        return q_files

    def create_file_row(self, file_info):
        # cursor="hand2" sprawia, że po najechaniu pojawia się wskaźnik dłoni
        row = ctk.CTkFrame(self.list_container, fg_color=self.bg_row, corner_radius=0, height=40, cursor="hand2")
        row.pack(side="top", fill="x", pady=1)
        row.pack_propagate(False)

        chk_var = ctk.IntVar(value=1 if file_info['full_path'] in self.selected_files else 0)

        # Funkcja przełączająca dany wiersz przy kliknięciu (checkbox lub tło)
        def toggle_row_selection(event=None):
            path = file_info['full_path']
            if path in self.selected_files:
                self.selected_files.remove(path)
                chk_var.set(0)
            else:
                self.selected_files.add(path)
                chk_var.set(1)
                
            # Aktualizacja "Master Checkboxa" jeśli zaznaczono/odznaczono wszystko ręcznie
            if len(self.selected_files) == len(self.current_displayed_files) and len(self.current_displayed_files) > 0:
                self.select_all_var.set(1)
            else:
                self.select_all_var.set(0)

        chk = ctk.CTkCheckBox(
            row, text="", width=30, corner_radius=0, checkbox_width=18, checkbox_height=18, 
            fg_color=self.accent_blue, hover_color="#005A9E", variable=chk_var, command=toggle_row_selection
        )
        chk.pack(side="left", padx=5)
        self.row_checkboxes.append(chk)

        name_lbl = ctk.CTkLabel(row, text=file_info['name'], anchor="w", width=450, font=("Segoe UI", 12), cursor="hand2")
        name_lbl.pack(side="left", padx=10)

        if self.current_tab == "inbox":
            stan_text, stan_color, detal = "New", self.accent_blue, f"{file_info.get('size_mb', '?')} MB"
        elif self.current_tab == "managed":
            stan_text = "Expired" if file_info['is_expired'] else f"{file_info['days_left']} days left"
            stan_color = "#ff4444" if file_info['is_expired'] else "#00C851"
            detal = str(Path(file_info['full_path']).parent)
        else:
            stan_text, stan_color, detal = "Hidden", self.text_dim, f"{file_info.get('size_mb', '?')} MB"

        status_lbl = ctk.CTkLabel(row, text=stan_text, anchor="w", width=150, text_color=stan_color, font=("Segoe UI", 12), cursor="hand2")
        status_lbl.pack(side="left", padx=10)
        
        detail_lbl = ctk.CTkLabel(row, text=detal, anchor="w", text_color=self.text_dim, font=("Segoe UI", 11), cursor="hand2")
        detail_lbl.pack(side="left", padx=10)

        # Przypisanie zdarzenia kliknięcia (<Button-1>) do tła i wszystkich tekstów
        row.bind("<Button-1>", toggle_row_selection)
        name_lbl.bind("<Button-1>", toggle_row_selection)
        status_lbl.bind("<Button-1>", toggle_row_selection)
        detail_lbl.bind("<Button-1>", toggle_row_selection)

    # --- BATCH ACTIONS ---
    def action_delete_selected(self):
        for path in list(self.selected_files):
            self.core.delete_permanently(path)
        self.selected_files.clear()
        self.refresh_list()

    def action_quarantine_selected(self):
        for path in list(self.selected_files):
            self.core.move_to_quarantine(path)
        self.selected_files.clear()
        self.refresh_list()

    def action_update_tags(self):
        """Applies or changes tags for all selected files, cleaning spaces in process."""
        tag = self.tag_var.get()
        for path in list(self.selected_files):
            self.core.update_file_tag(path, tag)
        self.selected_files.clear()
        self.refresh_list()

    def action_restore_selected(self):
        downloads_dir = Path.home() / "Downloads"
        for path in list(self.selected_files):
            p = Path(path)
            if p.exists():
                shutil.move(str(p), str(downloads_dir / p.name))
        self.selected_files.clear()
        self.refresh_list()

    # --- SYSTEM TRAY LOGIC ---
    def create_tray_image(self):
        # Tworzy prostą niebieską ikonkę, jeśli nie masz pliku .ico
        image = Image.new('RGB', (64, 64), color=self.accent_blue)
        d = ImageDraw.Draw(image)
        d.text((10, 10), "T", fill="white") # Proste logo
        return image

    def hide_to_tray(self):
        self.withdraw() # Chowa okno (nie zabija procesu)
        self.spawn_tray_icon()

    def spawn_tray_icon(self):
        image = Image.open("assets/logo.png")
        menu = pystray.Menu(
            pystray.MenuItem('Open', self.restore_from_tray),
            pystray.MenuItem('Quit', self.quit_app)
        )
        self.tray_icon = pystray.Icon("TempApp", image, "Temp", menu)
        
        # Ikona musi biec w osobnym wątku, żeby nie zablokować Pythona
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def restore_from_tray(self, icon=None, item=None):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        
        self.after(0, self.deiconify) # Bezpieczne przywrócenie okna Tkinter
        self.after(0, self.refresh_list) # Odświeżamy listę przy pokazaniu


    def quit_app(self, icon=None, item=None):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.destroy()
        os._exit(0) # Brutalne ubicie wszystkich wątków w tle

    def build_settings_view(self):
        """Renders the list of monitored folders with remove buttons."""
        # Nagłówek sekcji
        ctk.CTkLabel(self.list_container, text="Monitored Folders", font=("Segoe UI", 16, "bold")).pack(pady=(10, 20))

        for folder in self.core.config["monitored_folders"]:
            row = ctk.CTkFrame(self.list_container, fg_color=self.bg_row, corner_radius=0, height=40)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=folder, anchor="w", font=("Segoe UI", 12)).pack(side="left", padx=15)
            
            # Przycisk usuwania folderu
            ctk.CTkButton(
                row, text="Remove", width=60, height=24, fg_color=self.danger_red, corner_radius=0,
                command=lambda f=folder: [self.core.remove_monitored_folder(f), self.refresh_list()]
            ).pack(side="right", padx=10)

        # Przycisk dodawania nowego folderu
        ctk.CTkButton(
            self.list_container, text="+ Add New Folder", fg_color=self.accent_blue, corner_radius=0,
            command=self.action_add_folder_dialog
        ).pack(pady=30)

    def action_add_folder_dialog(self):
        folder = filedialog.askdirectory()
        if folder:
            self.core.add_monitored_folder(folder)
            self.refresh_list()