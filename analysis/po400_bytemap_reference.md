# Pulox PO-400 / Contec USB-HID Protokoll-Spezifikation
## Vollständige Bytemap-Dekodierung für alle Nachrichten (Host Request & Device Response)

Dieses Dokument enthält die vollständige, bit- und bytegenaue Spezifikation aller Befehle und Antworten des Pulox PO-400 (`VID_28E9&PID_028A`), reversiert aus `SpO2.exe` (Version 2.0) und verifiziert an echten USB-PCAP-Mitschnitten.

> **Maßgeblich ist `PROTOCOL.md`.** Diese deutsche Fassung wurde am 2026-10-16 gegen
> `analysis/bum400_20260906_100516.pcap` (Hersteller-Software) und `tests/fixtures/*.trace.json`
> (`fiedle400` am echten Gerät) abgeglichen; die Korrekturen in §§1-13 entsprechen denen in
> `PROTOCOL.md`. Der Abschnitt zum manuellen Aufnahme-Protokoll ist bewusst **unverändert**
> geblieben; seine offenen Abweichungen zu `PROTOCOL.md` §3.14 stehen in
> `handoff/docs-review-response.md`.

---

## 1. Grundlegende Protokollregeln

1. **7-Bit-Nutzdaten-Restriktion:**
   Aus Gründen der Abwärtskompatibilität zu 7-Bit-seriellen UART-Schnittstellen dürfen Datenbytes innerhalb von Nutzdatenfeldern niemals das höchste Bit (`Bit 7`) gesetzt haben (Wertebereich `0x00` bis `0x7F` bzw. 0..127).
2. **Prüfsummenberechnung (Checksum):**
   Für alle Request- und Subframe-Pakete gilt ausnahmslos die 7-Bit-Summenprüfsumme:
   $$\text{Checksum} = \left( \sum_{i=0}^{N-1} \text{Byte}[i] \right) \bmod 128$$
3. **14-Bit Integer-Packing (Little-Endian 7-Bit):**
   $$\text{Value}_{14} = (\text{Byte}_{\text{high}} \ll 7) \mid \text{Byte}_{\text{low}}$$
4. **28-Bit Integer-Packing (Rohwert-Zähler im `0xEC`-Header):**
   $$\text{Value}_{28} = B_0 \mid (B_1 \ll 7) \mid (B_2 \ll 14) \mid (B_3 \ll 21)$$
   Zählt **Rohwerte mit 2 Hz**, nicht Sekunden. Datensätze (= Sekunden) = `(Value_28 + 1) // 2`
   (243 Rohwerte -> 122 Datensätze im Hersteller-Mitschnitt).
5. **Zwei Request-Formen:** Die Hersteller-Software sendet Befehle "nackt" (`9C 01 1D`, Null-Padding),
   `fiedle400` meist als `7D 81 <Opcode> <Args>` mit `0x80`-Padding. Das Gerät beantwortet beide gleich.
6. **Antworten sind Frames eigener Länge** und enden jeweils mit ihrer Prüfsumme (siehe `PROTOCOL.md` §2.2).

---

## 2. Opcode & Hardware Response Registry (Übersicht)

| Opcode | Name | Host Request (Hex) | Response Opcode | Bedeutung |
| :---: | :--- | :--- | :---: | :--- |
| **0xA7 + 0xA2** | `UNLOCK_HANDSHAKE` | `7D 81 A7 80...` & `7D 81 A2 80...` | `0xF0` | MCU State Machine entsperren (ACK `F0 70`) |
| **0x9C [0x80]** | `SESSION_RESET` | `7D 81 9C 80 00` | `0xF0` | Session-Iterator zurücksetzen (nur `fiedle400`; die Hersteller-Software sendet es nie) |
| **0x9C [0x01]** | `QUERY_SESSIONS` | `9C 01 1D` | `0xEC` | Session-Metadaten / Header für User 1 abfragen |
| **0x82** | `READ_RTC` | `82 02` (oder `7D 81 82 80...`) | `0xF2` | Geräte-Uhrzeit auslesen (YY/MM/DD HH:MM:SS) |
| **0x83** | `SET_RTC` | `83 YY MM DD HH MM SS 33 06 [chk]` | `F3 00 73` | Echtzeituhr im Oximeter setzen (Hersteller-Mitschnitt) |
| **0x9B [0x00]** | `DATA_STREAM_QUERY` | `9B 00 1B` (Start) / `9B 7F 1A` (Stop) | `0xEB` | Live-Datenstrom öffnen / schließen |
| **0x9D [0x02]** | `STORAGE_INIT` | `9D 02 7F 7F 7F 00 00 1C` | keine | Vor dem Download gesendet; in keinem Mitschnitt beantwortet |
| **0x9D [0x04 0x01]** | `READ_SPO2_BLOCK` | `9D 04 01 01 01 00 00 00 24` | `0xED` | SpO2-Messreihe (Block 1) anfordern |
| **0x9D [0x04 0x02]** | `READ_PULSE_BLOCK` | `9D 04 02 01 01 00 00 00 25` | `0xED` | Pulsfrequenz-Messreihe (Block 2) anfordern |
| **0x9D [0x02]** | `SEGMENT_ACK` | `9D 02 7F 7F 7F 00 00 1C` | keine | Nach dem Download gesendet; keine Antwort |
| **0x9D [0x7F]** | `STORAGE_FINALIZE` | `9D 7F 7F 7F 7F 00 00 19` | nicht zugeordnet | Hersteller-Software, dreimal nach dem Download |
| **0x81** | `QUERY_DEVICE_INFO`| `81 01` | `0xF1` | Hardware-Kennung ("50F", CMS50F / PO-400). `0xAD` erhält nur `F0 70` |
| **0x80** | `FIRMWARE_QUERY` | `80 00` | `F0 70` | Nur ACK auf diesem Gerät; die `0xCF`-Antwort stammt allein aus der Disassembly |
| **0x8E [0x03]** | `SERIAL_PROFILE_QUERY` | `8E 03 11` (User), `8E 06 14`, `8E 07 15` | `0xFE` | Benutzerprofil ("user") & Seriennummer |
| **0x9F** | `FLASH_GEOMETRY_QUERY` | `9F 1F` | `0xEF` | Flash-Speichergeometrie (Feldbedeutung unbestätigt) |
| **0x8F** | (unbekannt) | `8F 04 00 13` | `FF 00 7F` | Früher als Geometrie-Abfrage geführt; das Gerät antwortet mit einem `0xFF`-Frame |
| **0x9E** | (Geometrie-Variante) | `7D 81 9E 40 04` | `F0 70` | Was `fiedle400 info` heute sendet; nur ACK |
| **0x90 [0x06]** | `USER_METADATA_QUERY` | `90 06 16` | `0xE0` | Alarmgrenzen (SpO2 High/Low, PR High/Low) |
| **0x94** | `FLASH_SECTOR_QUERY`| `94 14` / `7D 81 94 ...` | `0xD4` / `0x94` | Flash-Sektor-Layout-Parameter (in keinem Mitschnitt) |
| **0xA5** | `SESSION_SELECT` | `7D 81 A5 [id] [chk]` | keine | Varianten-Geräte; dieses Gerät antwortet nicht |
| **0xA6** | `SESSION_DOWNLOAD` | `7D 81 A6 [chk]` | keine | Varianten-Geräte; dieses Gerät antwortet nicht |
| **0x9A** | (unbekannt) | `9A 1A` | nicht zugeordnet | Letzter Befehl des Hersteller-Downloads |
| **0xAA / 0x91** | `FLASH_CLEAR` | `7D 81 AA ...` bzw. `91 01 12` | `0xF0` | Flash löschen / User 1 löschen (Gefahr!) |
| **0xA0** | `MANUAL_HEADER_QUERY` | `A0 00 20` | `0xD0` | Header der manuellen Aufnahme (Datum/Zeit/Dauer) |
| **0xA3** | `MANUAL_READ_SPO2` | `A3 00 00 00 23` | `0xD3` | SpO2-Messreihe der manuellen Aufnahme |
| **0xA2** | `MANUAL_READ_PULSE` | `A2 00 00 00 22` | `0xD2` | Pulsfrequenz-Messreihe der manuellen Aufnahme (Opcode-Doppelnutzung, siehe 3.14) |
| **0xA7 [0x00/0x01]** | `MANUAL_BLOCK_ACK` | `A7 00 27` (Puls) / `A7 01 28` (SpO2) | `0xD8` | Block-Quittung für manuellen Download |

