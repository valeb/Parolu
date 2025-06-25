# window.py
#
# Copyright 2025 walter
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw
from gi.repository import Gtk, Gio, GLib, Gdk

resource = Gio.Resource.load("/app/share/parolu.gresource")
Gio.Resource._register(resource)

import pyttsx4
import os
import shutil
import requests
import json
import time
import threading

from gtts import gTTS, lang

from .reader import Reader

from .pipervoice import VoiceManager

display = Gdk.Display.get_default()
if display:
    icon_theme = Gtk.IconTheme.get_for_display(display)
    icon_theme.add_search_path("/app/share/icons")

@Gtk.Template(resource_path='/im/bernard/Parolu/window.ui')
class ParoluWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'ParoluWindow'

    main_text_view = Gtk.Template.Child()  # Feld für Texteingabe
    open_button = Gtk.Template.Child()     # öffnet eine Datei
    save_text_button = Gtk.Template.Child()     # speichert den Text
    read_button = Gtk.Template.Child()     # spielt Audio-Datei ab
    save_button = Gtk.Template.Child()     # speichert Audio-Datei
    lang_chooser= Gtk.Template.Child()     # lädt Sprache
    pitch_chooser = Gtk.Template.Child()   # lädt Geschlecht
    speed_chooser= Gtk.Template.Child()    # lädt Sprechgeschwindigkeit
    voice_chooser= Gtk.Template.Child()    # lädt Stimme
    label_1 = Gtk.Template.Child()         # zeigt Stimmlage an
    adjustment_1 = Gtk.Template.Child()    # Wert der Stimmlage
    label_2 = Gtk.Template.Child()         # zeigt Geschwindigkeit an
    adjustment_2 = Gtk.Template.Child()    # Wert der Geschwindigkeit


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.is_playing = False

        # die Aktion zum Öffnen einer Datei wird hinzugefügt
        open_action = Gio.SimpleAction(name="open")
        open_action.connect("activate", self.open_file_dialog)
        self.add_action(open_action)

        # die Aktion zum Speichern des Texts wird hinzugefügt
        save_action = Gio.SimpleAction(name="save-as")
        save_action.connect("activate", self.save_text_dialog)
        self.add_action(save_action)

        # die Aktion zum Speichern des Audio-files wird hinzugefügt
        save_audio_action = Gio.SimpleAction(name="save-audio-as")
        save_audio_action.connect("activate", self.save_audio_dialog)
        self.add_action(save_audio_action)

        #die Aktion zum Hören des Texts wird hinzugefügt
        self.read_button.connect('clicked', self.read_text)

        #die Aktion zum  Speichern des Audio-files wird hinzugefügt
        self.save_button.connect('clicked', self.save_audio_dialog)

        #die Aktion beim Ändern der Stimmlage wird hinzugefügt
        self.adjustment_1.connect("value-changed", self.on_adjustment_value_changed)

        #die Aktion beim Ändern der Geschwindigkeit wird hinzugefügt
        self.adjustment_2.connect("value-changed", self.on_adjustment_value_changed)

        ## Operationen zum Auswählen bzw Laden einer Stimme ##
        # ======================================================================
        # Stimmen-API-URL hier können die piper-Stimmen heruntergeladen werden
        self.voices_api = "https://raw.githubusercontent.com/rhasspy/piper/master/VOICES.md"

         # Sprachzuordnung
        self.lang_map = {
            "Esperanto": "eo",
            "Deutsch": "de",
            "Italiano": "it",
            "Español": "es",
            "Francais": "fr",
        }
        self.voicemanager = VoiceManager(self)

        # Initiale UI-Aktualisierung
        self._connect_signals()
        self._setup_lang_chooser()

        lang_name = self.lang_chooser.get_selected_item().get_string()
        self.lang_code = self.lang_map.get(lang_name, "en")
        print ('Sprachkodex am Beginn  ', self.lang_code)

    def show_wait_dialog(self):
        self.wait_dialog = Gtk.Dialog(
            title="Synchronisierung",
            transient_for=self,  # Korrekt: self ist das Hauptfenster
            modal=True
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.append(Gtk.Label(label="Bitte warten..."))
        self.spinner = Gtk.Spinner()
        self.spinner.start()
        box.append(self.spinner)
        self.wait_dialog.set_child(box)
        self.wait_dialog.show()

    def hide_wait_dialog(self):
        if hasattr(self, 'wait_dialog') and self.wait_dialog:
            self.wait_dialog.destroy()
        if hasattr(self, 'spinner') and self.spinner:
            self.spinner.stop()

    def _show_error(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.connect("response", lambda d, _: d.destroy())
        dialog.show()

    def _connect_signals(self):
        self.lang_chooser.connect("notify::selected", self._on_lang_changed)
        self.voice_chooser.connect("notify::selected", self._on_voice_changed)

    def _setup_lang_chooser(self):
        # Signal vorübergehend deaktivieren
        self.lang_chooser.disconnect_by_func(self._on_lang_changed)

        # Aktuelle Sprache auswählen
        lang_name = self.lang_chooser.get_selected_item().get_string()
        self.lang_code = self.lang_map.get(lang_name, "en")
        self._update_voice_chooser(self.lang_code)
        print ('gewählte Sprache   ', lang_name)
        # Signal wieder verbinden
        self.lang_chooser.connect("notify::selected", self._on_lang_changed)

    def _on_lang_changed(self, dropdown, _):
        lang_name = self.lang_chooser.get_selected_item().get_string()
        print ('neue Sprache angeklickt', lang_name)
        self.lang_code = self.lang_map.get(lang_name, "en")
        self._update_voice_chooser(self.lang_code)

    def _on_voice_changed(self, dropdown, _):
        selected = dropdown.get_selected()
        model = dropdown.get_model()
        print ('$$$$$$$$$$$$$ in on voice changed  ', model)
        if selected == model.get_n_items() - 1:  # letzte Zeile ausgewählt
            if self.lang_code != "eo":
                self._show_voice_download_dialog()

    def _update_voice_chooser(self, lang_code):
        """Aktualisiert die Dropdown-Auswahl"""
        voices = self.voicemanager.get_installed_voices(lang_code)
        print ('lang_code in voice_chooser  ', lang_code)
        print ('verfügbare voices  ', voices)

        model = Gtk.StringList.new()
        for voice in voices:
            model.append(voice['name'])
            print ('Namen der Stimme voice[name]  = ', voice['name'])

        if lang_code != "eo":  # für Esperanto gibt es aktuell keine Stimmen
            model.append("Stimme herunterladen...")

        self.voice_chooser.set_model(model)
        self.voice_chooser.set_selected(0)   # stellt Auswahlfenster auf die erste Zeile

    def _show_voice_download_dialog(self):
        """Zeigt Download-Dialog an"""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Neue Stimme herunterladen"
        )

        # Lade verfügbare Stimmen vom Server
        available_voices = self._fetch_available_voices()
        print ('======= Verfügbare Stimmen  ', available_voices)
        # Erstelle Auswahl-Liste
        listbox = Gtk.ListBox()
        for voice in available_voices:
            row = Adw.ActionRow(title=voice['name'])
            # print ('in show voice_download_dialog model_url', model_url)
            print ('$$$####$$$$ in show voice_download_dialog voice', voice)
            btn = Gtk.Button(label="Installieren")
            btn.connect('clicked', self._on_voice_selected, voice['id'], voice['model_url'], voice['config_url'], dialog)
            row.add_suffix(btn)
            listbox.append(row)
        dialog.set_extra_child(listbox)
        dialog.present()

    def _fetch_available_voices(self):
        # Lädt verfügbare Stimmen von der Piper GitHub-Seite oder lokal zwischengespeichert
        try:
            #1. Versuche, von GitHub zu laden
            response = requests.get(
                self.voices_api,
                timeout=20  # Timeout nach 10 Sekunden
            )
            response.raise_for_status()  # Wirft Exception bei HTTP-Fehlern

            #2. Parse die Markdown-Antwort
            print ('### jetzt rufe ich aus fetch_available parse_voices auf für  ', self.lang_code)
            voices = self._parse_voices_md(response.text, self.lang_code)

            #3. Cache die Stimmen lokal
            cache_dir = os.path.join(GLib.get_user_cache_dir(), "parolu")
            os.makedirs(cache_dir, exist_ok=True)

            cache_file = os.path.join(cache_dir, "voices_cache.json")
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'voices': voices,
                    'lang': self.lang_code
                }, f)

            return voices

        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"Netzwerkfehler: {e}. Versuche Cache...")
            return self._load_cached_voices(lang_code)

    def _parse_voices_md(self, md_text, lang_code):
        """Parst das aktuelle Piper-Voices Markdown-Format"""
        voices = []
        current_lang = None
        current_voice = None
        # print ('Stimmen zum Download  ', md_text)
        for line in md_text.split('\n'):
            line = line.strip()

            # Sprachkategorie erkennen (z.B. "* Italian (`it_IT`, Italiano)")
            if line.startswith('* ') and '(`' in line:
                lang_parts = line.split('`')
                # print ('Teile der Stimme  ', lang_parts)
                if len(lang_parts) > 1:
                    current_lang = lang_parts[1].split('_')[0]  # Extrahiert "it" aus "it_IT"
                    current_voice = None

            # Nur Stimmen der gewählten Sprache verarbeiten
            if current_lang != lang_code:  # wenn andere Sprache wird Rest übersprungen
                continue

            # Stimmenname erkennen (z.B. "* paola")
            if line.startswith('* ') and not '(`' in line and not 'http' in line:
                current_voice = line.split('*')[1].strip()
                print ('aktuelle Stimme  ', current_voice)

            # Qualität und URLs erkennen (z.B. "* medium - [[model](http...)]")
            if current_voice and line.startswith('* ') and 'http' in line:
                quality = line.split('*')[1].split('-')[0].strip()
                urls = [u.split('(')[1].split(')')[0] for u in line.split('[') if 'http' in u]
                print ('---------- urls der Stimme in parse', urls)
                if urls and len(urls) >= 2:
                    voices.append({
                        'id': f"{lang_code}-{current_voice}-{quality}",
                        'name': f"{current_voice} ({quality})",
                        'model_url': urls[0],  # Erste URL ist das Modell
                        'config_url': urls[1],  # Zweite URL ist die Konfig
                        'quality': quality
                    })
        print ('##### voices aus parse', voices)

        return voices or [{'id': f"{lang_code}_default", 'name': "Standard-Stimme"}]

    def _load_cached_voices(self, lang_code):
        """Lädt zwischengespeicherte Stimmen falls Online-Laden fehlschlägt"""
        cache_file = os.path.join(
            GLib.get_user_cache_dir(),
            "parolu",
            "voices_cache.json"
        )

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    # Nur zurückgeben wenn gleiche Sprache oder keine Sprache gefiltert
                    if not lang_code or data.get('lang') == lang_code:
                        return data['voices']
            except Exception as e:
                print(f"Cache-Fehler: {e}")

        # Fallback-Stimme
        return [{
            'id': f"{lang_code}_default" if lang_code else "default",
            'name': "Standard-Stimme",
            'quality': "medium"
        }]

    def _on_voice_selected(self, btn, voice_id, model_url, config_url, dialog):
        """Installiert die ausgewählte Stimme"""

        lang_code = self.lang_code
        print ('voice_id in on_voice selected =  ', voice_id, 'Sprache', lang_code)

        # Initiale Meldung anzeigen
        GLib.idle_add(dialog.set_body, "Download läuft...")

        def on_progress(downloaded, total_size):
            # Prozentberechnung
            progress = int((downloaded / total_size) * 100) if total_size > 0 else 0
            GLib.idle_add(dialog.set_body, f"Download: {progress}%")

        def on_complete():
            GLib.idle_add(dialog.destroy)
            GLib.idle_add(self._update_voice_chooser, lang_code)

        # Download in einem separaten Thread starten
        def download_thread():
            self.voicemanager.download_voice(
                voice_id, model_url, config_url,
                progress_callback=on_progress
            )
            on_complete()

        threading.Thread(target=download_thread, daemon=True).start()
    ## ================================================================##
    # Dialog zum Öffnen einer Datei wird definiert
    def open_file_dialog(self, action, _):
        # Create a new file selection dialog, using the "open" mode
        native = Gtk.FileDialog()
        native.open(self, None, self.on_open_response)

    # Dialog zum Speichern einer Text-Datei wird definiert
    def save_text_dialog(self, action, _):
        native = Gtk.FileDialog()
        native.set_initial_name("text.txt")
        native.save(self, None, self.on_save_text_response)

    # Dialog zum Speichern einer Audio-Datei wird definiert
    def save_audio_dialog(self, action):
        native = Gtk.FileDialog()
        native.set_initial_name("audio.wav")
        native.save(self, None, self.on_save_audio_response)

    # definiert was geschieht wenn Datei ausgewählt/nicht ausgewählt wurde
    def on_open_response(self, dialog, result):
        file = dialog.open_finish(result)
        # If the user selected a file...
        if file is not None:
            # ... open itgit
            self.open_file(file)

    # definiert was geschieht wenn Text-Datei ausgewählt/nicht ausgewählt wurde
    def on_save_text_response(self, dialog, result):
        file = dialog.save_finish(result)
        if file is not None:
            self.save_text(file)

    # definiert was geschieht wenn Audio-Datei ausgewählt/nicht ausgewählt wurde
    def on_save_audio_response(self, dialog, result):
        file = dialog.save_finish(result)
        if file is not None:
            self.reader.save_audio_file(file)

    # definiert was geschieht wenn Stimmlage geändert wird
    def on_adjustment_value_changed(self, adjustment):
        value = adjustment.get_value()
        if adjustment == self.adjustment_1:
            self.label_1.set_text(f"× {value:.1f}")
        else:
            self.label_2.set_text(f"× {value:.1f}")

    # Inhalt der Textdatei wird asynchron geöffnet um die Anwendung nicht zu blockieren
    def open_file(self, file):
        file.load_contents_async(None, self.open_file_complete)

    # wird aufgerufen wenn das Einlesen fertig oder ein Fehler aufgetreten ist
    def open_file_complete(self, file, result):

        contents = file.load_contents_finish(result)  # enthält boolsche Variable, den eingelesenen Text, u.a.

        if not contents[0]:
            path = file.peek_path()
            print(f"Unable to open {path}: {contents[1]}")
            return

        # Kontrolle ob der eingelesene Inhalt ein Text ist
        try:
            text = contents[1].decode('utf-8')
        except UnicodeError as err:
            path = file.peek_path()
            print(f"Unable to load the contents of {path}: the file is not encoded with UTF-8")
            return

        buffer = self.main_text_view.get_buffer()
        buffer.set_text(text)
        start = buffer.get_start_iter()
        buffer.place_cursor(start)

    def save_text(self, file):
        buffer = self.main_text_view.get_buffer()

        # Retrieve the iterator at the start of the buffer
        start = buffer.get_start_iter()
        # Retrieve the iterator at the end of the buffer
        end = buffer.get_end_iter()
        # Retrieve all the visible text between the two bounds
        text = buffer.get_text(start, end, False)

        # If there is nothing to save, return early
        if not text:
            return

        bytes = GLib.Bytes.new(text.encode('utf-8'))

        # Start the asynchronous operation to save the data into the file
        file.replace_contents_bytes_async(bytes,
                                          None,
                                          False,
                                          Gio.FileCreateFlags.NONE,
                                          None,
                                          self.save_text_complete)

    def save_text_complete(self, file, result):
        res = file.replace_contents_finish(result)
        info = file.query_info("standard::display-name",
                               Gio.FileQueryInfoFlags.NONE)
        if info:
            display_name = info.get_attribute_string("standard::display-name")
        else:
            display_name = file.get_basename()
        if not res:
            print(f"Unable to save {display_name}")

    # Abspielen des Texts
    def read_text(self, button):
        print ('### Audio abspielen   ###')
        buffer = self.main_text_view.get_buffer()

        # Retrieve the iterator at the start of the buffer
        start = buffer.get_start_iter()
        # Retrieve the iterator at the end of the buffer
        end = buffer.get_end_iter()
        # Retrieve all the visible text between the two bounds
        text = buffer.get_text(start, end, False)

        engine = 'piper'
        print(engine)

        pitch = self.pitch_chooser.get_value()
        print('pitch', pitch)

        speed = self.speed_chooser.get_value()
        print('speed', speed)

        selected_voice = self.voice_chooser.get_selected_item().get_string()
        print('Stimme', selected_voice)

        #self.reader = Reader(text, engine, self.lang_code, selected_voice, pitch, speed, window=self)
        print ('is_playing:', self.is_playing)
        if self.is_playing:
            self.stop_playback(button)
        else:
            self.start_playback(button, text, engine, self.lang_code, selected_voice, pitch, speed)

    # def _update_play_button(self):
    #     print( """Sicherer UI-Update über GLib.idle_add""")
    #     button = self.read_button
    #     button.set_icon_name ("media-playback-stop-symbolic")

    def start_playback(self, button, text, engine, lang_code, selected_voice, pitch, speed):
        """Startet die Wiedergabe und aktualisier t UI"""
        if not self.is_playing:
            #self.read_text(button)  # Deine bestehende Methode
            self.reader = Reader(text, engine, self.lang_code, selected_voice, pitch, speed, window=self)

            self.is_playing = True
            button.set_icon_name("media-playback-stop-symbolic")

    def stop_playback(self, button):
        """Stoppt die Wiedergabe und aktualisiert UI"""
        if self.is_playing:
            # Hier müsstest du den Reader stoppen - je nach Implementierung:
            if hasattr(self, 'reader') and self.reader:
                self.reader.stop_audio()  # Annahme: dein Reader hat eine stop()-Methode
            self.is_playing = False
            button.set_icon_name("media-playback-start-symbolic")

