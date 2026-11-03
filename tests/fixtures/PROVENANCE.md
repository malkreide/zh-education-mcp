# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-11-03** von der Live-Quelle `https://www.bista.zh.ch/basicapi/ogd`, unveraendert bis auf die dokumentierte Zeilenauswahl.

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
- **Aufgezeichnet:** 2026-11-03
- **Auswahl:** alle Zeilen zu den Schulgemeinden Zuerich-Letzi und Adliswil — 277 von 13902 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,schulgemeinde,anforderungstyp,anzahl,obs_status`
- **SHA-256:** `0a399a077732595c339a2fc3371e78b237809e76d813156084476314f93e640e`

## `uebersicht.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_uebersicht_alle_lernende`
- **Aufgezeichnet:** 2026-11-03
- **Auswahl:** alle Zeilen des juengsten Jahrgangs — 110 von 3192 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,stufe,schultyp,geschlecht,staatsangehoerigkeit,traegerschaft,finanzierung,anzahl`
- **SHA-256:** `d2a87cea0e27742f57cdbf618b2c0d35b4c49d93708e5727ad4fd6f6fda92380`

## `nat_regional.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_regelschule_regional_staatsangehoerigkeit`
- **Aufgezeichnet:** 2026-11-03
- **Auswahl:** Schultraeger Zuerich-Letzi und Andelfingen, juengster Jahrgang — 65 von 65569 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,schultraeger_code,schultraeger,schultraeger_typ,staatsangehoerigkeit,staatsangehoerigkeit_iso2_code,anzahl,obs_status`
- **SHA-256:** `34149b12aa92eb238833d06ef31897c21e6745fe8a00212bdc61acbecf8bd4d9`

## `maturitaet.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_maturitaetsquote_gemeinden_und_kanton`
- **Aufgezeichnet:** 2026-11-03
- **Auswahl:** Gemeinden Zuerich und Winterthur — 24 von 1981 Zeilen
- **Kopfzeile:** `Stand,Stand_Gemeindegrenzen,Bezirk,Gemeinde_BFSCode,Gemeinde,Total_Abschluss_gymnasial,Total_19_Jahre_alt,Maturitaetsquote_gymnasial`
- **SHA-256:** `06809be38c2b84519275ce20d7a64026d3ad5638b5ee12a9626ead5d721c0ab7`

## `wohnort.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_nach_wohngemeinde`
- **Aufgezeichnet:** 2026-11-03
- **Auswahl:** Gebiet «Bezirk Winterthur», alle Jahre — 182 von 35903 Zeilen
- **Kopfzeile:** `jahr,gebietstyp_Code,gebietstyp,gebiet_code,gebiet_bezeichnung,stufe,anzahl`
- **SHA-256:** `4e3b61f3b03c4a5b60014a14fc98f62d832865c6dfe4bc79ac80322eadc93c7d`

## `mittelschulen.csv`

- **Endpunkt:** `https://www.bista.zh.ch/basicapi/ogd/data_lernende_mittelschulen`
- **Aufgezeichnet:** 2026-11-03
- **Auswahl:** alle Zeilen des juengsten Jahrgangs — 217 von 4717 Zeilen
- **Kopfzeile:** `stand,kanton,jahr,stufe,mittelschultyp,bildungsart,geschlecht,finanzierung,staatsangehoerigkeit,anzahl`
- **SHA-256:** `bf2d0b792d6d4e80aa69783877736ab65b9f09b75b9f34a1dc01dd976f91fd99`
