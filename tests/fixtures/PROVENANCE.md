# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-09-23** von der Live-Quelle `https://www.bista.zh.ch/basicapi/ogd`, unveraendert bis auf die dokumentierte Zeilenauswahl.

Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht
mehr zu unterscheiden — die Datei sieht gleich aus, und niemand weiss,
ob sie den Stand von gestern zeigt oder den von vor drei
Schema-Wechseln. Das Datum macht diesen Abstand zu einer lesbaren Zahl.

Die Kopfzeilen stehen absichtlich **so, wie die Quelle sie an diesem
Tag geschrieben hat**, inklusive der uneinheitlichen Schreibweise
zwischen den Endpunkten und innerhalb einzelner Zeilen. Sie zu
vereinheitlichen wuerde genau die Eigenschaft wegputzen, an der der
Server am 3.8.2026 gescheitert ist.

## `sek1.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_sekundarstufe_i_anforderungstyp`
- **Aufgezeichnet:** 2026-09-23
- **Auswahl:** alle Zeilen zu den Schulgemeinden Zuerich-Letzi und Adliswil — 277 von 13902 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,schulgemeinde,anforderungstyp,anzahl`
- **SHA-256:** `00eefe91cf0aa9b9dee25d532c17c649489839057afc0067848418af61e8f70d`

## `uebersicht.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_uebersicht_alle_lernende`
- **Aufgezeichnet:** 2026-09-23
- **Auswahl:** alle Zeilen des juengsten Jahrgangs — 110 von 3192 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,stufe,schultyp,geschlecht,staatsangehoerigkeit,traegerschaft,finanzierung,anzahl`
- **SHA-256:** `73f392e6becc462ebfcb110e3f72329963c738cbb9525addfd1beb48ad30ab93`

## `nat_regional.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_regelschule_regional_staatsangehoerigkeit`
- **Aufgezeichnet:** 2026-09-23
- **Auswahl:** Schultraeger Zuerich-Letzi und Andelfingen, juengster Jahrgang — 65 von 65542 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,schultraeger_code,schultraeger,schultraeger_typ,staatsangehoerigkeit,staatsangehoerigkeit_iso2_code,anzahl`
- **SHA-256:** `65e965ac48ff636ea2e40c3208f33ba86a88b2c5907d6850115fe006544bb216`

## `maturitaet.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_maturitaetsquote_gemeinden_und_kanton`
- **Aufgezeichnet:** 2026-09-23
- **Auswahl:** Gemeinden Zuerich und Winterthur — 24 von 1981 Zeilen
- **Kopfzeile:** `Stand,Stand_Gemeindegrenzen,Bezirk,Gemeinde_BFSCode,Gemeinde,Total_Abschluss_gymnasial,Total_19_Jahre_alt,Maturitaetsquote_gymnasial`
- **SHA-256:** `ce44f54a9011465ab79aa81cc58c87b8c91bb2f365d1053b9e2b29505543e88e`

## `wohnort.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_nach_wohngemeinde`
- **Aufgezeichnet:** 2026-09-23
- **Auswahl:** Gebiet «Bezirk Winterthur», alle Jahre — 182 von 35903 Zeilen
- **Kopfzeile:** `jahr,gebietstyp_Code,gebietstyp,gebiet_Code,gebiet_Bezeichnung,stufe,anzahl`
- **SHA-256:** `213579f082d1ad610e89b63506e9ade756a6e33551c8fb7cc337e6a917b03bf9`

## `mittelschulen.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_mittelschulen`
- **Aufgezeichnet:** 2026-09-23
- **Auswahl:** alle Zeilen des juengsten Jahrgangs — 217 von 4717 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,stufe,mittelschultyp,bildungsart,geschlecht,finanzierung,staatsangehoerigkeit,anzahl`
- **SHA-256:** `74a218f00f501affeaaaed0e85e51c389dbe249e0c89200cf01936dc0ef0c678`
