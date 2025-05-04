import requests
from bs4 import BeautifulSoup

import os
from urllib.parse import urljoin
from urllib.parse import unquote, urlparse
import re
import requests

from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urljoin

USERNAME = ""
PASSWORD = ""
ALLOWED_EXTENSIONS = [".pdf", ".zip", ".docx"]
BLOCKED_EXTENSIONS = [".ppt", ".pptx"]
global log
log = ""

# Liste für neu heruntergeladene Dateien
from collections import defaultdict, deque

downloaded_files = defaultdict(lambda: defaultdict(list))

# Liste für alle gefundenen Dateien (nicht nur heruntergeladene)
found_files = defaultdict(lambda: defaultdict(list))

# boolean für manual download oder favoriten downnload
global manual
manual = False



def init_session():
    session = requests.Session()
    return session

def login(session, username, password):
    base_url = "https://ilias3.uni-stuttgart.de"
    login_form_url = f"{base_url}/login.php?client_id=Uni_Stuttgart&cmd=force_login&lang=en"

    try:
        # Login-Seite laden
        response = session.get(login_form_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Login-Formular finden
        form = soup.find("form", {"name": "login_form"})
        if not form:
            raise Exception("🥵 Kein Login-Formular gefunden!")

        # Alle Inputs holen
        payload = {}
        for input_tag in form.find_all("input"):
            name = input_tag.get("name")
            value = input_tag.get("value", "")
            if name:
                payload[name] = value

        # Benutzername und Passwort setzen
        payload["login_form/input_3/input_4"] = username
        payload["login_form/input_3/input_5"] = password

        # Formular absenden
        post_url = urljoin(base_url, form.get("action"))
        login_response = session.post(post_url, data=payload)
        login_response.raise_for_status()

        # Erfolg prüfen
        if "logout" in login_response.text.lower() or "Meine Kurse" in login_response.text:
            log.log_output("✅ Login erfolgreich!")
            return True
        else:
            log.log_output("❌ Login fehlgeschlagen. Passwort oder Nutzername falsch? 👀")
            return False

    except Exception as e:
        log.log_output(f"❌ Login-Fehler: {e}")
        return False

def sanitize_path_component(component):
    return re.sub(r'[<>:"/\\|?*]', '_', component)

def download_file(session, file_url, dest_path, feedbackfile=False):
    # Ordner anlegen, falls nicht vorhanden
    log.log_output("Ordner anlegen")
    if not os.path.exists(dest_path):
        os.makedirs(dest_path)

    # Datei anfordern (noch nicht speichern)
    try:
        response = session.get(file_url, stream=True)
        response.raise_for_status()
    except Exception as e:
        log.log_output(f"❌ Fehler beim Herunterladen: {e}")
        return

    # Versuch, den echten Dateinamen aus dem Header zu extrahieren
    filename = None
    content_disp = response.headers.get("Content-Disposition")
    if content_disp:
        match = re.search('filename="(.+?)"', content_disp)
        if match:
            filename = match.group(1)

    # Fallback, falls kein Dateiname im Header
    if not filename:
        parsed_url = urlparse(file_url)
        last_part = os.path.basename(parsed_url.path)
        filename = unquote(last_part)
        if not filename.endswith(".pdf"):
            filename += ".pdf"

    # Fix für Encoding-Probleme
    filename = filename.encode('latin1').decode('utf-8', errors='ignore').strip()

    filename = sanitize_path_component(filename)
    if feedbackfile:
        filename = "Feedback_" + filename
    file_path = os.path.join(dest_path, filename)

    # Existenz-Check
    if os.path.exists(file_path):
        log.log_output(f"⏭ Datei existiert schon: {filename}")
        return
    
    #Kontrolle von Dateinamenendung:
    if any(filename.lower().endswith(ext) for ext in BLOCKED_EXTENSIONS):
        log.log_output(f"⛔️ Datei blockiert (unerlaubte Endung): {filename}")
        return  # Download wird übersprungen

    # Speichern
    try:
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        log.log_output(f"✅ Datei gespeichert: {file_path}")
        relative_path = os.path.relpath(file_path, BASE_DIR)
        parts = relative_path.split(os.sep)

        if len(parts) >= 3:
            kursname = parts[0]
            subfolder = parts[1]
            filename = os.sep.join(parts[2:])
            downloaded_files[kursname][subfolder].append(filename)
        else:
            log.log_output(f"⚠️ Unerwarteter Pfad: {relative_path}")


    except Exception as e:
        log.log_output(f"❌ Fehler beim Schreiben der Datei: {e}")

def scrape_course(session, kursname, start_url, subfolder):
    log.log_output(f"\n🔍 Scanne Kurs: {sanitize_path_component(kursname)} → {sanitize_path_component(subfolder)}")

    visited_links = set()
    queue = [(start_url, subfolder)]  # Warteschlange für Ordner-Pfade

    while queue:
        current_url, current_path = queue.pop(0)

        if current_url in visited_links:
            continue
        visited_links.add(current_url)

        try:
            response = session.get(current_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            base_url = response.url
            all_links = soup.find_all('a', href=True)

            # Nur relevante Links rauspicken
            course_links_data = [
                (link.text.strip(), urljoin(base_url, link['href']))
                for link in all_links
                if ("go/fold" in link['href'] or "cmd=sendfile" in link['href'])
            ]

            # Breadcrumb-Ordner überspringen
            breadcrumb = soup.find('div', class_='breadcrumb')
            if breadcrumb:
                breadcrumb_folders = {span.text.strip() for span in breadcrumb.find_all('span', class_='crumb')}
                course_links_data = [
                    (title, detail_url)
                    for title, detail_url in course_links_data
                    if title not in breadcrumb_folders
                ]

            log.log_output(f"📁 Ordner: {current_path} → {len(course_links_data)} Links")

            # Alle direkten Datei-Titel merken
            direktdateien = {t for t, u in course_links_data if "cmd=sendfile" in u}

            for title, detail_url in course_links_data:
                if detail_url in visited_links:
                    continue

                try:
                    if "go/fold" in detail_url:
                        # Vorschau laden, um Redundanz zu prüfen
                        folder_response = session.get(detail_url)
                        folder_response.raise_for_status()
                        folder_soup = BeautifulSoup(folder_response.text, "html.parser")
                        folder_links = folder_soup.find_all("a", href=True)
                        folder_files = [l.text.strip() for l in folder_links if "cmd=sendfile" in l["href"]]

                        # Ordner redundant?
                        if folder_files and set(folder_files).issubset(direktdateien):
                            log.log_output(f"🚫 Überspringe redundanten Unterordner '{title}'")
                            continue

                        log.log_output(f"📂 Füge Ordner zur Queue hinzu: {title}")
                        queue.append((detail_url, os.path.join(current_path, sanitize_path_component(title))))

                    elif "cmd=sendfile" in detail_url:
                        log.log_output(f"📎 Gefundene Datei: {title} → {detail_url}")
                        found_files[kursname][current_path].append(title)
                        download_file(session, detail_url, os.path.join(BASE_DIR, kursname, current_path))

                except Exception as e:
                    log.log_output(f"⚠️ Fehler beim Link: {e}")

        except Exception as e:
            log.log_output(f"❌ Fehler beim Abrufen von {current_url}: {e}")

def scrape_assignments(session, kursname, kursurl, subfolder):
    log.log_output(f"\n🧩 Scanne Assignments in: {sanitize_path_component(kursname)} ({sanitize_path_component(subfolder)})")

    try:
        response = session.get(kursurl)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        base_url = response.url  # Wichtig für relative Links!

        # Hole alle Assignment-Links (nur href + text)
        assignment_links_data = [
            (link.text.strip(), urljoin(base_url, link['href']))
            for link in soup.find_all('a', href=True)
            if "AssignmentPresentationGUI" in link['href']
        ]

        log.log_output(f"✅ Gefundene Assignment-Links: {len(assignment_links_data)}")

        titles = set()  # set to prevent double saving
        for title, detail_url in assignment_links_data:
            if title in titles or detail_url in titles:
                continue
            titles.add(title)
            titles.add(detail_url)

            try:
                log.log_output(f"📎 Assignment gefunden: {title}")

                assignment_response = session.get(detail_url)
                assignment_response.raise_for_status()
                assignment_soup = BeautifulSoup(assignment_response.text, 'html.parser')

                download_links = assignment_soup.find_all('a', href=True)
                for file_link in download_links:
                    href = file_link['href']
                    if href and ("downloadFile" in href or "downloadFeedbackFile" in href):
                        full_url = urljoin(detail_url, href)
                        dest_path = os.path.join(BASE_DIR, kursname, subfolder, sanitize_path_component(title))
                        log.log_output(f"📥 Lade Datei herunter: {full_url}")
                        if "downloadFeedbackFile" in href:
                            download_file(session, full_url, dest_path, feedbackfile=True)
                        else:
                            download_file(session, full_url, dest_path)

            except Exception as e:
                log.log_output(f"⚠️ Fehler beim Assignment-Link: {e}")

    except Exception as e:
        log.log_output(f"❌ Fehler beim Abrufen der Assignments: {e}")


def scrape_assignments_stupid(session, kursname, kursurl, subfolder):
    scrape_course(session, kursname, kursurl, subfolder)
    log.log_output(f"\n🧩 Scanne Assignments in: {sanitize_path_component(kursname)} ({sanitize_path_component(subfolder)})")

    try:
        response = session.get(kursurl)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        base_url = response.url

        # Hole alle Assignment-Links (nur href + text)
        assignment_links_data = [
            (link.text.strip(), urljoin(base_url, link['href']))
            for link in soup.find_all('a', href=True)
            if "go/exc/" in link['href']
        ]

        log.log_output(f"✅ Gefundene Assignment-Links: {len(assignment_links_data)}")

        titles = set()  # set to prevent double saving
        for title, detail_url in assignment_links_data:
            if title in titles or detail_url in titles:
                continue
            titles.add(title)
            titles.add(detail_url)

            try:
                scrape_assignments(session, kursname, detail_url, subfolder)
            except Exception as e:
                log.log_output(f"⚠️ Fehler beim Assignment-Link: {e}")

    except Exception as e:
        log.log_output(f"❌ Fehler beim Abrufen der Assignments: {e}")


def scrape_everything_iterative(session, kursname, start_url, subfolder):
    log.log_output(f"\n🔍 Starte Scrape für: {sanitize_path_component(kursname)} → {sanitize_path_component(subfolder)}")

    visited = set()
    queue = deque()
    queue.append((start_url, subfolder))

    while queue:
        current_url, current_path = queue.popleft()

        if current_url in visited:
            continue
        visited.add(current_url)

        try:
            response = session.get(current_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            base_url = response.url

            log.log_output(f"\n🌐 Besuche: {base_url} → {current_path}")

            # Sammle alle relevanten Links auf dieser Seite
            all_links = soup.find_all('a', href=True)

            links_data = [
                (link.text.strip(), urljoin(base_url, link['href']))
                for link in all_links
                if any(p in link['href'] for p in ["go/fold", "cmd=sendfile", "go/exc", "go/crs", "go/grp", "AssignmentPresentationGUI", "downloadFile", "ilrepositorygui&ref_id"])
            ]

            # Breadcrumb-Ordner überspringen
            breadcrumb = soup.find('div', class_='breadcrumb')
            if breadcrumb:
                breadcrumb_folders = {span.text.strip() for span in breadcrumb.find_all('span', class_='crumb')}
                links_data = [
                    (title, detail_url)
                    for title, detail_url in links_data
                    if title not in breadcrumb_folders
                ]

            direktdateien = {t for t, u in links_data if "cmd=sendfile" in u}

            for title, detail_url in links_data:
                if detail_url in visited:
                    continue

                if "go/fold" in detail_url:
                    # Ordner-Vorschau holen
                    folder_response = session.get(detail_url)
                    folder_response.raise_for_status()
                    folder_soup = BeautifulSoup(folder_response.text, "html.parser")
                    folder_links = folder_soup.find_all("a", href=True)
                    folder_files = [l.text.strip() for l in folder_links if "cmd=sendfile" in l["href"]]

                    # Redundanz vermeiden
                    if folder_files and set(folder_files).issubset(direktdateien):
                        log.log_output(f"🚫 Überspringe redundanten Ordner: {title}")
                        continue

                    log.log_output(f"📂 Neuer Ordner gefunden: {title}")
                    queue.append((detail_url, os.path.join(current_path, sanitize_path_component(title))))

                elif "cmd=sendfile" in detail_url:
                    log.log_output(f"📥 Datei gefunden: {title}")
                    found_files[kursname][current_path].append(title)
                    download_file(session, detail_url, os.path.join(BASE_DIR, kursname, current_path))

                elif "go/exc/" in detail_url or "AssignmentPresentationGUI" in detail_url:
                    log.log_output(f"🧩 Assignment erkannt: {title}")
                    
                    # Transformiere die URL in das gewünschte Format
                    if "go/exc/" in detail_url:
                        match = re.search(r"go/exc/(\d+)", detail_url)
                        if match:
                            ref_id = match.group(1)
                            detail_url = f"https://ilias3.uni-stuttgart.de/ilias.php?baseClass=ilexercisehandlergui&cmdNode=cn:ns&cmdClass=ilObjExerciseGUI&cmd=showOverview&ref_id={ref_id}&mode=all&from_overview=1"

                    try:
                        scrape_assignments(session, kursname, detail_url, current_path)
                    except Exception as e:
                        log.log_output(f"⚠️ Fehler bei Assignment-Verarbeitung: {e}")

                elif "go/crs/" in detail_url or "go/grp/" in detail_url or "ilrepositorygui&ref_id" in detail_url:
                    log.log_output(f"🔁 Kurs-/Gruppenlink erkannt, füge hinzu: {title}")
                    queue.append((detail_url, os.path.join(current_path, sanitize_path_component(title))))

                elif "downloadFile" in detail_url:
                    log.log_output(f"📎 Datei aus special-case: {title}")
                    download_file(session, detail_url, os.path.join(BASE_DIR, kursname, current_path, sanitize_path_component(title)))

        except Exception as e:
            log.log_output(f"❌ Fehler beim Abrufen von {current_url}: {e}")
#Get Ilias Favoriten

def get_semester_kurse(session, dashboard_url):
    semester_filter = config_data["semester_filter"]
    folder_name = config_data["folder_name"]

    if not semester_filter:
        log.log_output("⚠️ Kein Semester-Filter gesetzt. Alle Kurse in den Favoriten werden geladen.")
    elif not manual:
        log.log_output(f"🔍 Filtere nach Semester: {semester_filter}")

    if folder_name and semester_filter and not manual:
        log.log_output(f"📁 Zielordner: {os.path.join(BASE_DIR, folder_name)}")

    semester_kurse = []
    try:
        response = session.get(dashboard_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        current_semester = None

        # Durchlaufe ALLE Tags, in Reihenfolge wie sie im DOM stehen
        for element in soup.find_all(True):
            tag_name = element.name
            if tag_name in ["h3"] and element.text:
                text = element.text.strip()
                if semester_filter:
                    if semester_filter in text:
                        current_semester = text  # neuen Kontext setzen
                    else:
                        current_semester = None
                elif "Sommer" in text or "Winter" in text:
                    current_semester = text  # neuen Kontext setzen
                continue

            if element.name == "a" and element.has_attr("href"):
                # Überspringe Links innerhalb von #block_pdmem_0
                if element.find_parent(id="block_pdmem_0"):
                    continue

                title = element.text.strip()
                href = element["href"]
                if "go/crs/" in href and current_semester:  # Nur Kurs-Links mit aktivem Semester
                    full_url = urljoin(dashboard_url, href)
                    semester_kurse.append((title, full_url, current_semester))
        
        # Ändere den Ordnernamen von semester_filter zu folder_name in der Ordnerstruktur von allen semester_kursen, falls folder_name und semester_filter gesetzt ist.
        if semester_filter and folder_name:
            for i, (title, url, semester) in enumerate(semester_kurse):
                if semester == semester_filter:
                    semester_kurse[i] = (title, url, folder_name)

    except Exception as e:
        log.log_output(f"❌ Fehler beim Parsen des Dashboards: {e}")
    return semester_kurse




#Formatierung für die Übersicht der neuen Dateien
def print_overview():
    global log
    log.log_output("\n📋 Übersicht der neu heruntergeladenen Dateien:")
    if not downloaded_files:
        log.log_output("✨ Keine neuen Dateien. Alles auf dem neuesten Stand! 🚀")
        return

    for kurs, subfolders in downloaded_files.items():
        log.log_output(f"\n📚 {kurs}")
        for sub, files in subfolders.items():
            log.log_output(f"├── {sub}")
            for f in files:
                log.log_output(f"│   └── {f}")
    
    log.log_output(f"\n🌟 Insgesamt {sum(len(f) for s in downloaded_files.values() for f in s.values())} neue Dateien geladen. Du bist ein verdammter Download-Magier! 🧙‍♂️💾")

#Telegram Nachricht:
def build_telegram_message():
    if not downloaded_files:
        return None
    
    message = "📥 *Neue Dateien von ILIAS:*\n"
    message += "```"
    for kurs, subfolders in downloaded_files.items():
        message += f"\n📚 {kurs}"
        for sub, files in subfolders.items():
            message += f"\n├── {sub}"
            for f in files:
                message += f"\n│   └── {f}"
    message += "\n```"
    return message

#Telegrammessage

def send_telegram_message(message, chat_id):
    # ONLY WORKS IN EXE
    return "Only works in .EXE"


def main1(logger, config, manuale):
    global manual
    global BASE_DIR
    global log
    global USERNAME
    global PASSWORD
    global BLOCKED_EXTENSIONS
    global downloaded_files
    global config_data

    log = logger
    # JSON-Daten laden
    config_data = config
    manual = manuale  # Ensure assignment happens after global declaration
    
    # Variables
    BASE_DIR = config_data["base_path"]
    USERNAME = config_data["username"]
    PASSWORD = log.config.get("password") or getattr(log, "_session_password", "")
    BLOCKED_EXTENSIONS = config_data["blocked_extensions"]

    session = init_session()
    login(session, USERNAME, PASSWORD)

    #Testing Ilias Favoriten
    kurse = get_semester_kurse(session, "https://ilias3.uni-stuttgart.de/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems")

    semester_dict = defaultdict(list)

    if not manual:
        # AUTOMATIC SCRAPE
        # Gruppiere Kurse nach Semester
        for titel, link, semester in kurse:
            clean_semester = sanitize_path_component(semester.replace("/", "-").replace(" ", "_"))
            clean_titel = sanitize_path_component(titel.replace("/", "-"))
            semester_dict[clean_semester].append((clean_titel, link))

        # Scrape Kurse innerhalb der Semester-Ordner
        for clean_semester, courses in semester_dict.items():
            for clean_titel, link in courses:
                kursname = clean_titel  # Nur der Titel ohne Semester-Prefix
                scrape_everything_iterative(session, os.path.join(clean_semester, kursname), link, subfolder="")
    else:
        # MANUAL SCRAPE.
        for course in config_data["courses"]:
            scrape_everything_iterative(session, course["name"], course["url"], course["subfolder"])

    # Übersicht anzeigen
    print_overview()

    # Telegram Nachricht
    if config_data["telegram_chat_id"]:
        msg = build_telegram_message()
        if msg:
            send_telegram_message(msg, config_data["telegram_chat_id"])
    
    downloaded_files = defaultdict(lambda: defaultdict(list)) ## if user wants to download again, reset the list
