# ADR-0007: Deklarative Missionen mit Ziel-, Trigger- und Aktions-Register

- **Status:** Angenommen · **Datum:** 2026-10-31 · **Phase:** 9

## Kontext

Kampagne und Tutorials brauchen Ziele, zeitgesteuerte Ereignisse, Hinweise und Siegbedingungen.
Dieselben Bausteine dienen später den Spielmodi (König des Hügels, Kopfgeld, Schatzsuche).

## Optionen

1. Eine eingebettete Skriptsprache (Lua, Python-Snippets in Daten): mächtig, aber unsicher und
   schwer zu testen.
2. **Deklaratives JSON** (Ziele, Trigger „wenn Ereignis X mit Bedingung Y“, Aktionen) mit einem
   Python-Register für Ziel-, Bedingungs- und Aktionstypen.

## Entscheidung

Option 2. Der `MissionRunner` abonniert den Ereignisbus (Plan Phase 0.4), wertet Trigger aus
und ruft registrierte Aktionen auf. Neue Typen sind kleine Python-Klassen mit Tests. Missionen sind
headless über ein Eingabeprotokoll lösbar, so wird jede Mission automatisch auf Lösbarkeit getestet.

## Konsequenzen

- Missionen und Tutorials sind reine Inhalte und vom Kern getrennt.
- Sehr ungewöhnliche Abläufe brauchen einen neuen Aktionstyp im Code. Das ist gewollt.
