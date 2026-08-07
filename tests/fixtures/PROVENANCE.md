# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-08-07** von der Live-Quelle `https://www.bista.zh.ch/basicapi/ogd`, unveraendert bis auf die dokumentierte Zeilenauswahl.

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
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** alle Zeilen zu den Schulgemeinden Zuerich-Letzi und Adliswil — 277 von 13902 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,schulgemeinde,anforderungstyp,anzahl`
- **SHA-256:** `304e49a589dea87f2e11d3a9ed9aecbf7f7456b3394a277d1f9f9eeeff1ca00a`

## `uebersicht.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_uebersicht_alle_lernende`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** alle Zeilen des juengsten Jahrgangs — 110 von 3192 Zeilen
- **Kopfzeile:** `Stand,Kanton,Jahr,Stufe,Schultyp,Geschlecht,Staatsangehoerigkeit,Traegerschaft,Finanzierung,Anzahl`
- **SHA-256:** `f931d2ae9637dafbec0592476a7c52d4f3de86259d115c8e3517cffe33432afe`

## `nat_regional.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_regelschule_regional_staatsangehoerigkeit`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** Schulgemeinde Zuerich-Letzi, juengster Jahrgang — 49 von 62684 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,schulgemeinde,staatsangehoerigkeit,staatsangehoerigkeit_ISO2_Code,anzahl`
- **SHA-256:** `e77d413eacebbf11fdc39a27c2ca8db6132b68e161a2f68646dc0ab07fbe9022`

## `maturitaet.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_maturitaetsquote_gemeinden_und_kanton`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** Gemeinden Zuerich und Winterthur — 24 von 1981 Zeilen
- **Kopfzeile:** `Stand,Stand_Gemeindegrenzen,Bezirk,Gemeinde_BFSCode,Gemeinde,Total_Abschluss_gymnasial,Total_19_Jahre_alt,Maturitaetsquote_gymnasial`
- **SHA-256:** `8521b0c8550872cb90f0821ba9c65de3037822249ec70beed947a76a3b1a8c18`

## `wohnort.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_nach_wohngemeinde`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** Gebiet «Bezirk Winterthur», alle Jahre — 182 von 35903 Zeilen
- **Kopfzeile:** `jahr,gebietstyp_Code,gebietstyp,gebiet_Code,gebiet_Bezeichnung,stufe,anzahl`
- **SHA-256:** `213579f082d1ad610e89b63506e9ade756a6e33551c8fb7cc337e6a917b03bf9`

## `mittelschulen.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_mittelschulen`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** alle Zeilen des juengsten Jahrgangs — 218 von 4717 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,stufe,mittelschultyp,bildungsart,geschlecht,finanzierung,staatsangehoerigkeit,anzahl`
- **SHA-256:** `4b7d017cb52509a14cc41cadf4acb04cb71f831219e931cbb46620d869399243`
