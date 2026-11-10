# Ticketsystem für Home Assistant

Ein leichtgewichtiges Ticketsystem als **Custom Integration** – komplett lokal, ohne
Cloud, ohne Datenbank-Server. Tickets werden direkt in Home Assistant gespeichert,
über Services verwaltet und über zwei fertige Lovelace-Karten bedient:

| Karte | Zweck |
| --- | --- |
| `custom:ticket-submit-card` | Formular zum Einreichen neuer Tickets (Titel, Beschreibung, Dringlichkeit, Ersteller) |
| `custom:ticket-list-card` | Verwaltung aller Tickets: Suche, Filter, Sortierung nach Dringlichkeit, Statuswechsel per Klick |

Enthalten sind außerdem:

- vier Sensoren (offen, in Bearbeitung, kritisch, gesamt)
- fünf Services inkl. Antwortdaten für Automatisierungen
- drei Events (`ticket_system_ticket_created` / `_updated` / `_deleted`)
- **Benachrichtigungen** bei neuen Tickets, Sprachausgabe für kritische Tickets und
  Rückmeldung an den Ersteller bei Abschluss (konfigurierbar über die Optionen)
- deutsche und englische Oberflächentexte, deutsche **und** englische Service-Werte
  (`high` = `Hoch`, `in_progress` = `In Bearbeitung`, …)
- automatische Auslieferung der Karten durch die Integration – keine manuelle
  Lovelace-Ressource nötig

---

## Voraussetzungen

- Home Assistant **2024.11** oder neuer
- Lovelace (Standard-Dashboard) für die Karten
- HACS ist optional, aber empfohlen

---

## Installation

### Variante A: HACS (benutzerdefiniertes Repository)

1. HACS öffnen → Drei-Punkte-Menü oben rechts → **Benutzerdefinierte Repositories**.
2. Repository-URL eintragen: `https://github.com/Moritz2501/home-assistant-tickets`.
3. Kategorie **Integration** wählen → **Hinzufügen**.
4. In HACS nach **Ticketsystem** suchen → **Herunterladen**.
5. Home Assistant neu starten.
6. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Ticketsystem.**

### Variante B: manuell

1. Ordner `custom_components/ticket_system` aus diesem Repository nach
   `/config/custom_components/ticket_system` kopieren.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Ticketsystem.**

Die Einrichtung ist ein einzelner Dialog (Name der Integration) und kann nur einmal
durchgeführt werden.

---

## Datenmodell und Speicherung

Jedes Ticket besitzt genau die geforderten Felder:

```json
{
  "id": "20261110-114800-a1b2c3",
  "title": "Heizung im Wohnzimmer defekt",
  "description": "Wird seit heute Morgen nicht mehr warm.",
  "priority": "high",
  "status": "open",
  "author": "Max Mustermann",
  "created_at": "2026-11-10T11:48:00+00:00",
  "updated_at": "2026-11-10T11:52:10+00:00",
  "closed_at": null
}
```

| Feld | Werte |
| --- | --- |
| `id` | Zeitstempel-basiert und eindeutig, z. B. `20261110-114800-a1b2c3` |
| `priority` | `low`, `medium`, `high`, `critical` (Niedrig, Mittel, Hoch, Kritisch) |
| `status` | `open`, `in_progress`, `closed` (Offen, In Bearbeitung, Abgeschlossen) |
| `created_at` / `updated_at` / `closed_at` | ISO-8601 in UTC |

Gespeichert wird in `.storage/ticket_system.tickets` im Home-Assistant-Konfigurations-
verzeichnis. Die Datei ist damit automatisch Teil deiner Backups. Es gibt keine externe
Datenbank und keine Netzwerkverbindung.

---

## Sensoren

Die Integration legt ein Gerät (Name aus dem Einrichtungsdialog) mit vier Sensoren an:

| Sensor | Bedeutung |
| --- | --- |
| `sensor.ticketsystem_offene_tickets` | Tickets mit Status `open` |
| `sensor.ticketsystem_tickets_in_bearbeitung` | Tickets mit Status `in_progress` |
| `sensor.ticketsystem_kritische_tickets` | aktive (`open` + `in_progress`) Tickets der Dringlichkeit `critical` |
| `sensor.ticketsystem_tickets_gesamt` | alle Tickets |

Die Entity-IDs hängen von der Sprache und vom Namen der Integration ab – im Zweifel
unter **Entwicklerwerkzeuge → Zustände** nachsehen. Alle Sensoren liefern zusätzlich
die Attribute `by_status` und `by_priority`.

---

## Services

Alle Services sind unter **Entwicklerwerkzeuge → Aktionen** mit deutschen Feldnamen
verfügbar. Dringlichkeit und Status akzeptieren sowohl Schlüssel als auch deutsche
Schreibweisen.

### `ticket_system.create`

| Feld | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `title` | ja | – | Titel (max. 200 Zeichen) |
| `description` | nein | `""` | Beschreibung |
| `priority` | nein | `medium` | Dringlichkeit |
| `status` | nein | `open` | Anfangsstatus |
| `author` | nein | `Unbekannt` | Ersteller |
| `notify` | nein | `true` | Team (und bei „Kritisch“ die Mediaplayer) über dieses Ticket informieren |

```yaml
action: ticket_system.create
data:
  title: "Heizung im Wohnzimmer defekt"
  description: "Seit heute Morgen wird die Heizung nicht mehr warm."
  priority: high
  author: "Max Mustermann"
response_variable: ticket
```

Antwort:

```yaml
ticket_id: "20261110-114800-a1b2c3"
ticket:
  id: "20261110-114800-a1b2c3"
  title: "Heizung im Wohnzimmer defekt"
  priority: high
  status: open
  # ...
```

### `ticket_system.update`

| Feld | Pflicht | Beschreibung |
| --- | --- | --- |
| `ticket_id` | ja | ID des Tickets |
| `title`, `description`, `priority`, `status`, `author` | nein | zu ändernde Felder |

```yaml
action: ticket_system.update
data:
  ticket_id: "20261110-114800-a1b2c3"
  priority: critical
  description: "Heizung ist komplett ausgefallen, Techniker informiert."
```

### `ticket_system.set_status`

| Feld | Pflicht | Beschreibung |
| --- | --- | --- |
| `ticket_id` | ja | ID des Tickets |
| `status` | ja | `open`, `in_progress` oder `closed` |

```yaml
action: ticket_system.set_status
data:
  ticket_id: "20261110-114800-a1b2c3"
  status: in_progress
```

### `ticket_system.delete`

```yaml
action: ticket_system.delete
data:
  ticket_id: "20261110-114800-a1b2c3"
```

### `ticket_system.notify`

Verschickt eine Information oder Erinnerung zu einem bestehenden Ticket – gedacht für
Automationen und die Schnellaktionen der Verwaltungskarte.

| Feld | Pflicht | Standard | Beschreibung |
| --- | --- | --- | --- |
| `ticket_id` | ja | – | ID des Tickets |
| `kind` | nein | `info` | `info` (Sachstand) oder `reminder` (Erinnerung inkl. Wartezeit) |
| `target` | nein | `admins` | `admins`, `creator` oder `all` |
| `message` | nein | automatisch | eigener Nachrichtentext |
| `title` | nein | automatisch | eigener Titel |
| `notify_service` | nein | – | nur diesen Dienst nutzen, z. B. `mobile_app_pixel` |

```yaml
action: ticket_system.notify
data:
  ticket_id: "20261110-114800-a1b2c3"
  kind: reminder
  target: admins
```

```yaml
action: ticket_system.notify
data:
  ticket_id: "20261110-114800-a1b2c3"
  notify_service: mobile_app_pixel
  title: "Bitte übernehmen"
  message: "Das Ticket wartet seit heute Morgen auf einen Techniker."
```

Antwort (nur mit `response_variable` abrufbar):

```yaml
sent:
  - notify.persistent_notification
failed: []
```