---

## 3. Detaillierte Bytemaps für jede Nachricht

---

### 1. UNLOCK_HANDSHAKE (`0xA7` + `0xA2`)

#### A. Host Request: ein kombinierter 64-Byte-Report (`0xA7` + `0xA2`)
*Wird über den Protocol 0 Dispatcher (`0x004915c5`) gesendet.* Korrigiert 2026-10-16: **ein** Report,
keine Prüfsummen, Rest mit `0x80` aufgefüllt (so im Hersteller-Mitschnitt und in `fiedle400`;
frühere Fassungen nannten zwei Reports mit Prüfsummen `0x20`/`0x1B`, die nirgends auftauchen).

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Sync Prefix | `0x7D` | Protokoll 0 Synchronisationsbyte |
| `0x01` | 1 Byte | Channel ID | `0x81` | Kanal-ID / Geräte-Target |
| `0x02` | 1 Byte | Opcode | `0xA7` | Unlock Phase 1 Befehl |
| `0x03..0x08` | 6 Bytes | Key / Padding | `0x80` × 6 | Fester Handshake-Schlüssel / Padding |
| `0x09` | 1 Byte | Sync Prefix | `0x7D` | Phase 2 folgt direkt, ohne Prüfsumme dazwischen |
| `0x0A` | 1 Byte | Channel ID | `0x81` | |
| `0x0B` | 1 Byte | Opcode | `0xA2` | Unlock Phase 2 |
| `0x0C..0x3F` | 52 Bytes | Padding | `0x80` | Report-Auffüllung |

#### C. Hardware Response: ACK (`0xF0`)
*Empfangen an Adresse `0x004c5e6f`.*

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xF0` | Bestätigungs-Report (ACK) |
| `0x01` | 1 Byte | Status | `0x70` | `0x70` = Erfolg / MCU entsperrt (`0x004c5e75`) |
| `0x02..0x3F` | 62 Bytes | Padding | `0x00...` | HID-Report Auffüllbytes |

---

### 2. SESSION_RESET & QUERY_SESSIONS (`0x9C`)

#### A. Host Request: SESSION_RESET (Iterator auf Slot 0 zurücksetzen)

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x9C` | Session-Befehl |
| `0x01` | 1 Byte | Sub-Command | `0x80` | `0x80` = Reset Iterator auf Anfang |
| `0x02` | 1 Byte | Checksum | `0x1C` | `(0x9C + 0x80) mod 128 = 0x1C` |

#### B. Host Request: QUERY_SESSIONS (Header für Slot anfordern)

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x9C` | Session-Befehl |
| `0x01` | 1 Byte | User / Slot-ID | `0x01` | User 1 (Slot 1) |
| `0x02` | 1 Byte | Checksum | `0x1D` | `(0x9C + 0x01) mod 128 = 0x1D` |

#### C. Hardware Response: Session Header (`0xEC`, 21 Bytes)
*Empfangen an Adresse `0x004c587a`.*

| Offset | Länge | Feldname | Wert / Format | Bedeutung & Dekodierung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Header-Opcode | `0xEC` | Kennung für Session-Metadaten / Segment-Header |
| `0x01` | 1 Byte | Status & Flags | `0x40` | **Bit 6 (`0x40`):** `Session Valid / Data Ready` (1 = Daten vorhanden)<br>**Bits 0..3 (`0x0F`):** User-ID / Speicher-Slot *(Keine Paketlänge!)* |
| `0x02` | 1 Byte | Total Segments | `0x01` | Gesamtanzahl gespeicherter Segmente (`[this + 0x1e8]`); `fiedle400` liest das Byte als User-ID |
| `0x03` | 1 Byte | Segment Index | `0x01` | Aktuelle Segment-Nummer (1-basiert, `[this + 0x1ec]`); `fiedle400` liest es als Session-ID. Alle Mitschnitte zeigen `01 01`, keine Lesart ist bestätigt |
| `0x04` | 1 Byte | Year (YY) | `0x1A` (26) | Jahr seit 2000 (`2000 + 26 = 2026`) |
| `0x05` | 1 Byte | Month (MM) | `0x09` (9) | Monat (1..12) -> September |
| `0x06` | 1 Byte | Day (DD) | `0x06` (6) | Tag im Monat (1..31) -> 6. |
| `0x07` | 1 Byte | Hour (HH) | `0x0A` (10) | Stunde (0..23) -> 10 Uhr |
| `0x08` | 1 Byte | Minute (MM) | `0x00` (0) | Minute (0..59) -> 00 min |
| `0x09` | 1 Byte | Second (SS) | `0x2E` (46) | Sekunde (0..59) -> 46 s |
| `0x0A..0x0D` | 4 Bytes | Sample Count | `0x73 0x01 0x00 0x00` | **28-Bit Packed Little-Endian Integer (7-Bit Chunks):**<br>`Samples = B0 \| (B1<<7) \| (B2<<14) \| (B3<<21)`<br>`115 + (1 << 7) = 243 Rohwerte` (bei 2 Hz = 122 Sekunden, `(243 + 1) // 2`) |
| `0x0E..0x13` | 6 Bytes | Username | `"user"` + `00 00` | In allen Mitschnitten gleich |
| `0x14` | 1 Byte | Checksum | `0x42` | `(sum(Byte[0..0x13])) mod 128` |
| `0x15..0x3F` | 43 Bytes | Padding | `0x00...` | Null-Padding |

