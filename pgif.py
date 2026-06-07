import os
import sys
import json
import threading

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    print("\nThe dependency tk is missing. Please install it to get me working :>")
    print("Tip: Run -> sudo pacman -S tk\n")
    sys.exit(1)

try:
    from PIL import Image, ImageTk
except ImportError:
    print("\nThe dependency pillow is missing. Please install it to get me working :>")
    print("Tip: Run -> sudo pacman -S python-pillow\n")
    sys.exit(1)

try:
    import imageio
except ImportError:
    print("\nThe dependency imageio is missing. Please install it to get me working :>")
    print("Tip: Run -> pip install imageio imageio-ffmpeg\n")
    sys.exit(1)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings.conf")

DEFAULT_SETTINGS = {
    "fps_limit": 60,
    "default_gif": "your_animation.gif",
    "default_save_path": CONFIG_FILE,
    "saved_sessions": {}
}

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except Exception:
            return DEFAULT_SETTINGS
    return DEFAULT_SETTINGS

def save_settings(settings):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings file: {e}")

def open_config_window(settings):
    root = tk.Tk()
    root.title("PGIF Settings Manager")
    root.geometry("400x220")
    root.columnconfigure(1, weight=1)
    
    tk.Label(root, text="FPS Limit:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
    fps_entry = tk.Entry(root)
    fps_entry.insert(0, str(settings.get("fps_limit", 60)))
    fps_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    
    tk.Label(root, text="Default GIF Name:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
    gif_entry = tk.Entry(root)
    gif_entry.insert(0, settings.get("default_gif", ""))
    gif_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
    
    tk.Label(root, text="Config Path:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
    path_entry = tk.Entry(root)
    path_entry.insert(0, settings.get("default_save_path", CONFIG_FILE))
    path_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
    
    def save_action():
        try:
            settings["fps_limit"] = int(fps_entry.get())
        except ValueError:
            settings["fps_limit"] = 60
        settings["default_gif"] = gif_entry.get().strip()
        settings["default_save_path"] = path_entry.get().strip()
        
        save_settings(settings)
        print("-> Configuration successfully written to settings.conf!")
        root.destroy()
        
    save_btn = tk.Button(root, text="Save Settings", command=save_action, bg="#2ecc71", fg="white")
    save_btn.grid(row=3, column=0, columnspan=2, padx=10, pady=20, sticky="ew")
    root.mainloop()

class FloatingMediaApp:
    def __init__(self, root, media_path, settings, session_key):
        self.root = root
        self.media_path = media_path
        self.settings = settings
        self.session_key = session_key
        
        self.session_data = settings.get("saved_sessions", {}).get(session_key, {})
        init_w = self.session_data.get("w", 300)
        init_h = self.session_data.get("h", 300)
        init_x = self.session_data.get("x", 100)
        init_y = self.session_data.get("y", 100)
        self.locked = self.session_data.get("locked", False)
        
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry(f"{init_w}x{init_h}+{init_x}+{init_y}")
        
        self.label = tk.Label(root, bd=0, bg='red' if self.locked else 'black')
        self.label.pack(fill=tk.BOTH, expand=True)
        
        self.raw_frames = []
        self.display_frames = []
        self.current_frame = 0
        self.delay = 50 
        
        self.load_media()
        self.animate()
        
        self.label.bind("<Button-1>", self.start_drag)
        self.label.bind("<B1-Motion>", self.drag)
        self.label.bind("<Button-3>", self.start_resize)
        self.label.bind("<B3-Motion>", self.resize)
        
        self.print_instructions()
        self.listener_thread = threading.Thread(target=self.terminal_listener, daemon=True)
        self.listener_thread.start()

    def load_media(self):
        if not os.path.exists(self.media_path):
            print(f"\nError: File '{self.media_path}' not found.")
            sys.exit(1)
            
        fps_limit = self.settings.get("fps_limit", 60)
        max_allowed_delay = int(1000 / fps_limit)
        
        self.raw_frames = []
        try:
            reader = imageio.get_reader(self.media_path)
            meta = reader.get_meta_data()
            
            detected_delay = None
            
            if "fps" in meta and meta["fps"] > 0:
                detected_delay = int(1000 / meta["fps"])
            elif "duration" in meta:
                if isinstance(meta["duration"], (int, float)):
                    detected_delay = int(meta["duration"])
                elif isinstance(meta["duration"], list) and len(meta["duration"]) > 0:
                    detected_delay = int(meta["duration"][0])
            
            if detected_delay and detected_delay > 0:
                self.delay = max(detected_delay, max_allowed_delay)
            else:
                self.delay = max(40, max_allowed_delay)
                
            for frame in reader:
                self.raw_frames.append(Image.fromarray(frame))
            reader.close()
        except Exception as e:
            print(f"Error parsing media layout container: {e}")
            sys.exit(1)
            
        self.cache_resized_frames()

    def cache_resized_frames(self):
        w = max(15, self.root.winfo_width())
        h = max(15, self.root.winfo_height())
        
        self.display_frames = []
        for img in self.raw_frames:
            resized = img.resize((w, h), Image.Resampling.BILINEAR)
            self.display_frames.append(ImageTk.PhotoImage(resized))

    def animate(self):
        if self.display_frames:
            self.current_frame = (self.current_frame + 1) % len(self.display_frames)
            self.label.config(image=self.display_frames[self.current_frame])
        self.root.after(self.delay, self.animate)

    def start_drag(self, event):
        if self.locked: return
        self.x = event.x
        self.y = event.y

    def drag(self, event):
        if self.locked: return
        x = self.root.winfo_x() + (event.x - self.x)
        y = self.root.winfo_y() + (event.y - self.y)
        self.root.geometry(f"+{x}+{y}")

    def start_resize(self, event):
        if self.locked: return
        self.start_width = self.root.winfo_width()
        self.start_height = self.root.winfo_height()
        self.start_x = event.x_root
        self.start_y = event.y_root

    def resize(self, event):
        if self.locked: return
        new_w = max(15, self.start_width + (event.x_root - self.start_x))
        new_h = max(15, self.start_height + (event.y_root - self.start_y))
        self.root.geometry(f"{new_w}x{new_h}")
        self.cache_resized_frames()

    def update_and_save_session(self, target_key):
        if "saved_sessions" not in self.settings:
            self.settings["saved_sessions"] = {}
        self.settings["saved_sessions"][target_key] = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
            "w": self.root.winfo_width(),
            "h": self.root.winfo_height(),
            "locked": self.locked
        }
        save_settings(self.settings)
        print(f"-> Session profile successfully saved under key: '{target_key}'\n")

    def terminal_listener(self):
        while True:
            try:
                user_input = input("Enter command (l/s/q): ").strip()
                parts = user_input.split(maxsplit=1)
                if not parts:
                    continue
                
                command = parts[0].lower()
                
                if command == 'l':
                    self.locked = not self.locked
                    status = "LOCKED" if self.locked else "UNLOCKED"
                    print(f"-> Status: {status}\n")
                    self.root.after(0, lambda: self.label.config(bg='red' if self.locked else 'black'))
                    self.update_and_save_session(self.session_key)
                    
                elif command == 's':
                    if len(parts) > 1:
                        target_profile = parts[1].strip()
                    else:
                        target_profile = input("Enter profile save name: ").strip()
                        if not target_profile:
                            print("-> Save cancelled: No name provided.\n")
                            continue
                    self.update_and_save_session(target_profile)
                    
                elif command == 'q':
                    print("-> Saving run parameters and shutting down gracefully...")
                    self.update_and_save_session(self.session_key)
                    self.root.close_app()
                    break
            except (KeyboardInterrupt, EOFError):
                self.update_and_save_session(self.session_key)
                self.root.close_app()
                break

    def print_instructions(self):
        print("=========================================")
        print(f" Active profile: {self.session_key}")
        print("=========================================")
        print(" Mouse Left-Click drag  -> Move")
        print(" Mouse Right-Click drag -> Resize")
        print("-----------------------------------------")
        print(" Commands:")
        print(" l        -> Toggle movement lock")
        print(" s        -> Save profile (could be used as 's <name>')")
        print(" q        -> Save and quit")
        print("=========================================\n")


if __name__ == "__main__":
    current_settings = load_settings()
    
    if "-conf" in sys.argv:
        open_config_window(current_settings)
        sys.exit(0)
        
    target_media_name = current_settings.get("default_gif", "your_animation.gif")
    session_profile_key = None
    
    args = sys.argv[1:]
    for arg in args:
        if arg.startswith("conf="):
            session_profile_key = arg.split("=", 1)[1]
        elif any(arg.lower().endswith(ext) for ext in ['.gif', '.mp4', '.avi', '.webm', '.mpeg', '.mov', '.m4v']):
            target_media_name = arg

    if not session_profile_key:
        session_profile_key = target_media_name

    script_directory = os.path.dirname(os.path.realpath(__file__))
    final_media_path = os.path.join(script_directory, target_media_name)

    root = tk.Tk()
    def close_app():
        root.quit()
        root.update()
    root.close_app = close_app

    app = FloatingMediaApp(root, final_media_path, current_settings, session_profile_key)
    root.update()
    app.cache_resized_frames()
    root.mainloop()