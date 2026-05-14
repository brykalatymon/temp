import sys
from pathlib import Path
from ui import TempApp
from core import TempCore

if __name__ == "__main__":
    # 1. TRYB MENU KONTEKSTOWEGO
    if len(sys.argv) >= 4 and sys.argv[1] == "--tag":
        tag = sys.argv[2]
        file_path = sys.argv[3].strip('"') # Zabezpieczenie przed cudzysłowami
        
        core = TempCore()
        
        # Wyciągamy ścieżkę folderu z pliku i dodajemy do obserwowanych
        folder_path = str(Path(file_path).parent)
        core.add_monitored_folder(folder_path)
        
        core.update_file_tag(file_path, tag)
        sys.exit(0)

    # 2. STANDARDOWY START APLIKACJI
    silent = "--silent" in sys.argv
    app = TempApp(silent_start=silent)
    app.mainloop()