Korrigiert 2026-10-16: früher als 64-Byte-Frame mit 16-Byte-Benutzername geführt. Der echte Frame
ist 21 Bytes lang: `EC 40 01 01 1A 09 06 0A 00 2E 73 01 00 00 75 73 65 72 00 00 42`.

---

### 3. READ_RTC (`0x82`) & SET_RTC (`0x83`)

#### A. Host Request: READ_RTC (`0x82`)

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x82` | Echtzeituhr auslesen |
| `0x01` | 1 Byte | Checksum | `0x02` | `0x82 mod 128 = 0x02` |

#### B. Host Request: SET_RTC (`0x83`)
*Erzeugt in `SpO2.exe` @ `0x0049bbb8` via `GetLocalTime`.*

| Offset | Länge | Feldname | Wert / Bereich | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x83` | Echtzeituhr synchronisieren |
| `0x01` | 1 Byte | Year | `0x00..0x7F` | Jahr seit 2000 (z. B. `0x1A` = 26 -> 2026) |
| `0x02` | 1 Byte | Month | `0x01..0x0C` | Monat (1..12) |
| `0x03` | 1 Byte | Day | `0x01..0x1F` | Tag im Monat (1..31) |
| `0x04` | 1 Byte | Hour | `0x00..0x17` | Stunde (0..23) |
| `0x05` | 1 Byte | Minute | `0x00..0x3B` | Minute (0..59) |
| `0x06` | 1 Byte | Second | `0x00..0x3B` | Sekunde (0..59) |
| `0x07` | 1 Byte | Subsecond/Flags | `0x33` | Interne Timing-Flags |
| `0x08` | 1 Byte | Reserved | `0x06` | Fester Parameter |
| `0x09` | 1 Byte | Checksum | `0x00..0x7F` | `(sum(Byte[0..8])) mod 128` |

#### C. Hardware Response: RTC-Report (`0xF2`, 8 Bytes)
*Verarbeitet in `SpO2.exe` @ `0x004c670b`.*

| Offset | Länge | Feldname | Format / Werte | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xF2` | RTC-Antwortkennung |
| `0x01` | 1 Byte | Year | `0x00..0x7F` | Jahr seit 2000 (YY) |
| `0x02` | 1 Byte | Month | `0x01..0x0C` | Monat (1..12) |
| `0x03` | 1 Byte | Day | `0x01..0x1F` | Tag (1..31) |
| `0x04` | 1 Byte | Hour | `0x00..0x17` | Stunde (0..23) |
| `0x05` | 1 Byte | Minute | `0x00..0x3B` | Minute (0..59) |
| `0x06` | 1 Byte | Second | `0x00..0x3B` | Sekunde (0..59) |
| `0x07` | 1 Byte | Checksum | `0x00..0x7F` | `(sum(Byte[0..6])) mod 128` |

> **Die `0xF2`-Antwort enthält auf diesem Gerät keine aktuelle Uhrzeit.** Sie lautet in jedem
> Mitschnitt gleich `F2 00 00 02 07 00 0C 07` (Hersteller-Mitschnitt vom 2026-09-06, vor und nach
> einem mit `F3 00 73` quittierten `SET_RTC`; `fiedle400`-Mitschnitte vom 2026-10-15). Die Feldtabelle
> oben ist daher unbestätigt. `fiedle400` bis 0.3.6 las ab Byte 3 und erhielt so 2002-07-01 12:07 (die
> Minute war das Prüfsummenbyte); seit 0.3.7 wird die Antwort nicht mehr dekodiert, `read-time` zeigt sie roh. Der Hersteller-`SET_RTC` entspricht genau Tabelle B
> (`83 1A 09 06 0A 05 18 33 06 0C`); `fiedle400 set-time` sendet ein anderes, nicht aufgezeichnetes Layout.

---

### 4. DATA_STREAM_QUERY (`0x9B`) & Live-Streaming (`0xEB`)

#### A. Host Request: DATA_STREAM_QUERY

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x9B` | Live-Stream Steuerung |
| `0x01` | 1 Byte | Control | `0x00` / `0x7F` | `0x00` = Stream Start, `0x7F` = Stream Stop |
| `0x02` | 1 Byte | Checksum | `0x1B` / `0x1A` | `(0x9B + Control) mod 128` |

#### B. Hardware Response: Live Frames (`0xEB`, je 6 Bytes)
*Verarbeitet in `SpO2.exe` @ `0x004c6acf`.*