Konnte über keinen Dienst gesendet werden, bricht der Service mit einer verständlichen
Fehlermeldung ab (z. B. wenn in den Optionen nur gelöschte Dienste stehen).

> Hinweis: Unbekannte Ticket-IDs führen zu einem verständlichen Fehler
> (`Ticket '…' wurde nicht gefunden.`). `create` gibt als einziger Service
> `ticket_id` zurück; `update` und `set_status` geben das aktualisierte `ticket` zurück.

---

## Events

Für Automatisierungen feuert die Integration drei Events auf dem Event-Bus:

| Event | Nutzdaten |
| --- | --- |
| `ticket_system_ticket_created` | `{ "ticket": { … } }` |
| `ticket_system_ticket_updated` | `{ "ticket": { … }, "changes": ["status"] }` |
| `ticket_system_ticket_deleted` | `{ "ticket": { … } }` |

`changes` enthält nur die Felder, die sich tatsächlich geändert haben.

```yaml
trigger:
  - platform: event
    event_type: ticket_system_ticket_created
condition:
  - condition: template
    value_template: "{{ trigger.event.data.ticket.priority == 'critical' }}"
action:
  - action: notify.persistent_notification
    data:
      title: "Kritisches Ticket"
      message: "{{ trigger.event.data.ticket.title }} von {{ trigger.event.data.ticket.author }}"
```

Weitere Beispiele: [`examples/automations.yaml`](examples/automations.yaml).

---

## Benachrichtigungen

Die Integration meldet sich von selbst – ohne Automatisierung. Einstellungen unter
**Einstellungen → Geräte & Dienste → Ticketsystem → Konfigurieren**. Änderungen greifen
sofort, ein Neustart ist nicht nötig.

### Optionen

| Option | Standard | Bedeutung |
| --- | --- | --- |
| Benachrichtigungsdienste für das Team | `notify.persistent_notification` | Mehrfachauswahl, z. B. `notify.persistent_notification`, `notify.mobile_app_pixel`, `notify.telegram` |
| Benachrichtigungsdienste für den Ersteller | leer | Empfänger der Abschluss-Info; leer = Team-Dienste |
| Bei neuen Tickets benachrichtigen | an | Info an das Team beim Anlegen |
| Ersteller bei Abschluss benachrichtigen | an | Info, sobald ein Ticket auf „Abgeschlossen“ wechselt |
| Kritische Tickets ansagen | an | zusätzliche Sprachausgabe |
| TTS-Entität | – | `tts.*`, z. B. `tts.cloud` oder `tts.piper` |
| Mediaplayer für Ansagen | leer | eine oder mehrere `media_player.*`-Entitäten |
| Gesprochener Text | `Kritisches Ticket im Ticketsystem: {title}. Bitte sofort prüfen.` | Platzhalter: `{title}`, `{priority}`, `{author}`, `{id}` |
| Lautstärke vor der Ansage | 0 % | setzt vor jeder Ansage `media_player.volume_set` (0–100 %, **0 % = Lautstärke nicht ändern**); der alte Pegel wird danach wiederhergestellt |

### Was wann passiert

| Auslöser | Empfänger | Inhalt |
| --- | --- | --- |
| Ticket erstellt | Team-Dienste | Titel, Dringlichkeit, Status, Ersteller, ID und Beschreibung (max. 500 Zeichen) |
| Ticket erstellt mit Dringlichkeit **Kritisch** | zusätzlich die Mediaplayer | gesprochener Text aus dem Template |
| Status wechselt auf **Abgeschlossen** | Ersteller-Dienste (sonst Team) | Abschluss-Info mit Titel, Ersteller und ID |

Im Formular lässt sich die Benachrichtigung pro Ticket abwählen. Ein so erstelltes
Ticket (`notify: false`) löst weder Push noch Sprachausgabe aus – nützlich für Tickets,
die per Automation aus einem bekannten Ereignis entstehen.

### Sprachausgabe

