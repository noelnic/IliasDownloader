import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys
import threading
import time
import requests 
import webbrowser  
from ilias_main import main1

GITHUB_API_URL = "https://api.github.com/repos/noelnic/IliasDownloader/releases/latest"
CURRENT_VERSION = "v0.4"  # Aktueller TAG

def check_for_updates():
    try:
        response = requests.get(GITHUB_API_URL, timeout=5)
        response.raise_for_status()
        latest_release = response.json()
        latest_version = latest_release.get("tag_name", "")
        download_url = latest_release.get("html_url", "")

        if latest_version and latest_version != CURRENT_VERSION:
            return f"Eine neue Version ({latest_version}) ist verfügbar!", download_url
        else:
            return "Die Anwendung ist auf dem neuesten Stand.", None
    except requests.RequestException as e:
        return f"Fehler bei der Update-Überprüfung: {e}", None

def write_readme():
    readme_content = """
📘 README – ILIAS Downloader

Willkommen zu deinem ILIAS-Download-Tool 💾🚀

🔐 Login:
  - Trage Username und Passwort ein (Passwort-Speicherung optional).
  - Telegram-ID ist optional (für Benachrichtigungen). Um herauszufinden, welche Chat_ID ihr habt, könnt ihr den CHAT_ID Telegram bot befragen.

📁 Kurse:
  - Gib Name, URL, Subfolder und Typ an.
        -URL: Einfach die Ilias-Seite kopieren, von der du downloaden möchtest.
        -Name: Bspw. PSE
        -Subfolder: Bspw. Vorlesungen (für VLS) und Übungen(für Abgabeblätter)
        Das ganze wird dann in einer Ordnerstruktur angelegt, sodass ihr Übungen unter PSE/Übungen findet etc.
        Du kannst diese Seiteninfos in der config selbst eintragen, oder in der UI. Schaue hierfür die Struktur an.
  - Wähle aus, welche Dateiformate ausgeschlossen werden sollen (z.B. pdf, pptx...).
  
  ODER: Favoriten Download (einfache Alternative, wenn man die links nicht heraussuchen möchte, lädt allerdings ALLES in deinen Favoriten herunter.)
  Du kannst hiermit auch nicht bestimmen wie die Ordner benannt werden. Es werden die Ilias-Ordnernamen verwendet.
  -Wähle den Favoriten-Download, um alle deine ILIAS-Favoriten herunterzuladen. 
  (Die Filterung nach Semester ist optional. Wenn du nur ein Semester herunterladen möchtest, gib den Namen des Semesters ein. Z.B. 'Sommer 2025' oder 'Winter 2024/25'. 
  Wenn du alle Semester herunterladen möchtest, lasse das Feld leer.)
    - Wenn du einen Ordnernamen angibst, wird dieser als Ordnername für das ausgewählte Semester verwendet.
    - Wenn du keinen Ordnernamen angibst, wird bspw. Sommer 2025 als Ordnername verwendet.

  - Getestet auf Windows.

🖥️ Download:
  - Der Download wird automatisch gestartet.
  - Der Pfad wird in config.json gespeichert.

💬 Viel Spaß & Feedback gerne!

– Niclas Noel Kuehn [Universität Stuttgart]👑
"""

    readme_path = get_config_path("README.txt")
    
    # Optional: nur schreiben, wenn die Datei noch nicht existiert
    if not os.path.exists(readme_path):
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

def get_config_path(filename="config.json"):
    # Wenn als .exe kompiliert
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)

CONFIG_PATH = get_config_path()

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:  # Sicherstellen, dass UTF-8 verwendet wird
            return json.load(f)
    else:
        return {
            "username": "",
            "password": "",
            "telegram_chat_id": "",
            "courses": [],
            "base_path": os.path.expanduser("~"),
            "blocked_extensions": [],  # 🆕 NEU!
            "semester_filter": "",
            "folder_name": ""
        }


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:  # Sicherstellen, dass UTF-8 verwendet wird
        json.dump(config, f, indent=4, ensure_ascii=False)  # ensure_ascii=False für korrekte Umlaut-Speicherung

class DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ILIAS Downloader - Niclas Noel Kuehn [Universitaet Stuttgart]")
        self.manual_bool = True

        self.config = load_config()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.login_frame = ttk.Frame(self.notebook)
        self.courses_frame = ttk.Frame(self.notebook)
        self.output_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.login_frame, text="🔐 Login")
        self.notebook.add(self.courses_frame, text="📚 Kurse")
        self.notebook.add(self.output_frame, text="📦 Status")

        self.create_login_tab()
        self.create_courses_tab()
        self.create_output_tab()

    def create_login_tab(self):
        ttk.Label(self.login_frame, text="Username:").pack(pady=5)
        self.username_entry = ttk.Entry(self.login_frame)
        self.username_entry.pack()
        self.username_entry.insert(0, self.config.get("username", ""))

        ttk.Label(self.login_frame, text="Passwort:").pack(pady=5)
        self.password_entry = ttk.Entry(self.login_frame, show="*")
        self.password_entry.pack()
        self.password_entry.insert(0, self.config.get("password", ""))

        self.save_password_var = tk.BooleanVar(value=True)  # standardmäßig speichern aktiv
        self.save_password_checkbox = ttk.Checkbutton(
            self.login_frame,
            text="🔒 Passwort speichern?",
            variable=self.save_password_var
        )
        self.save_password_checkbox.pack(pady=5)

        # Add clickable link for Telegram bot
        telegram_label = ttk.Label(self.login_frame, text="Telegram Chat ID (optional):", foreground="blue", cursor="hand2")
        telegram_label.pack(pady=5)
        telegram_label.bind("<Button-1>", lambda e: os.system("start https://t.me/username_to_id_bot"))

        self.telegram_entry = ttk.Entry(self.login_frame)
        self.telegram_entry.pack()
        self.telegram_entry.insert(0, self.config.get("telegram_chat_id", ""))

        # Add link to start chat with the bot
        start_chat_label = ttk.Label(self.login_frame, text="Start Chat with Bot", foreground="blue", cursor="hand2")
        start_chat_label.pack(pady=5)
        start_chat_label.bind("<Button-1>", lambda e: os.system("start https://t.me/NNKUNI_bot"))

        telegram_tooltip = ttk.Label(self.login_frame, text="?", foreground="blue", cursor="hand2")
        telegram_tooltip.pack(pady=5)
        create_tooltip(telegram_tooltip, "Die Telegram Chat ID wird verwendet, um Benachrichtigungen zu versenden. Klicke auf den oberen Link, um deine ChatID zu bekommen. Klicke auf den unteren Link um den Chat mit dem Bot zu starten, damit du Nachrichten empfangen kannst.")

        ttk.Label(self.login_frame, text="Gesperrte Dateiendungen (z.B. pdf, pptx):").pack(pady=5)
        self.blocked_entry = ttk.Entry(self.login_frame)
        self.blocked_entry.pack()
        self.blocked_entry.insert(0, ", ".join(self.config.get("blocked_extensions", [])))


        ttk.Label(self.login_frame, text="Download-Verzeichnis:").pack(pady=5)
        self.base_path_label = ttk.Label(self.login_frame, text=self.config.get("base_path", ""))
        self.base_path_label.pack()

        choose_path_btn = ttk.Button(self.login_frame, text="📁 Pfad wählen", command=self.choose_base_path)
        choose_path_btn.pack(pady=5)

        save_btn = ttk.Button(self.login_frame, text="💾 Speichern", command=self.save_login_data)
        save_btn.pack(pady=10)

        # Update-Status anzeigen
        update_status, download_url = check_for_updates()
        if download_url:
            self.update_label = ttk.Label(self.login_frame, text=update_status, foreground="red", cursor="hand2")
            self.update_label.bind("<Button-1>", lambda e: webbrowser.open(download_url))
        else:
            self.update_label = ttk.Label(self.login_frame, text=update_status, foreground="green")
        self.update_label.pack(pady=10)

    def choose_base_path(self):
        path = filedialog.askdirectory()
        if path:
            self.config["base_path"] = path
            self.base_path_label.config(text=path)
            save_config(self.config)
            messagebox.showinfo("Pfad gespeichert", f"Basis-Verzeichnis gesetzt auf:\n{path} ✅")

    def save_login_data(self):
        self.config["username"] = self.username_entry.get()
        self.config["telegram_chat_id"] = self.telegram_entry.get()

        # Passwort in RAM (self.config), aber nur speichern wenn Checkbox aktiv ist
        entered_password = self.password_entry.get()
        if self.save_password_var.get():
            self.config["password"] = entered_password
        else:
            self.config["password"] = ""  # nichts in Datei

        # Aber trotzdem im RAM speichern für direkten Zugriff
        self._session_password = entered_password

        # Blocked Extensions speichern
        self.config["blocked_extensions"] = self.blocked_entry.get().split(",")
        self.config["blocked_extensions"] = [ext.strip().lower() for ext in self.config["blocked_extensions"]]

        save_config(self.config)
        messagebox.showinfo("Gespeichert", "Login-Daten wurden gespeichert 💾✅")

    def collect_and_save_all_inputs(self):
        # Username & Telegram
        self.config["username"] = self.username_entry.get()
        self.config["telegram_chat_id"] = self.telegram_entry.get()

        # Passwort: speichern nur wenn Checkbox aktiv
        password = self.password_entry.get()
        self._session_password = password  # immer im RAM merken
        if self.save_password_var.get():
            self.config["password"] = password
        else:
            self.config["password"] = ""

        # Blocked Extensions (aus der UI holen, falls Feld da ist)
        if hasattr(self, "blocked_entry"):
            self.config["blocked_extensions"] = self.blocked_entry.get().split(",")
            self.config["blocked_extensions"] = [ext.strip().lower() for ext in self.config["blocked_extensions"]]

        # Speichern in Datei
        save_config(self.config)

    def create_courses_tab(self):
        self.courses_listbox = tk.Listbox(self.courses_frame, width=80, height=10)
        self.courses_listbox.pack(pady=10)
        self.refresh_courses_list()

        # Auswahloptionen für Kurs-Download-Modus
        mode_frame = ttk.Frame(self.courses_frame)
        mode_frame.pack(pady=10)

        self.download_mode = tk.StringVar(value="manual")  # Standardmodus: Manuell
        ttk.Label(mode_frame, text="Kurs-Download-Modus:").grid(row=0, column=0, sticky="w", pady=5)

        manual_mode_rb = ttk.Radiobutton(
            mode_frame, text="Manuell hinzufügen", variable=self.download_mode, value="manual", command=self.toggle_course_mode
        )
        manual_mode_rb.grid(row=1, column=0, sticky="w")

        favorites_mode_rb = ttk.Radiobutton(
            mode_frame, text="Favoriten von ILIAS herunterladen", variable=self.download_mode, value="favorites", command=self.toggle_course_mode
        )
        favorites_mode_rb.grid(row=2, column=0, sticky="w")

        # Frame für manuelles Hinzufügen von Kursen
        self.manual_frame = ttk.Frame(self.courses_frame)
        self.manual_frame.pack(pady=10)

        ttk.Label(self.manual_frame, text="Name:").grid(row=0, column=0, sticky="w", pady=2)
        name_reset = ttk.Button(self.manual_frame, text="X", width=2, command=lambda: self.course_name.delete(0, tk.END))
        name_reset.grid(row=1, column=0, padx=5, sticky="w")
        self.course_name = ttk.Entry(self.manual_frame, width=50)
        self.course_name.grid(row=1, column=1, pady=2)
        name_tooltip = ttk.Label(self.manual_frame, text="?", foreground="blue", cursor="hand2")
        name_tooltip.grid(row=1, column=2, padx=5)
        create_tooltip(name_tooltip, "Name des Kurses/Moduls, z.B. 'Machine Learning'.")

        ttk.Label(self.manual_frame, text="URL:").grid(row=2, column=0, sticky="w", pady=2)
        url_reset = ttk.Button(self.manual_frame, text="X", width=2, command=lambda: self.course_url.delete(0, tk.END))
        url_reset.grid(row=3, column=0, padx=5, sticky="w")
        self.course_url = ttk.Entry(self.manual_frame, width=50)
        self.course_url.grid(row=3, column=1, pady=2)
        url_tooltip = ttk.Label(self.manual_frame, text="?", foreground="blue", cursor="hand2")
        url_tooltip.grid(row=3, column=2, padx=5)
        create_tooltip(url_tooltip, "URL der ILIAS-Seite, z.B. 'https://ilias3.uni-stuttgart.de/ilias.php?baseClass=ilrepositorygui&ref_id=4024095'")

        ttk.Label(self.manual_frame, text="Subfolder:").grid(row=4, column=0, sticky="w", pady=2)
        subfolder_reset = ttk.Button(self.manual_frame, text="X", width=2, command=lambda: self.course_subfolder.delete(0, tk.END))
        subfolder_reset.grid(row=5, column=0, padx=5, sticky="w")
        self.course_subfolder = ttk.Entry(self.manual_frame, width=50)
        self.course_subfolder.grid(row=5, column=1, pady=2)
        subfolder_tooltip = ttk.Label(self.manual_frame, text="?", foreground="blue", cursor="hand2")
        subfolder_tooltip.grid(row=5, column=2, padx=5)
        create_tooltip(subfolder_tooltip, "Unterordner, in dem die Dateien gespeichert werden, z.B. 'Vorlesungen'.")

        add_btn = ttk.Button(self.manual_frame, text="➕ Hinzufügen", command=self.add_course)
        add_btn.grid(row=6, column=1, pady=5)

        # Button für Favoriten-Download
        self.favorites_btn = ttk.Button(self.courses_frame, text="🚀 Favoriten herunterladen", command=self.download_favorites)
        self.favorites_btn.pack(pady=10)
        self.favorites_btn.pack_forget()  # Standardmäßig verstecken

        self.del_btn = ttk.Button(self.courses_frame, text="🗑️ Löschen", command=self.delete_selected_course)
        self.del_btn.pack(pady=5, anchor="center")

        self.del_all_btn = ttk.Button(self.courses_frame, text="❌ Alle löschen", command=self.delete_all_courses, style="Red.TButton")
        self.del_all_btn.pack(pady=5, anchor="center")

        style = ttk.Style()
        style.configure("Red.TButton", foreground="red")

        self.start_btn = ttk.Button(self.courses_frame, text="🚀 Download starten", command=self.run_downloader_thread)
        self.start_btn.pack(pady=10, anchor="center")

    def toggle_course_mode(self):
        if self.download_mode.get() == "manual":
            self.manual_frame.pack(pady=10)
            self.favorites_btn.pack_forget()
            self.del_btn.pack(pady=5, anchor="center")
            self.del_all_btn.pack(pady=5, anchor="center")
            self.start_btn.pack(pady=10, anchor="center")

            # Verstecke Semester- und Ordnername-Felder
            if hasattr(self, 'semester_frame'):
                self.semester_frame.pack_forget()
        else:
            self.manual_frame.pack_forget()
            self.favorites_btn.pack(pady=10)

            # Verstecke Löschen, Alle löschen und Download starten Buttons
            self.del_btn.pack_forget()
            self.del_all_btn.pack_forget()
            self.start_btn.pack_forget()

            # Zeige Semester- und Ordnername-Felder
            if not hasattr(self, 'semester_frame'):
                self.semester_frame = ttk.Frame(self.courses_frame)
                self.semester_frame.pack(pady=10)

                ttk.Label(self.semester_frame, text="Semester:").grid(row=0, column=0, sticky="w", pady=2)
                self.semester_entry = ttk.Entry(self.semester_frame, width=30)
                self.semester_entry.grid(row=0, column=1, pady=2)
                self.semester_entry.insert(0, self.config.get("semester_filter", ""))

                semester_tooltip = ttk.Label(self.semester_frame, text="?", foreground="blue", cursor="hand2")
                semester_tooltip.grid(row=0, column=2, padx=5)
                create_tooltip(semester_tooltip, "spezifisches Semester, z.B. 'Sommer 2025' oder 'Winter 2024/25'. Leere Eingabe nimmt alle Favoriten.")

                ttk.Label(self.semester_frame, text="Ordnername für das ausgewählte Semester (optional):").grid(row=1, column=0, sticky="w", pady=2)
                self.folder_name_entry = ttk.Entry(self.semester_frame, width=30)
                self.folder_name_entry.grid(row=1, column=1, pady=2)
                self.folder_name_entry.insert(0, self.config.get("folder_name", ""))

                folder_name_tooltip = ttk.Label(self.semester_frame, text="?", foreground="blue", cursor="hand2")
                folder_name_tooltip.grid(row=1, column=2, padx=5)
                create_tooltip(folder_name_tooltip, "Optionaler Ordnername, falls das Semesterfeld ausgefüllt ist. Z.B. anstatt, dass der Ordner 'Sommer_2025' heißt, kannst du den Ordner 'Semester 5' nennen.")
            else:
                self.semester_frame.pack(pady=10)

    def download_favorites(self):
        self.log_output("⏳ Favoriten von ILIAS werden heruntergeladen...")
        self.manual_bool = False  # Automatic mode: Downloads Favorites.

        # Pass the semester filter and folder name to the backend
        semester_filter = self.semester_entry.get().strip() if hasattr(self, 'semester_entry') else None
        folder_name = self.folder_name_entry.get().strip() if hasattr(self, 'folder_name_entry') else None
        self.config['semester_filter'] = semester_filter
        self.config['folder_name'] = folder_name

        self.run_downloader_thread()

    def create_output_tab(self):
        # Make the output text widget read-only and add a scrollbar
        self.output_text = tk.Text(self.output_frame, height=20, wrap="word", state="normal")
        self.output_text.pack(side="left", padx=10, pady=10, fill="both", expand=True)

        scrollbar = ttk.Scrollbar(self.output_frame, orient="vertical", command=self.output_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.output_text.configure(yscrollcommand=scrollbar.set)

    def toggle_progress(self, event):
        item_id = self.progress_tree.identify_row(event.y)
        if item_id in self.progress_data:
            self.progress_data[item_id] = not self.progress_data[item_id]
            if self.progress_data[item_id]:
                self.progress_tree.item(item_id, tags=("checked",))
            else:
                self.progress_tree.item(item_id, tags=("unchecked",))

        # Entferne die blaue Hervorhebung
        self.progress_tree.selection_remove(item_id)

    def refresh_progress_tab(self, courses):
        self.progress_tree.delete(*self.progress_tree.get_children())
        for course in courses:
            course_id = self.progress_tree.insert("", "end", text=course["name"], open=True)
            subfolder_id = self.progress_tree.insert(course_id, "end", text=course["subfolder"], open=True)
            for file in course["files"]:
                file_id = self.progress_tree.insert(subfolder_id, "end", text=file, open=False)
                self.progress_data[file_id] = False

    def log_output(self, message):
        self.output_text.insert("end", message + "\n")
        self.output_text.see("end")

    def refresh_courses_list(self):
        self.courses_listbox.delete(0, tk.END)
        for c in self.config["courses"]:
            self.courses_listbox.insert(tk.END, f"{c['name']} → {c['subfolder']}")

    def add_course(self):
        new_course = {
            "name": self.course_name.get(),
            "url": self.course_url.get(),
            "subfolder": self.course_subfolder.get()
        }
        self.config["courses"].append(new_course)
        save_config(self.config)
        self.refresh_courses_list()
        self.log_output(f"➕ Kurs hinzugefügt: {new_course['name']} → {new_course['subfolder']}")

    def delete_selected_course(self):
        selected_index = self.courses_listbox.curselection()
        if not selected_index:
            return
        idx = selected_index[0]
        kurs = self.config["courses"].pop(idx)
        save_config(self.config)
        self.refresh_courses_list()
        self.log_output(f"🗑️ Kurs gelöscht: {kurs['name']}")

    def delete_all_courses(self):
        if messagebox.askyesno("Warnung", "Möchten Sie wirklich alle Kurse löschen?"):
            self.config["courses"].clear()
            save_config(self.config)
            self.refresh_courses_list()
            self.log_output("❌ Alle Kurse wurden gelöscht")

    def run_downloader_thread(self):
        self.notebook.select(self.output_frame)  # Direkt zum Status-Tab wechseln
        thread = threading.Thread(target=self.run_downloader)
        thread.start()

    def run_downloader(self):
        self.collect_and_save_all_inputs()
        self.log_output("⏳ Starte Download...")
        time.sleep(3)
        
        #BACKEND:
        main1(self, self.config, self.manual_bool)

# Tooltip-Funktion hinzufügen
def create_tooltip(widget, text):
    tooltip = tk.Toplevel(widget)
    tooltip.withdraw()
    tooltip.overrideredirect(True)
    tooltip_label = tk.Label(tooltip, text=text, background="yellow", relief="solid", borderwidth=1, wraplength=200)
    tooltip_label.pack()

    def show_tooltip(event):
        tooltip.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
        tooltip.deiconify()

    def hide_tooltip(event):
        tooltip.withdraw()

    widget.bind("<Enter>", show_tooltip)
    widget.bind("<Leave>", hide_tooltip)

if __name__ == "__main__":
    print
    root = tk.Tk()
    app = DownloaderApp(root)
    write_readme()
    root.mainloop()