| Offset | Länge | Feldname | Format / Werte | Bedeutung & Bitfield |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Sync Opcode | `0xEB` | Live-Frame Kennung |
| `0x01` | 1 Byte | Status & Quality | Bitfield `0x00..0x7F` | **Bit 0:** Finger-Out / Probe-Drop (1 = Finger draußen, 0 = OK)<br>**Bits 1..3:** Puls-Signalstärke (0..8 Balken)<br>**Bit 4:** Beat-Trigger (1 = Herzschlag erkannt) |
| `0x02` | 1 Byte | Plethysmogramm | `0x00..0x7F` | Live-Pulswellen-Amplitude für Kurvengraph |
| `0x03` | 1 Byte | Pulse Rate | `0x00..0xFE` | Pulsfrequenz in bpm (`0xFF` = Ungültig / Kein Puls) |
| `0x04` | 1 Byte | SpO2 | `0x00..0x64` | Sauerstoffsättigung in % (`0x7F` = Ungültig / Finger-Out) |
| `0x05` | 1 Byte | Checksum | `0x00..0x7F` | `(sum(Byte[0..4])) mod 128` |

> **Vom einzigen Live-Mitschnitt nicht bestätigt.** Der Hersteller-Mitschnitt (ohne Finger) enthält
> drei Frame-Formen mit jeweils gültiger Prüfsumme am Ende: `EB 00 04 40 30 5F` (6 Bytes),
> `EB 01 06 7F 7F 7F 00 6F` (8 Bytes) und `EB 7F 6A` (3 Bytes, Antwort auf `9B 7F 1A`). Die Länge
> hängt an Byte 1, das damit eher ein Frame-Typ als ein Status-Bitfeld ist (so behandelt es auch
> `parsers.parse_hid_chunks`). Klärung braucht einen Mitschnitt mit Finger.

---

### 5. STORAGE_INIT, BLOCK READ (`0x9D`) & Subframes (`0xED`)

#### A. Host Request: STORAGE_INIT / SEGMENT_ACK (`0x9D 0x02`)
*Erzeugt in `SpO2.exe` @ `0x0049bc60`.*

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x9D` | Speicher-Befehl |
| `0x01` | 1 Byte | Mode | `0x02` | Buffer Init / Segment-Quittierung |
| `0x02` | 1 Byte | Type Wildcard | `0x7F` | Alle Typen |
| `0x03` | 1 Byte | User Wildcard | `0x7F` | Alle Benutzer |
| `0x04` | 1 Byte | Seg Wildcard | `0x7F` | Alle Segmente |
| `0x05` | 1 Byte | Offset Low | `0x00` | Start bei Subframe 0 |
| `0x06` | 1 Byte | Offset High | `0x00` | Start-Offset High-Byte |
| `0x07` | 1 Byte | Checksum | `0x1C` | `(sum(Byte[0..6])) mod 128 = 0x1C` |

So (8 Bytes) im Hersteller-Mitschnitt. `fiedle400` sendet eine 9-Byte-Variante mit zusätzlichem
`0x00` vor der Prüfsumme. Keine der beiden wird beantwortet; der Download funktioniert danach mit beiden.

#### B. Host Request: READ_SPO2_BLOCK (`0x9D 0x04 0x01`)

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x9D` | Speicher-Befehl |
| `0x01` | 1 Byte | Mode | `0x04` | Block-Lesemodus |
| `0x02` | 1 Byte | Data Type | `0x01` | **0x01 = SpO2-Messreihe** |
| `0x03` | 1 Byte | User ID | `0x01` | User 1 |
| `0x04` | 1 Byte | Segment ID | `0x01` | Segment 1 |
| `0x05` | 1 Byte | Offset Low | `0x00` | Start-Offset in Rohwerten, Bits 0..6 |
| `0x06` | 1 Byte | Offset High | `0x00` | Start-Offset in Rohwerten, Bits 7..13 |
| `0x07` | 1 Byte | Reserved | `0x00` | Null-Byte |
| `0x08` | 1 Byte | Checksum | `0x24` | `(sum(Byte[0..7])) mod 128 = 0x24` |

#### C. Host Request: READ_PULSE_BLOCK (`0x9D 0x04 0x02`)

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x9D` | Speicher-Befehl |
| `0x01` | 1 Byte | Mode | `0x04` | Block-Lesemodus |
| `0x02` | 1 Byte | Data Type | `0x02` | **0x02 = Pulsfrequenz-Messreihe** |
| `0x03` | 1 Byte | User ID | `0x01` | User 1 |
| `0x04` | 1 Byte | Segment ID | `0x01` | Segment 1 |
| `0x05` | 1 Byte | Offset Low | `0x00` | Start-Offset in Rohwerten, Bits 0..6 |
| `0x06` | 1 Byte | Offset High | `0x00` | Start-Offset in Rohwerten, Bits 7..13 |
| `0x07` | 1 Byte | Reserved | `0x00` | Null-Byte |
| `0x08` | 1 Byte | Checksum | `0x25` | `(sum(Byte[0..7])) mod 128 = 0x25` |

#### D. Hardware Response: Stored Data Subframes (`0xED`, 30 Bytes)
*Verarbeitet in `SpO2.exe` @ `0x004c4fa7` & `0x004c5a79`.*

| Offset | Länge | Feldname | Format / Werte | Bedeutung & Dekodierung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xED` | Synchronisations-Opcode für Speicher-Subframes |
| `0x01` | 1 Byte | Mode | `0x04` | Protokoll-Modus (Modus 4 = Flash-Block-Download) |
| `0x02` | 1 Byte | Data Type | `0x01` / `0x02` | `0x01` = SpO2-Messreihe, `0x02` = Pulsfrequenz-Messreihe |
| `0x03..0x04` | 2 Bytes | Sequence Index | `0x00..0x7F` (je Byte) | **14-Bit Subframe-Zähler (Little-Endian 7-Bit):**<br>`SubframeIndex = (Byte[4] << 7) \| Byte[3]`<br>Byte 3: Zähler Bits 0..6 (0..127)<br>Byte 4: Zähler Bits 7..13 (Übertrag nach 128 Subframes) |
| `0x05` | 1 Byte | MSB Mask 1 | Bitmaske `0x00..0x7F` | Stellt Bit 7 für Datenbytes `0x08..0x0E` (Bytes 8..14) wieder her |
| `0x06` | 1 Byte | MSB Mask 2 | Bitmaske `0x00..0x7F` | Stellt Bit 7 für Datenbytes `0x0F..0x15` (Bytes 15..21) wieder her |
| `0x07` | 1 Byte | MSB Mask 3 | Bitmaske `0x00..0x7F` | Stellt Bit 7 für Datenbytes `0x16..0x1C` (Bytes 22..28) wieder her |
| `0x08..0x1C` | 21 Bytes | Compressed Data | 42 Nibbles (4-Bit) | **Delta-komprimierte Messwerte (2 Halbmesspunkte / Byte):**<br>• `0xF_ 0xF_`: Basiswert-Initialisierung `((B1 & 0xF) << 4) \| (B2 & 0xF)`<br>• `0xFF 0xFF`: Stream Terminator (`遇到无效包，结束`)<br>• High-Nibble: `Wert = Base - (B >> 4)`<br>• Low-Nibble: `Wert = Base - (B & 0x0F)` *(0x0F = Padding)* |
| `0x1D` | 1 Byte | Checksum | `0x00..0x7F` | **7-Bit-Summenprüfsumme:**<br>`Checksum = (sum(Byte[0..28])) mod 128` |