- Mit **TTS-Entität + Mediaplayer** läuft alles über `tts.speak` (Home Assistant Cloud,
  Piper, Google Translate …).
- Gehört der Mediaplayer zu einem **Echo** (Integration „Alexa Devices“), wird direkt
  dessen `notify.<gerät>_announce`- bzw. `_speak`-Entität über `notify.send_message`
  angesagt – in übersetzten Installationen heißen die Entitäten z. B.
  `notify.moritz_durchsagen` und `notify.moritz_sprechen`, beides wird erkannt.
  `tts.speak` wird dort gar nicht erst versucht, weil Echo-Geräte die
  gestreamte Audiodatei mit `music is not available as a music provider` ablehnen.
- Alternativ bzw. als Rückfallebene nutzt die Integration **Alexa Media Player**
  (`notify.alexa_media`, je nach Version auch `notify.alexa_media_<konto>` mit
  `data.type: tts`).
- Ist nichts davon vorhanden, bleibt es bei der Text-Benachrichtigung; im Log steht ein
  einmaliger Hinweis, was fehlt.
- Mit **Lautstärke vor der Ansage** (Option, 0–100 %) wird pro Player zuerst
  `media_player.volume_set` aufgerufen und danach angesagt – so ist ein leise
  gedrehter Echo oder Sonos nicht zu überhören. Die vorherige Lautstärke merkt sich
  die Integration und stellt sie etwa 15 Sekunden später wieder her (Ansagen laufen
  asynchron, vorher würde die Ansage leiser werden). Bei 0 % bleibt der Pegel
  unangetastet; meldet der Player keinen Pegel (z. B. offline), wird nichts
  zurückgesetzt.
- Unbekannte Platzhalter bleiben im Text stehen, ein syntaktisch kaputtes Template fällt
  auf den Standardtext zurück.

### Benachrichtigungsdienste finden

Unter **Entwicklerwerkzeuge → Aktionen** nach `notify.` suchen. Typische Kandidaten:

- `notify.persistent_notification` – immer vorhanden, Glocke in der Seitenleiste
- `notify.mobile_app_<gerät>` – Companion-App, z. B. `notify.mobile_app_pixel_9`
- `notify.telegram`, `notify.signal`, `notify.pushover` – je nach eingerichteter Integration

Die Auswahl im Optionsdialog liest die vorhandenen `notify`-Dienste direkt aus Home
Assistant. Verschwindet ein Dienst später, wird er übersprungen und das Log meldet es –
die übrigen Dienste funktionieren weiter.

---

## Dashboard-Karten

### Registrierung

Die Integration liefert die Datei `ticket-system-cards.js` selbst aus und lädt sie als
JS-Modul (`/ticket_system/ticket-system-cards.js?v=1.1.8`). **Du musst keine Ressource
manuell anlegen.**

Ab Home Assistant 2026.8 ersetzt das Frontend `window.customElements` beim Start durch
ein Polyfill für „scoped custom element registries“. Module, die wie hier über
`add_extra_js_url` eingebunden werden, laufen häufig vorher – ihre Registrierung geht
dann still verloren und die Karte meldet „Custom element doesn't exist“. Die Karte
registriert sich deshalb selbst erneut, sobald das Polyfill aktiv ist (ab 1.1.3).

Nach der Installation:

1. Browser-Cache leeren bzw. mit `Strg + F5` neu laden.
2. Dashboard bearbeiten → **Karte hinzufügen** → nach „Ticket“ suchen.

Falls die Karten nicht auftauchen (z. B. weil das Frontend nachträglich geladen wurde),
kannst du sie als Fallback manuell registrieren:
**Einstellungen → Dashboards → Drei-Punkte-Menü → Ressourcen → Ressource hinzufügen**

| Feld | Wert |
| --- | --- |
| URL | `/ticket_system/ticket-system-cards.js?v=1.1.8` |
| Typ | JavaScript-Modul |

### Karte: `custom:ticket-submit-card`

