import os
import re
import json
import shutil
import datetime
from pathlib import Path
from send2trash import send2trash

class TempCore:
    def __init__(self):
        # 1. Konfiguracja w %APPDATA%/TempApp
        self.app_data = Path(os.getenv('APPDATA')) / "TempApp"
        self.config_file = self.app_data / "config.json"
        self.quarantine_folder = self.app_data / "quarantine"
        
        # Tworzymy foldery, jeśli nie istnieją
        self.app_data.mkdir(parents=True, exist_ok=True)
        self.quarantine_folder.mkdir(parents=True, exist_ok=True)

        # 2. Domyślne ustawienia
        self.config = self.load_config()
        
        # 3. Regex do wykrywania tagu {#}
        self.tag_pattern = re.compile(r"\{(\d+)\}")

    def load_config(self):
        """Ładuje ustawienia z JSON lub tworzy domyślne."""
        defaults = {
            "monitored_folders": [str(Path.home() / "Downloads"), str(Path.home() / "Desktop")],
            "auto_clean": False
        }
        if self.config_file.exists():
            with open(self.config_file, "r", encoding="utf-8") as f:
                return {**defaults, **json.load(f)}
        return defaults

    def save_config(self):
        """Zapisuje aktualne ustawienia do pliku."""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def scan_for_tagged_files(self):
        """Przeszukuje foldery w poszukiwaniu plików z <t#>."""
        found_files = []
        for folder in self.config["monitored_folders"]:
            path = Path(folder)
            if not path.exists(): continue

            for file in path.iterdir():
                if file.is_file():
                    match = self.tag_pattern.search(file.name)
                    if match:
                        weeks = int(match.group(1))
                        # Data modyfikacji jako punkt odniesienia
                        m_time = datetime.datetime.fromtimestamp(file.stat().st_mtime)
                        expiry_date = m_time + datetime.timedelta(weeks=weeks)
                        days_left = (expiry_date - datetime.datetime.now()).days

                        found_files.append({
                            "name": file.name,
                            "full_path": str(file),
                            "days_left": days_left,
                            "is_expired": days_left < 0
                        })
        return found_files

    def get_new_files(self):
        new_files = []
        downloads = Path.home() / "Downloads"
        
        if downloads.exists():
            for file in downloads.iterdir():
                if file.is_file() and not self.tag_pattern.search(file.name):
                    c_time = datetime.datetime.fromtimestamp(file.stat().st_ctime)
                    # ZMIANA: Zamiast < 1, sprawdzamy czy plik ma mniej niż 30 dni
                    if (datetime.datetime.now() - c_time).days <= 30:
                        new_files.append({
                            "name": file.name,
                            "full_path": str(file),
                            "size_mb": round(file.stat().st_size / (1024 * 1024), 2)
                        })
        return new_files

    def run_auto_cleaner(self):
        """Funkcja przeznaczona do odpalenia w osobnym wątku. Cicho sprząta."""
        while True:
            try:
                files = self.scan_for_tagged_files()
                for f in files:
                    if f['is_expired']:
                        self.move_to_quarantine(f['full_path'])
            except Exception as e:
                print(f"Błąd auto-cleanera: {e}")
            
            # Usypia wątek na godzinę, po czym sprawdza znowu
            import time
            time.sleep(3600)

    def move_to_quarantine(self, file_path):
        """Przenosi plik do 'czyśćca' w AppData."""
        p = Path(file_path)
        if p.exists():
            target = self.quarantine_folder / p.name
            # Jeśli plik o tej nazwie już tam jest, dodaj timestamp
            if target.exists():
                target = self.quarantine_folder / f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{p.name}"
            
            shutil.move(str(p), str(target))
            return True
        return False

    def delete_permanently(self, file_path):
        """Wrzuca plik do systemowego kosza Windows."""
        p = Path(file_path)
        if p.exists():
            send2trash(str(p))
            return True
        return False
    
    def remove_tag(self, file_path):
        """Removes the {#} tag from the filename and renames it."""
        p = Path(file_path)
        if not p.exists(): return False
        
        # Usuwamy wzorzec {#} oraz ewentualną spację przed nim
        new_name = self.tag_pattern.sub("", p.name).replace("  ", " ").strip()
        
        # Jeśli po usunięciu tagu nazwa pliku zaczynałaby się od kropki (pusty stem) 
        # lub nic by nie zostało, lepiej nic nie robić.
        if new_name == p.name: return False
        
        new_path = p.parent / new_name
        p.rename(new_path)
        return True