**Ergänzungen 2026-10-16 (siehe `PROTOCOL.md` §3.5):**
- Der Offset in Byte 5/6 der Leseanfrage zählt **Rohwerte**, keine Blöcke: Offset `k` liefert die
  Daten ab Rohwert `k` bis zum Ende der gespeicherten Reihe. Bei Offset = Anzahl gespeicherter
  Rohwerte kommt ein End-Frame `ED 04 01 00 00 7B 7F 7F 7F 7F 0F 7F ...` (Terminator `0xFF 0xFF`),
  darüber hinaus nichts (`tests/fixtures/probe.trace.json`).
- Die Maskenbytes des letzten Frames einer Antwort haben für jedes Füllbyte ein Bit gesetzt
  (`70 7F 7F`, `78 7F 7F`, im Hersteller-Mitschnitt `00 00 60`); Byte 7 ist Maske `m2`, kein Status.
- Finger-Out im Speicherstrom ist in keinem Mitschnitt belegt. `0x7F`/`0xFF` sind die Werte, die
  `SpO2.exe` bei unplausiblen *dekodierten* Werten in seine eigenen Datensätze schreibt.

---

### 6. QUERY_DEVICE_INFO (`0x81` / `0xAD`) & Response (`0xF1`)

#### A. Host Request: QUERY_DEVICE_INFO

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x81` | Geräte-Info anfordern |
| `0x01` | 1 Byte | Checksum | `0x01` | `0x81 mod 128 = 0x01` |

`0xAD` erhält auf diesem Gerät nur `F0 70`.

#### B. Hardware Response: Device Info (`0xF1`, 10 Bytes)
*Verarbeitet in `SpO2.exe` @ `0x004c7281`.*

| Offset | Länge | Feldname | Wert / Format | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xF1` | Geräte-Info Kennung |
| `0x01..0x08` | 8 Bytes | Device String | ASCII `"50F     "` | Modellbezeichnung (z. B. CMS50F / PO-400) |
| `0x09` | 1 Byte | Checksum | `0x3C` | `(sum(Byte[0..8])) mod 128` |

---

### 7. FIRMWARE_QUERY (`0x80` / `0x81`) & Response (`0xCF` / `0x81`)

#### A. Host Request: FIRMWARE_QUERY

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x80` | Firmware-Version anfordern |
| `0x01` | 1 Byte | Checksum | `0x00` | `0x80 mod 128 = 0x00` |

#### B. Hardware Response: Firmware Version (`0xCF`, 10 Bytes)
*Verarbeitet in `SpO2.exe` @ `0x004c54bb`.*

| Offset | Länge | Feldname | Wert / Format | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xCF` | Firmware-Versions-Kennung |
| `0x01..0x08` | 8 Bytes | Version String | ASCII `"V3.1    "` | Versionsbezeichnung der Firmware |
| `0x09` | 1 Byte | Checksum | `0x00..0x7F` | `(sum(Byte[0..8])) mod 128` |

**Nie beobachtet:** Das Gerät beantwortet `80 00` nur mit `F0 70` (dreimal im Hersteller-Mitschnitt,
einmal in `tests/fixtures/probe.trace.json`). Tabelle B stammt allein aus der Disassembly.

---

### 8. SERIAL_PROFILE_QUERY (`0x8E`) & Response (`0xFE`)

#### A. Host Request: SERIAL_PROFILE_QUERY

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x8E` | Profil- und Seriennummernabfrage |
| `0x01` | 1 Byte | Sub-Index | `0x03` / `0x06` / `0x07` | `0x03` = Benutzername, `0x06` = Profil, `0x07` = Seriennummer |
| `0x02` | 1 Byte | Checksum | `0x11` / `0x14` / `0x15` | `(0x8E + Sub-Index) mod 128` |

#### B. Hardware Response: Profile/User String (`0xFE`, 11 Bytes)
*Verarbeitet in `SpO2.exe` @ `0x004c5c95`.*

| Offset | Länge | Feldname | Wert / Format | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xFE` | Profil-Antwortkennung |
| `0x01` | 1 Byte | Sub-Index Echo | `0x03` / `0x07` | Bestätigter Parameter-Index |
| `0x02..0x09` | 8 Bytes | Data String | ASCII `"   user "` | Benutzername bzw. Seriennummer |
| `0x0A` | 1 Byte | Checksum | `0x00..0x7F` | `(sum(Byte[0..9])) mod 128` |

**Korrektur nach Mitschnitt:** Die Länge hängt vom Sub-Index ab. `8E 03` -> `FE 03 20 20 20 75 73 65 72 20`
(10 Bytes: 7 Zeichen `"   user"`, Prüfsumme `0x20` an `0x09`); `8E 06` -> `FE 06 07 00 00 00 0B` (7 Bytes,
Bedeutung unbekannt); `8E 07` -> `FE 07 00 00 05` (5 Bytes, **keine** Seriennummer). Die Tabelle oben passt
zu keiner aufgezeichneten Antwort.

---

### 9. FLASH_GEOMETRY_QUERY (`0x8F` / `0x9F`) & Response (`0xEF`)