Formular zum Einreichen. Der Ersteller wird mit dem Namen des angemeldeten
Home-Assistant-Benutzers vorbelegt und kann geändert werden.

| Option | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| `title` | string | `Ticket einreichen` | Überschrift |
| `subtitle` | string | `""` | Untertitel |
| `default_priority` | `low` \| `medium` \| `high` \| `critical` | `medium` | Vorauswahl |
| `show_priority` | bool | `true` | Dringlichkeits-Auswahl anzeigen |
| `show_description` | bool | `true` | Beschreibungsfeld anzeigen |
| `allow_author` | bool | `true` | Ersteller-Feld anzeigen |
| `show_notify` | bool | `true` | Auswahl „Team benachrichtigen“ anzeigen |
| `notify_default` | bool | `true` | Auswahl standardmäßig aktiv |
| `notify_label` | string | `Team über dieses Ticket benachrichtigen` | Beschriftung der Auswahl |
| `button_label` | string | `Ticket absenden` | Button-Text |
| `success_message` | string | `Ticket wurde erstellt – vielen Dank!` | Erfolgsmeldung |

```yaml
type: custom:ticket-submit-card
title: Neues Ticket einreichen
subtitle: Dein Anliegen landet direkt in der Ticket-Verwaltung.
default_priority: medium
show_priority: true
show_description: true
allow_author: true
show_notify: true
notify_default: true
notify_label: Team über dieses Ticket benachrichtigen
button_label: Ticket absenden
success_message: Danke! Dein Ticket wurde erstellt.
```

### Karte: `custom:ticket-list-card`

Verwaltung mit Suche, Filtern und Direktaktionen. Die Standard-Sortierung ist
**Dringlichkeit absteigend, danach neueste zuerst** – „Kritisch“ steht also oben.
Zusätzlich sortierbar nach „Neueste“, „Älteste“ und „Zuletzt geändert“.

Pro Ticket stehen je nach Status bereit:

- **In Bearbeitung** (nur bei `open`)
- **Abschließen** (bei `open` und `in_progress`)
- **Wieder öffnen** (bei `closed`)
- **Benachrichtigen** – schickt eine Info zum Ticket an das Team
- **Erinnerung** – schickt eine Erinnerung inkl. Wartezeit (nicht bei abgeschlossenen Tickets)
- **Löschen** (mit Rückfrage)

| Option | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| `title` | string | `Ticket-Verwaltung` | Überschrift |
| `subtitle` | string | `""` | Untertitel |
| `show_closed` | bool | `true` | abgeschlossene Tickets dauerhaft ausblenden, wenn `false` |
| `show_description` | bool | `true` | Beschreibung in der Liste anzeigen |
| `allow_status_change` | bool | `true` | Status-Buttons anzeigen |
| `allow_notify` | bool | `true` | Buttons „Benachrichtigen“ und „Erinnerung“ anzeigen |
| `allow_delete` | bool | `true` | Löschen-Button anzeigen |
| `default_status_filter` | `all` \| `open` \| `in_progress` \| `closed` | `all` | Startfilter |
| `max_items` | number | `0` | Anzahl sichtbarer Tickets (`0` = alle) |

```yaml
type: custom:ticket-list-card
title: Ticket-Verwaltung
subtitle: Nach Dringlichkeit sortiert – Kritisch zuerst.
show_closed: true
show_description: true
allow_status_change: true
allow_notify: true
allow_delete: true
default_status_filter: all
max_items: 0
```

### Komplettes Beispiel-Dashboard

Zwei Ansichten („Einreichen“ und „Verwaltung“) liegen fertig in
[`examples/dashboard-tickets.yaml`](examples/dashboard-tickets.yaml):

