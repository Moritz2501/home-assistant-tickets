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
- vier Services inkl. Antwortdaten für Automatisierungen
- drei Events (`ticket_system_ticket_created` / `_updated` / `_deleted`)
- deutsche und englische Oberflächentexte, deutsche **und** englische Service-Werte
  (`high` = `Hoch`, `in_progress` = `In Bearbeitung`, …)
- automatische Auslieferung der Karten durch die Integration – keine manuelle
  Lovelace-Ressource nötig

---

## Voraussetzungen

- Home Assistant **2024.7** oder neuer
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

> Hinweis: Unbekannte Ticket-IDs führen zu einem verständlichen Fehler
> (`Ticket '…' wurde nicht gefunden.`). `create` gibt als einziger Service
> `ticket_id` zurück; `update` und `set_status` geben das aktualisierte `ticket` zurück.

---

## Events

Für Automatisierungen feuert die Integration drei Events auf dem Event-Bus:

| Event | Nutzdaten |
| --- | --- |
| `ticket_system_ticket_created` | `{ "ticket": { … } }` |
| `ticket_system_ticket_updated` | `{ "ticket": { … } }` |
| `ticket_system_ticket_deleted` | `{ "ticket": { … } }` |

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

## Dashboard-Karten

### Registrierung

Die Integration liefert die Datei `ticket-system-cards.js` selbst aus und lädt sie als
JS-Modul (`/ticket_system/ticket-system-cards.js?v=1.0.0`). **Du musst keine Ressource
manuell anlegen.**

Nach der Installation:

1. Browser-Cache leeren bzw. mit `Strg + F5` neu laden.
2. Dashboard bearbeiten → **Karte hinzufügen** → nach „Ticket“ suchen.

Falls die Karten nicht auftauchen (z. B. weil das Frontend nachträglich geladen wurde),
kannst du sie als Fallback manuell registrieren:
**Einstellungen → Dashboards → Drei-Punkte-Menü → Ressourcen → Ressource hinzufügen**

| Feld | Wert |
| --- | --- |
| URL | `/ticket_system/ticket-system-cards.js?v=1.0.0` |
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
- **Löschen** (mit Rückfrage)

| Option | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| `title` | string | `Ticket-Verwaltung` | Überschrift |
| `subtitle` | string | `""` | Untertitel |
| `show_closed` | bool | `true` | abgeschlossene Tickets dauerhaft ausblenden, wenn `false` |
| `show_description` | bool | `true` | Beschreibung in der Liste anzeigen |
| `allow_status_change` | bool | `true` | Status-Buttons anzeigen |
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
│       ├── manifest.json
│       ├── sensor.py              # 4 Zähler-Sensoren
│       ├── services.py            # create / update / set_status / delete
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

3. Release erstellen (`v1.0.0`) – HACS löst darüber Updates aus und zeigt die Version an.

4. Der mitgelieferte Workflow `.github/workflows/validate.yml` prüft bei jedem Push
   `hassfest` und die HACS-Kriterien. Fehlermeldungen dort sind ernst zu nehmen, sie
   sind die gleichen Checks, die HACS beim Aufnehmen anwendet.

5. Nutzer installieren anschließend über **HACS → Benutzerdefinierte Repositories →
   Kategorie Integration**.

---

## Fehlerbehebung

| Problem | Ursache / Lösung |
| --- | --- |
| Karten erscheinen nicht in der Kartenauswahl | Integration einmal neu laden (Einstellungen → Geräte & Dienste → Ticketsystem → Neu laden), dann Browser mit `Strg + F5` neu laden. Prüfe, ob `http://<dein-ha>:8123/ticket_system/ticket-system-cards.js` erreichbar ist. |
| „Tickets konnten nicht geladen werden“ | Die Integration ist nicht (mehr) eingerichtet. Unter Geräte & Dienste prüfen und ggf. neu hinzufügen; Log auf `ticket_system`-Fehler prüfen. |
| Änderungen kommen nicht an | Mehrere Browser-Tabs offen? Die Karte aktualisiert sich per Push; ein Reload der Seite hilft. |
| Tickets weg nach Neustart | `.storage/ticket_system.tickets` muss im Konfigurationsverzeichnis liegen und beschreibbar sein. |
| Dienst-Aufruf meldet „Unbekannte Dringlichkeit“ | Erlaubt sind `low/medium/high/critical` bzw. `Niedrig/Mittel/Hoch/Kritisch`. |
| Nach einem Update alte Kartendarstellung | `?v=`-Parameter der Ressource bzw. Browser-Cache leeren. |

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