#### A. Host Request: FLASH_GEOMETRY_QUERY

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x9F` | Speicher-Topologie anfordern |
| `0x01` | 1 Byte | Checksum | `0x1F` | `0x9F mod 128 = 0x1F` |

Korrigiert 2026-10-16: Die `0xEF`-Antwort folgt auf `9F 1F`. Das früher hier genannte `8F 04 00 13`
beantwortet das Gerät mit `FF 00 7F`.

#### B. Hardware Response: Flash Geometry (`0xEF`, 8 Bytes)
*Verarbeitet in `SpO2.exe` @ `0x004c5e8e`.*

| Offset | Länge | Feldname | Wert / Format | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xEF` | Flash-Geometrie Kennung |
| `0x01` | 1 Byte | Sector Count | `0x00..0x7F` | Anzahl verfügbarer Sektoren |
| `0x02..0x03` | 2 Bytes | Block Size | `0x01 0x40` | Blockgröße (7-Bit Packed: 64 oder 256 Bytes) |
| `0x04..0x06` | 3 Bytes | Total Capacity | `0x00..0x7F` | Gesamte Speicherkapazität |
| `0x07` | 1 Byte | Checksum | `0x30` | `(sum(Byte[0..6])) mod 128` |

Einzige aufgezeichnete Antwort: `EF 00 01 40 00 00 00 30`. Die Feldbedeutungen sind unbestätigt.

---

### 10. FLASH_SECTOR_QUERY (`0x94`) & Response (`0xD4`)

#### A. Host Request: FLASH_SECTOR_QUERY

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x94` | Flash-Sektor-Layout abfragen |
| `0x01` | 1 Byte | Checksum | `0x14` | `0x94 mod 128 = 0x14` |

In keinem Mitschnitt; nur aus der Disassembly.

#### B. Hardware Response: Flash Sector Layout (`0xD4`, 18 Bytes)
*Verarbeitet in `SpO2.exe` (Länge 18 Bytes laut Global Table).*

| Offset | Länge | Feldname | Format / Werte | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xD4` | Sektor-Layout Kennung |
| `0x01` | 1 Byte | Total Blocks | `0x00..0x7F` | Anzahl Flash-Blöcke |
| `0x02..0x03` | 2 Bytes | Block Pages | `0x00..0x7F` | Seiten pro Block |
| `0x04..0x10` | 13 Bytes | Sector Map | `0x00..0x7F` | Bitmaske / Belegungsstatus der Sektoren |
| `0x11` | 1 Byte | Checksum | `0x00..0x7F` | `(sum(Byte[0..16])) mod 128` |

---

### 11. USER_METADATA_QUERY (`0x90`) & Response (`0xE0`)

#### A. Host Request: USER_METADATA_QUERY

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x90` | Benutzer-Alarmparameter anfordern |
| `0x01` | 1 Byte | Sub-Index | `0x06` | Index 6 = Alarm-Schwellenwerte |
| `0x02` | 1 Byte | Checksum | `0x16` | `(0x90 + 0x06) mod 128 = 0x16` |

#### B. Hardware Response: User Alarm Limits (`0xE0`, 7 Bytes)
*Verarbeitet in `SpO2.exe` @ `0x004c56f2`.*

| Offset | Länge | Feldname | Format / Werte | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xE0` | Alarmgrenzen Kennung |
| `0x01` | 1 Byte | Sub-Index Echo | `0x06` | Bestätigter Sub-Index |
| `0x02` | 1 Byte | SpO2 Low Limit | `0x00..0x64` | Untere SpO2-Alarmschwelle in % (z. B. 85%) |
| `0x03` | 1 Byte | SpO2 High Limit | `0x00..0x64` | Obere SpO2-Alarmschwelle in % (z. B. 100%) |
| `0x04` | 1 Byte | PR Low Limit | `0x00..0xFE` | Untere Puls-Alarmschwelle in bpm (z. B. 50 bpm) |
| `0x05` | 1 Byte | PR High Limit | `0x00..0xFE` | Obere Puls-Alarmschwelle in bpm (z. B. 120 bpm) |
| `0x06` | 1 Byte | Checksum | `0x00..0x7F` | `(sum(Byte[0..5])) mod 128` |

Die aufgezeichnete Antwort ist 15 Bytes lang (Prüfsumme an `0x0E`):
`E0 06 01 00 01 00 00 52 1F 00 1A 4E 1F 00 60`. `01 00 01 00` sind keine plausiblen Alarmgrenzen; die
Tabelle ist unbestätigt.

---

### 12. SESSION_SELECT (`0xA5`) & SESSION_DOWNLOAD (`0xA6`)

#### A. Host Request: SESSION_SELECT (`0xA5`)
*Verwendet auf Serial-Stream-Geräten zur Index-Direktanwahl.*

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Sync Prefix | `0x7D` | Protokoll 0 Prefix |
| `0x01` | 1 Byte | Channel ID | `0x81` | Kanal-Target |
| `0x02` | 1 Byte | Opcode | `0xA5` | Session-Auswahlbefehl |
| `0x03` | 1 Byte | Session Slot | `0x01..0x04` | Ziel-Session Index |
| `0x04` | 1 Byte | Checksum | `0x00..0x7F` | `(sum(Byte[0..3])) mod 128` |

#### B. Host Request: SESSION_DOWNLOAD (`0xA6`)

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Sync Prefix | `0x7D` | Protokoll 0 Prefix |
| `0x01` | 1 Byte | Channel ID | `0x81` | Kanal-Target |
| `0x02` | 1 Byte | Opcode | `0xA6` | Stream-Start für Session |
| `0x03` | 1 Byte | Param | `0x00` | Modus-Parameter |
| `0x04` | 1 Byte | Checksum | `0x00..0x7F` | `(sum(Byte[0..3])) mod 128` |

#### C. Hardware Response: ACK (`0xF0`) bzw. Stream (`0xEB`)
*Antwortet mit Bestätigung `0xF0 0x70` oder startet kontinuierlichen Datenstrom.*

Auf diesem (Flash-Speicher-)PO-400 für Session 1-3 getestet: keine Antwort, nicht einmal ein ACK
(`CHANGELOG.md`, "Manual-mode protocol").

---

### 13. FLASH_CLEAR (`0xAA` & `0x91`..`0x96`)