```yaml
title: Tickets
views:
  - title: Einreichen
    path: ticket-einreichen
    icon: mdi:ticket-plus-outline
    cards:
      - type: custom:ticket-submit-card
        title: Neues Ticket einreichen
      - type: entities
        title: Ticket-Übersicht
        entities:
          - sensor.ticketsystem_offene_tickets
          - sensor.ticketsystem_tickets_in_bearbeitung
          - sensor.ticketsystem_kritische_tickets
          - sensor.ticketsystem_tickets_gesamt

  - title: Verwaltung
    path: ticket-verwaltung
    icon: mdi:ticket-account
    cards:
      - type: custom:ticket-list-card
        title: Ticket-Verwaltung
        default_status_filter: all
      - type: custom:ticket-list-card
        title: Nächste Aufgaben
        show_closed: false
        show_description: false
        allow_delete: false
        max_items: 5
```

Einzufügen über **Dashboard → Stift → Drei-Punkte-Menü → Raw-Konfiguration bearbeiten**.

> **Sichtbarkeit:** Die Karten prüfen keine Benutzerrollen. Wer ein Dashboard mit der
> Verwaltungskarte sehen darf, kann dort auch Status ändern und Tickets löschen. Nutze
> die Dashboard-Sichtbarkeit pro Benutzer (Dashboard bearbeiten → Sichtbarkeit), um die
> Verwaltung auf Admins zu beschränken.

---

## Projektstruktur

```
.
├── custom_components/
│   └── ticket_system/
│       ├── __init__.py            # Setup, Storage, Frontend-Auslieferung
│       ├── config_flow.py         # UI-Einrichtung (eine Instanz)
│       ├── const.py               # Domäne, Feldwerte, Events
│       ├── manager.py             # Ticket-CRUD + Persistenz
│       ├── notifications.py       # Benachrichtigungen, TTS, notify-Service
│       ├── manifest.json
│       ├── brand/icon.png         # Icon für Geräte-UI und HACS
│       ├── sensor.py              # 4 Zähler-Sensoren
│       ├── services.py            # create / update / set_status / delete / notify
│       ├── services.yaml          # Felddefinitionen für die UI
│       ├── strings.json           # englische Quelltexte
│       ├── translations/
│       │   ├── de.json
│       │   └── en.json
│       ├── websocket_api.py       # list + subscribe für die Karten
│       └── frontend/
│           └── ticket-system-cards.js
├── examples/
│   ├── automations.yaml
│   └── dashboard-tickets.yaml
├── .github/workflows/validate.yml # hassfest + HACS-Validierung
├── hacs.json
├── .gitignore
├── LICENSE
└── README.md
```

Technischer Ablauf der Karten: Sie abonnieren `ticket_system/subscribe` über die
authentifizierte WebSocket-Verbindung von Home Assistant und erhalten bei jeder
Änderung die komplette, sortierte Ticketliste. Schreibzugriffe laufen über die
normalen Services – dadurch greifen die üblichen Home-Assistant-Berechtigungen und
Automatisierungen sehen dieselben Änderungen sofort.

---

## Veröffentlichung auf GitHub / HACS

1. Repository: <https://github.com/Moritz2501/home-assistant-tickets>. Dieses
   Verzeichnis liegt dort bereits als `main`; ein eigener Fork wird genauso gepusht:

   ```bash
   git init -b main
   git add .
   git commit -m "Ticketsystem: Custom Integration mit Lovelace-Karten"
   git remote add origin https://github.com/Moritz2501/home-assistant-tickets.git
   git push -u origin main
   ```

2. Repository-Einstellungen: Beschreibung setzen und Topics vergeben, z. B.
   `home-assistant`, `hacs`, `integration`, `ticket-system`, `lovelace`.

3. Release erstellen (`v1.1.8`) – HACS löst darüber Updates aus und zeigt die Version an.
   Tag und Version in `manifest.json` sollten übereinstimmen.

4. Der mitgelieferte Workflow `.github/workflows/validate.yml` prüft bei jedem Push
   `hassfest` und die HACS-Kriterien. Fehlermeldungen dort sind ernst zu nehmen, sie
   sind die gleichen Checks, die HACS beim Aufnehmen anwendet.

5. Nutzer installieren anschließend über **HACS → Benutzerdefinierte Repositories →
   Kategorie Integration**.

---

## Fehlerbehebung

