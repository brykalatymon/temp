import sys 
from ui import TempApp 

if __name__ == "__main__":
    silent = "--silent" in sys.argv
    app = TempApp(silent_start=silent)
    app.mainloop()