#### A. Host Request: FLASH_CLEAR (Gesamtes Gerät löschen - GEFAHR!)
*Wird von unmodifizierter `SpO2.exe` @ `0x0048a354` gesendet (durch unseren Patch neutralisiert).*

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Sync Prefix | `0x7D` | Protokoll 0 Prefix |
| `0x01` | 1 Byte | Channel ID | `0x81` | Kanal-Target |
| `0x02` | 1 Byte | Opcode | `0xAA` | Vollständiger Flash-Löschbefehl |
| `0x03..0x08` | 6 Bytes | Reserved | `0x00 0x00 0x00 0x00 0x00 0x00` | Null-Bytes |
| `0x09` | 1 Byte | Checksum | `0x28` | `(sum(Byte[0..8])) mod 128 = 0x28` |

#### B. Host Request: USER_DELETE (`0x91` bis `0x96`)
*Wird nach dem Download von `SpO2.exe` @ `0x0049baa9` gesendet (durch unseren Hook geblockt).*

| Offset | Länge | Feldname | Wert / Maske | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0x91..0x96` | `0x91` = User 1 löschen, `0x92` = User 2 löschen, etc. |
| `0x01` | 1 Byte | Sub-Param | `0x01` | Löschparameter |
| `0x02` | 1 Byte | Checksum | `0x12..0x17` | `(Opcode + 0x01) mod 128` |

#### C. Hardware Response: ACK (`0xF0`)

| Offset | Länge | Feldname | Format / Werte | Bedeutung |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 1 Byte | Opcode | `0xF0` | Bestätigung |
| `0x01` | 1 Byte | Status | `0x70` | Löschvorgang gestartet / abgeschlossen |

Nichts davon ist aufgezeichnet. `fiedle400 clear` sendet andere Bytes (`0xAF`, dann `0xAB 01 [id]` bzw.
`0xAA 80 80`, `0xAB 80 80`, `0xAC 80 80`, jeweils mit `7D 81`-Präfix), die weder dokumentiert noch
aufgezeichnet sind. Das Umschalten zwischen Auto- und Manual-Modus am Gerät löscht ebenfalls den Speicher.

---

### Manuelles Aufnahme-Protokoll (`0xA0`/`0xD0`, `0xA2`/`0xD2`, `0xA3`/`0xD3`, `0xA7`/`0xD8`)

**Gefunden am 15.10.2026** durch einen Live-USB-Mitschnitt von SpO2 Assistant
beim Lesen einer **Manual-Mode**-Aufnahme, abgeglichen mit der Disassembly
(`SpO2.exe` @ `0x004c4875` für die Delta-Dekodierung). Dies ist ein
**eigenständiges, paralleles** Protokoll zu den `0x9C`/`0x9D`-Flash-Index-
Befehlen, die überall sonst in diesem Dokument nur **Auto-Mode**-Sessions
lesen -- das ist die Erklärung, warum `fiedle400` bisherige Manual-Mode-
Aufnahmen nie finden konnte: sie waren über `0x9C`/`0x9D` grundsätzlich nicht
erreichbar, kein Bug und kein fehlendes Argument. **Noch nicht implementiert**
in diesem Projekt.

**Opcode `0xA2` wird doppelt genutzt:** Der UNLOCK_HANDSHAKE (oben) sendet
`0xA2` bereits als zweite Hälfte der `0xA7`-dann-`0xA2`-Präambel. Die Anfrage
unten ist ein eigenständiges `A2 00 00 00 22` mit völlig anderer Bedeutung
(Puls-Daten). Unterscheidung über den Kontext, nicht über das Opcode-Byte
allein.

#### A. Header der manuellen Aufnahme (`0xA0` -> `0xD0`)

Anfrage: `A0 00 20`.

| Offset | Feld | Format | Hinweis |
| :--- | :--- | :--- | :--- |
| `0x00` | Opcode | `0xD0` | |
| `0x01` | Unbekannt | `0x00` | In jedem bisherigen Sample Null |
| `0x02..0x04` | Datum | `YY MM DD` | **Live verifiziert:** `1A 0A 0F` = 2026-10-15 |
| `0x05..0x07` | Uhrzeit | `HH MM SS` | **Live verifiziert:** `13 31 0C` = 19:49:12 |
| `0x08..0x0A` | Dauer (s) | 3 Bytes, direkt | `00 00 29` = 41 s |

#### B. SpO2-Datenblock (`0xA3` -> `0xD3`) und Puls-Datenblock (`0xA2` -> `0xD2`)

Anfrage: `A3 00 00 00 23` (SpO2) bzw. `A2 00 00 00 22` (Puls), jeweils ab
Subframe 0. Antwort: eine durchgehende Kette von 20-Byte-Subframes
(`[D3|D2] seq 00 [16 Datenbytes] [Prüfsumme]`), die NICHT an 64-Byte-Report-
Grenzen ausgerichtet ist -- ein Subframe kann über zwei Reports verteilt sein.

**Live verifiziert (2026-10-15):** je 3 Reports, 7 Subframes pro Block, **jede
Prüfsumme korrekt** (`sum(Byte[0..18]) mod 128 == Byte[19]`). Subframes mit
reinem `0x7F`-Byte-Inhalt ("kein Finger") liegen bei SpO2 und Puls an den
**gleichen** Subframe-Positionen (seq 0, 2, 5) -- beide Reihen werden
offenbar zeitgleich, Sekunde für Sekunde, gemessen.

#### C. Block-Quittung (`0xA7` -> `0xD8`)

| Reihe | Anfrage | Antwort |
| :--- | :--- | :--- |
| SpO2 | `A7 01 28` | `D8 01 00 59` |
| Puls | `A7 00 27` | `D8 00 00 58` |

**Felder der `0xD8`-Antwort** (aus der Disassembly @ `0x004c55ba`):

| Offset | Feld | Hinweis |
| :--- | :--- | :--- |
| `0x00` | Opcode | `0xD8` |
| `0x01` | Block-Typ | `0x01` = SpO2, `0x00` = Puls |
| `0x02` | Status | `0x00` = Erfolg (Code prüft `== 0`, setzt internes ACK-Flag) |
| `0x03` | Checksum | `0x59` (SpO2) / `0x58` (Puls) |

**Modul-Zuordnung** (String-Referenzen in der gleichen Disassembly): MFC-Name
`STR_StorageManual` / "Single Spo2"; Datenbanktabelle `Spo2Single`
(`.?AVCDbSpo2SingleInfo@@`); Speicherort exportierter Dateien
`%s\50KReview\Spo2Single\*.csv`. Bestätigt, dass "Manual" und "Single SpO2"
die herstellereigenen Bezeichnungen für diesen Aufnahmemodus sind.

#### D. Ende des manuellen Downloads

`A3 7F` (SpO2) und `A2 7F` (Puls) signalisieren das reguläre Ende -- analog zu
`0x9D 0x02` (`SEGMENT_ACK`) im Auto-Mode-Speicherpfad.

#### E. Delta-Dekodierung -- **GELÖST UND VERIFIZIERT**

**Gelöst am 15.10.2026.** Alle 8 Daten-Subframes des Referenz-Mitschnitts
dekodieren zu physiologisch plausiblen Werten -- ohne Offset, Skalierung
oder Nachkorrektur.

Innerhalb eines 20-Byte-Subframes `[Opcode][seq][00][16 Datenbytes][Prüfsumme]`:

| Offset | Feld | Bedeutung |
| :--- | :--- | :--- |
| `0x03..0x04` | Unbekannt | Für die Dekodierung nicht nötig |
| `0x05` | **Basiswert** | Erster Messwert, direkt: SpO2 in %, Puls in bpm. `0x7F` = ganzer Subframe "kein Finger". |
| `0x06..0x12` | Delta-Strom | 13 Bytes, 2 Messpunkte je Byte, **High-Nibble zuerst** |
| `0x13` | Prüfsumme | `sum(Byte[0x00..0x12]) % 128` |

Ein Subframe trägt also maximal **27 Messpunkte** (1 Basis + 13x2 Deltas).

Jedes Nibble ist Vorzeichen+Betrag: **Bit 3 = Vorzeichen** (1 = negativ),
**Bits 2..0 = Betrag** (0-7). Die Kette ist **laufend**:
`S_n = S_(n-1) +/- Betrag`.

Zwei Terminatoren, in dieser Reihenfolge geprüft:

1. **Ganzes Byte `0x7F`** -- Padding, Subframe endet. Wird geprüft, *bevor*
   in Nibbles zerlegt wird.
2. **Nibble `0xF`** -- Endemarke bei ungerader Anzahl; Subframe endet an
   diesem Halbbyte.

Referenz-Implementierung siehe PROTOCOL.md §3.14.F.

Dekodierter Referenz-Mitschnitt: SpO2 96-100 %, Puls 62-67 bpm, 59 Messpunkte
mit Signal auf einer 140-Punkte-Zeitachse (~2m20s); Subframes 0, 2 und 5 sind
"kein Finger".

> **Warum die früheren Versuche falsch lagen:** Zwei Anläufe lasen den
> Basiswert von Offset `0x03` statt `0x05`. Daraus folgten SpO2-Werte von
> 116-127 (vermeintlich "über der 100%-Grenze"), negative Pulswerte und
> daraufhin die beiden Fehlschlüsse "konstanter Offset 27-28" und
> "Einschwing-Transiente in Subframe 1 und 3". Alles war nur der
> Off-by-two. Die gemeldete Disassembly-Notiz "Byte `0x04` des
> Datenbereichs ist der Basiswert" war **korrekt** -- zählt man den
> Datenbereich ab dem `seq`-Byte (`rec[1]`), ist Index 4 genau `rec[5]`.

> **Offene Punkte, aktualisiert am 15.10.2026 nach einem zweiten
> Live-Pull (bytidentisch zum ersten Mitschnitt -- deterministisch, kein
> Transkriptionsfehler) und einem zweiten relayten Disassembly-Durchgang:**
>
> (a) **Offset `0x04` ist KEINE Kanal-ID.** Eine relayte Disassembly
> behauptete, dieses Byte sei ein konstantes Hardware-Kanal-Flag (`0x08`
> für SpO2, `0x04` für Puls). Direkt am Live-Mitschnitt geprüft: nicht
> konstant. SpO2 zeigt `0x7C, 0x00, 0x7F, 0x7F`, Puls `0x7D, 0x00, 0x7F,
> 0x7F` über die vier echten Subframes. Ein Negativ-Befund aus der
> Disassembly ergänzt das: Der Host (`SpO2.exe`) liest dieses Byte an
> keiner Stelle des Dekodierpfads -- er liest Byte 0/1/2 und springt dann
> direkt zu Byte 4 (Basiswert). Das erklärt, warum die PC-Software trotz
> der wechselnden Werte funktioniert (sie ignoriert das Feld schlicht), sagt
> aber nichts darüber, was die **Firmware** dort tatsächlich codiert --
> ein Kandidat (unbestätigt): Hardware-Statusbits oder Signalgüte der MCU.
> Bleibt offiziell unidentifiziert.
>
> (b) **High-Nibble-zuerst jetzt zweifach abgesichert.** Der empirische
> Glattheitstest auf diesem Mitschnitt war nahezu unentschieden (23 zu 24
> von 189 Punkten). Eine zweite, unabhängig relayte Beschreibung der
> Dekodierschleife stimmt exakt mit der hier verwendeten Nibble-Arithmetik
> überein (Vorzeichen Bit 7 des Bytes / Bit 3 des Nibbles, Betrag in den
> restlichen 3 Bits, High-Nibble zuerst) -- Bestätigung, nicht Herkunft,
> der bereits dokumentierten Formel. Als geklärt zu behandeln, sofern ein
> Mitschnitt mit scharfen Übergängen nicht widerspricht.
>
> (c) **Dauer-Feld vs. Stream-Länge: plausibler Mechanismus angeboten,
> nicht unabhängig bestätigt.** Dieselbe relayte Quelle behauptet, der
> Host-Reader breche die Sample-Zählung exakt beim Header-Dauerwert ab
> (`cmp edx, [this+0x120]`) und behandle alles danach -- selbst Deltas, die
> wie echte konstante Messwerte aussehen -- als verwerfbares Padding. Das
> würde 41s echte Daten mit einem 59-Punkte-Decode vereinbaren, ist aber aus
> den Rohbytes allein nicht prüfbar: `0x00`-Deltas sind von echten
> "keine Änderung"-Messwerten nicht unterscheidbar -- genau das war die
> ursprüngliche Ambiguität. Eine präzise zeitgestoppte frische
> Aufnahme (am Gerät selbst gestartet/gestoppt) ist weiterhin der einzige
> Weg, das direkt zu klären.

---
---