| Problem | Ursache / Lösung |
| --- | --- |
| „Custom element doesn't exist: ticket-…-card“ | Das Frontend hat `window.customElements` nach dem Laden ausgetauscht (ab HA 2026.8) und die Registrierung ging verloren. Ab 1.1.3 registriert sich die Karte selbst neu – Seite mit `Strg + F5` neu laden. Bleibt es dabei: Ressource manuell anlegen (siehe „Registrierung“) und im Browser prüfen, ob `http://<dein-ha>:8123/ticket_system/ticket-system-cards.js` ausgeliefert wird. |
| Karten erscheinen nicht in der Kartenauswahl | Integration einmal neu laden (Einstellungen → Geräte & Dienste → Ticketsystem → Neu laden), dann Browser mit `Strg + F5` neu laden. Prüfe, ob `http://<dein-ha>:8123/ticket_system/ticket-system-cards.js` erreichbar ist. |
| „Tickets konnten nicht geladen werden“ | Die Integration ist nicht (mehr) eingerichtet. Unter Geräte & Dienste prüfen und ggf. neu hinzufügen; Log auf `ticket_system`-Fehler prüfen. |
| Änderungen kommen nicht an | Mehrere Browser-Tabs offen? Die Karte aktualisiert sich per Push; ein Reload der Seite hilft. |
| Tickets weg nach Neustart | `.storage/ticket_system.tickets` muss im Konfigurationsverzeichnis liegen und beschreibbar sein. |
| Dienst-Aufruf meldet „Unbekannte Dringlichkeit“ | Erlaubt sind `low/medium/high/critical` bzw. `Niedrig/Mittel/Hoch/Kritisch`. |
| Nach einem Update alte Kartendarstellung | `?v=`-Parameter der Ressource bzw. Browser-Cache leeren. |
| Keine Benachrichtigung bei neuen Tickets | Optionen der Integration prüfen (Team-Dienste, „Bei neuen Tickets benachrichtigen“) und ob das Ticket mit abgewählter Benachrichtigung erstellt wurde (`notify: false`). |
| Kritisches Ticket wird nicht angesagt | Es braucht mindestens einen Mediaplayer und entweder eine TTS-Entität (`tts.*`) oder ein Alexa-Gerät mit Speak-/Announce-Entität („Alexa Devices“) bzw. Alexa Media Player; siehe einmalige Warnung im Log. |
| Log: „Sprachausgabe auf media_player… fehlgeschlagen: … music is not available as a music provider“ | Der Zielplayer ist ein Echo-Gerät. `tts.speak` schickt eine Audiodatei an den Player, und Echo-Geräte lehnen das über `aioamazondevices` mit dieser Meldung ab. Ab **1.1.8** erkennt die Integration den Player und sagt direkt über seine Speak-/Announce-Entität an (Alexa Devices), sonst über Alexa Media Player; `tts.speak` wird für Echo-Geräte übersprungen. Steht in der Warnung zusätzlich ein fehlgeschlagener Alexa-Weg, sind die Geräte offline oder Ansagen in der Alexa-App deaktiviert. |
| „Es konnte keine Benachrichtigung gesendet werden“ | In den Optionen steht kein vorhandener `notify`-Dienst. Unter Entwicklerwerkzeuge → Aktionen prüfen, welcher Dienst existiert. |

Logs: **Einstellungen → System → Protokolle**, Filter `ticket_system`.

---

## Entwicklung

```bash
# Python-Syntax prüfen
python -m compileall custom_components/ticket_system

# JavaScript-Syntax prüfen
node --check custom_components/ticket_system/frontend/ticket-system-cards.js
```

Zum Testen den Ordner `custom_components/ticket_system` in eine Home-Assistant-
Testinstanz kopieren, neu starten und die Integration hinzufügen. Die Karten-Datei
benötigt keinen Build-Schritt; Änderungen werden nach einem Neuladen der Integration
und einem Hard-Refresh des Browsers übernommen.

---

## Lizenz

[MIT](LICENSE)
