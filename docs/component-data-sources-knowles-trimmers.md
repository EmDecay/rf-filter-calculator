# Knowles Voltronics Trimmer Data

This appendix to [component-data-sources.md](component-data-sources.md#trimmer-capacitors)
lists, type by type, the Knowles Voltronics trimmers whose catalog states both range ends as
bounds: the glass and quartz piston trimmers (S, H, TF, TM, TP, QM and QP series), the K series
air trimmers and the K_HV series PTFE trimmers. Every value comes from the Knowles catalog
[KNO-CAT-R5] ("Trimmers and Non-Magnetic Components", R5, PDF dated 2024-08-22; URL and SHA-256
in the [source index](component-data-sources.md#source-index)), on the page given. It is
packaged with the main per-part table as `filter_lib/shared/trimmer_data.json`, and
`tests/test_trimmer_data.py` checks every packaged row against this page.

**How to read it.**

- "Cmin ≤" and "Cmax ≥" are the catalog's bounds. For the glass and quartz lines the general
  specifications (p. 41) say: "From below minimum to above maximum value listed for each part.
  Capacitance measured at 1 MHz." The K and K_HV tables head their range columns "Capacitance
  Range (pF) From Below To Above" and state no measurement frequency.
- Q is as the catalog states it: the glass and quartz tables give "Q (Min.) at 1 MHz" with no
  setting; the K line gives a typical Q only (p. 19); the K_HV table gives "Q at 100MHz at maximum rated
  C", measured with no terminals and not labelled a minimum. No line states an SRF, so the
  calculator assumes a series inductance of at most 10 nH for every Knowles part.
- A row holds the base type numbers of the electrical tables (124 ranges, 258 types) that share
  a range, Q, dielectric and rating; "Mounting" gives each type's own mounting, from its column
  heading. Lead style letters refer to the K line drawings on p. 21, except G, drawn on p. 26
  (figure 5). Optional configurations ordered by adding letters to a type number (for example
  the extended shafts TM9EI and TM9CE and the insulated bushing TIM9C on p. 45, or KP10HVE on
  p. 33) are not listed.
- Four type numbers are printed or extracted with a character that breaks the series naming;
  this page gives them in that naming: TM30G ("1M30G" on p. 46), TM15 ("TMI5"), TP15 ("TPI5")
  and QP10G ("QP1OG").
- The JZ and JR chip trimmers are not listed: their minimum is printed as a bare value
  (component-data-sources.md, Trimmer capacitors, Not qualifying).

| Part numbers | Cmin ≤ | Cmax ≥ | Q as stated | Dielectric | Working V | Mounting | Source |
|---|---|---|---|---|---|---|---|
| SP10, SF10A, SM10 | 1.5 pF | 10 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 250 V | SP10: THT horizontal mount; SF10A: THT vertical mount; SM10: surface mount | [KNO-CAT-R5] p. 42 |
| SP20, SF20A, SM20 | 1.5 pF | 20 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 250 V | SP20: THT horizontal mount; SF20A: THT vertical mount; SM20: surface mount | [KNO-CAT-R5] p. 42 |
| SP30, SF30A, SM30 | 1.5 pF | 30 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 250 V | SP30: THT horizontal mount; SF30A: THT vertical mount; SM30: surface mount | [KNO-CAT-R5] p. 42 |
| SP40, SF40A, SM40 | 1.5 pF | 40 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 250 V | SP40: THT horizontal mount; SF40A: THT vertical mount; SM40: surface mount | [KNO-CAT-R5] p. 42 |
| HSP19, HSF19, HSM19, HTM19C | 2 pF | 19 pF | min 1000 at 1 MHz (setting not stated) | H series high-range glass, TC -150 ±150 ppm/C | 125 V | HSP19: THT horizontal printed circuit; HSF19: THT vertical printed circuit; HSM19: surface mount; HTM19C: panel mount | [KNO-CAT-R5] p. 43 |
| HSP34, HSF34, HSM34, HTM34C | 2 pF | 34 pF | min 900 at 1 MHz (setting not stated) | H series high-range glass, TC -150 ±150 ppm/C | 125 V | HSP34: THT horizontal printed circuit; HSF34: THT vertical printed circuit; HSM34: surface mount; HTM34C: panel mount | [KNO-CAT-R5] p. 43 |
| HSP46, HSF46, HSM46, HTM46C | 2 pF | 46 pF | min 800 at 1 MHz (setting not stated) | H series high-range glass, TC -150 ±150 ppm/C | 125 V | HSP46: THT horizontal printed circuit; HSF46: THT vertical printed circuit; HSM46: surface mount; HTM46C: panel mount | [KNO-CAT-R5] p. 43 |
| HSP64, HSF64, HSM64, HTM64C | 2 pF | 64 pF | min 700 at 1 MHz (setting not stated) | H series high-range glass, TC -150 ±150 ppm/C | 125 V | HSP64: THT horizontal printed circuit; HSF64: THT vertical printed circuit; HSM64: surface mount; HTM64C: panel mount | [KNO-CAT-R5] p. 43 |
| HTP96C, HTM96C | 2 pF | 96 pF | min 600 at 1 MHz (setting not stated) | H series high-range glass, TC -150 ±150 ppm/C | 125 V | HTP96C: THT horizontal printed circuit; HTM96C: panel mount | [KNO-CAT-R5] p. 43 |
| HTP130C, HTM130C | 2 pF | 130 pF | min 500 at 1 MHz (setting not stated) | H series high-range glass, TC -150 ±150 ppm/C | 125 V | HTP130C: THT horizontal printed circuit; HTM130C: panel mount | [KNO-CAT-R5] p. 43 |
| HTP210C, HTM210C | 2 pF | 210 pF | min 350 at 1 MHz (setting not stated) | H series high-range glass, TC -150 ±150 ppm/C | 125 V | HTP210C: THT horizontal printed circuit; HTM210C: panel mount | [KNO-CAT-R5] p. 43 |
| HTP250C, HTM250C | 2 pF | 250 pF | min 250 at 1 MHz (setting not stated) | H series high-range glass, TC -150 ±150 ppm/C | 125 V | HTP250C: THT horizontal printed circuit; HTM250C: panel mount | [KNO-CAT-R5] p. 43 |
| TF5A | 0.8 pF | 4.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TF5A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF6A | 0.8 pF | 5.5 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TF6A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF8A | 1 pF | 8.5 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TF8A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF9A | 0.8 pF | 8.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TF9A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF11A | 1 pF | 11 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TF11A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF12A | 0.8 pF | 12 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TF12A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF17A | 0.8 pF | 16 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TF17A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF10A | 1.2 pF | 10 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TF10A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF14A | 1.5 pF | 14 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TF14A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF15A | 1.2 pF | 16 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TF15A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF16A | 1 pF | 16 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TF16A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF22A | 2 pF | 22 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TF22A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF25A | 2 pF | 25 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TF25A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF28A | 1 pF | 28 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TF28A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TF36A | 1 pF | 36 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TF36A: THT vertical PC mount | [KNO-CAT-R5] p. 44 |
| TM5, TM5C | 0.8 pF | 4.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM5: panel mount, unsealed; TM5C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM5G | 0.8 pF | 4.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM5G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM6, TM6C | 0.8 pF | 5.5 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM6: panel mount, unsealed; TM6C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM6G | 0.8 pF | 5.5 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM6G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM9, TM9C | 0.8 pF | 8.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM9: panel mount, unsealed; TM9C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM9G | 0.8 pF | 8.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM9G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM11, TM11C | 1 pF | 11 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM11: panel mount, unsealed; TM11C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM11G | 1 pF | 11 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM11G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM12, TM12C | 0.8 pF | 12 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM12: panel mount, unsealed; TM12C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM12G | 0.8 pF | 12 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM12G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM17, TM17C | 0.8 pF | 16 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM17: panel mount, unsealed; TM17C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM17G | 0.8 pF | 16 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM17G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM18, TM18C | 0.8 pF | 18 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM18: panel mount, unsealed; TM18C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM18G | 0.8 pF | 18 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM18G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM21, TM21C | 0.8 pF | 21 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM21: panel mount, unsealed; TM21C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM23, TM23C | 0.8 pF | 23 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM23: panel mount, unsealed; TM23C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM23G | 0.8 pF | 23 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM23G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM30, TM30C | 0.8 pF | 30 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM30: panel mount, unsealed; TM30C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM30G | 0.8 pF | 30 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM30G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM38, TM38C | 0.8 pF | 38 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TM38: panel mount, unsealed; TM38C: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM38G | 0.8 pF | 38 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TM38G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TM10, TM10C, TM10M | 2 pF | 10 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TM10: panel mount, unsealed; TM10C: panel mount, sealed, metal cap, turret terminal; TM10M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM14, TM14C, TM14M | 1.5 pF | 14 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM14: panel mount, unsealed; TM14C: panel mount, sealed, metal cap, turret terminal; TM14M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM15, TM15C, TM15M | 1.2 pF | 16 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TM15: panel mount, unsealed; TM15C: panel mount, sealed, metal cap, turret terminal; TM15M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM16, TM16C, TM16M | 1 pF | 16 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM16: panel mount, unsealed; TM16C: panel mount, sealed, metal cap, turret terminal; TM16M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM25, TM25C, TM25M | 2 pF | 25 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM25: panel mount, unsealed; TM25C: panel mount, sealed, metal cap, turret terminal; TM25M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM28, TM28C, TM28M | 1 pF | 28 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM28: panel mount, unsealed; TM28C: panel mount, sealed, metal cap, turret terminal; TM28M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM36, TM36C, TM36M | 1 pF | 36 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM36: panel mount, unsealed; TM36C: panel mount, sealed, metal cap, turret terminal; TM36M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM42, TM42C, TM42M | 1 pF | 42 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM42: panel mount, unsealed; TM42C: panel mount, sealed, metal cap, turret terminal; TM42M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM52, TM52C, TM52M | 1 pF | 52 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM52: panel mount, unsealed; TM52C: panel mount, sealed, metal cap, turret terminal; TM52M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM60, TM60C, TM60M | 1 pF | 60 pF | min 650 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM60: panel mount, unsealed; TM60C: panel mount, sealed, metal cap, turret terminal; TM60M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM75, TM75C, TM75M | 1 pF | 75 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM75: panel mount, unsealed; TM75C: panel mount, sealed, metal cap, turret terminal; TM75M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM90, TM90C, TM90M | 1 pF | 90 pF | min 600 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM90: panel mount, unsealed; TM90C: panel mount, sealed, metal cap, turret terminal; TM90M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM120, TM120C, TM120M | 1 pF | 120 pF | min 600 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TM120: panel mount, unsealed; TM120C: panel mount, sealed, metal cap, turret terminal; TM120M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| TM180, TM180C, TM180M | 2 pF | 180 pF | min 500 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TM180: panel mount, unsealed; TM180C: panel mount, sealed, metal cap, turret terminal; TM180M: panel mount, sealed, metal cap | [KNO-CAT-R5] p. 46 |
| QM2 | 0.6 pF | 1.8 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 750 V | QM2: panel mount, unsealed | [KNO-CAT-R5] p. 46 |
| QM2G | 0.6 pF | 1.8 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 1250 V | QM2G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| QM6 | 0.8 pF | 5.5 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 750 V | QM6: panel mount, unsealed | [KNO-CAT-R5] p. 46 |
| QM6G | 0.8 pF | 5.5 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 1250 V | QM6G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| QM10 | 0.6 pF | 9.5 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 750 V | QM10: panel mount, unsealed | [KNO-CAT-R5] p. 46 |
| QM10G | 0.6 pF | 9.5 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 1250 V | QM10G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| QM16 | 0.8 pF | 16 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 750 V | QM16: panel mount, unsealed | [KNO-CAT-R5] p. 46 |
| QM16G | 0.8 pF | 16 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 1250 V | QM16G: panel mount, sealed, glass/quartz end | [KNO-CAT-R5] p. 46 |
| TP5 | 0.8 pF | 4.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP5: THT horizontal mount, unsealed | [KNO-CAT-R5] p. 48 |
| TP5G, TP5GA | 0.8 pF | 4.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP5G: THT horizontal mount, sealed, glass/quartz end; TP5GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP6 | 0.8 pF | 5.5 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP6: THT horizontal mount, unsealed | [KNO-CAT-R5] p. 48 |
| TP6G, TP6GA | 0.8 pF | 5.5 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP6G: THT horizontal mount, sealed, glass/quartz end; TP6GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP9, TP9C | 0.8 pF | 8.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP9: THT horizontal mount, unsealed; TP9C: THT horizontal mount, sealed, metal cap | [KNO-CAT-R5] p. 48 |
| TP9G, TP9GA | 0.8 pF | 8.5 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP9G: THT horizontal mount, sealed, glass/quartz end; TP9GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP11, TP11C | 1 pF | 11 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP11: THT horizontal mount, unsealed; TP11C: THT horizontal mount, sealed, metal cap | [KNO-CAT-R5] p. 48 |
| TP11G, TP11GA | 1 pF | 11 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP11G: THT horizontal mount, sealed, glass/quartz end; TP11GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP12, TP12C | 0.8 pF | 12 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP12: THT horizontal mount, unsealed; TP12C: THT horizontal mount, sealed, metal cap | [KNO-CAT-R5] p. 48 |
| TP12G, TP12GA | 0.8 pF | 12 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP12G: THT horizontal mount, sealed, glass/quartz end; TP12GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP17, TP17C | 0.8 pF | 16 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP17: THT horizontal mount, unsealed; TP17C: THT horizontal mount, sealed, metal cap | [KNO-CAT-R5] p. 48 |
| TP17G, TP17GA | 0.8 pF | 16 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP17G: THT horizontal mount, sealed, glass/quartz end; TP17GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP18, TP18C | 0.8 pF | 18 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP18: THT horizontal mount, unsealed; TP18C: THT horizontal mount, sealed, metal cap | [KNO-CAT-R5] p. 48 |
| TP18G, TP18GA | 0.8 pF | 18 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP18G: THT horizontal mount, sealed, glass/quartz end; TP18GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP21, TP21C | 0.8 pF | 21 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP21: THT horizontal mount, unsealed; TP21C: THT horizontal mount, sealed, metal cap | [KNO-CAT-R5] p. 48 |
| TP23, TP23C | 0.8 pF | 23 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP23: THT horizontal mount, unsealed; TP23C: THT horizontal mount, sealed, metal cap | [KNO-CAT-R5] p. 48 |
| TP23G, TP23GA | 0.8 pF | 23 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP23G: THT horizontal mount, sealed, glass/quartz end; TP23GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP30, TP30C | 0.8 pF | 30 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP30: THT horizontal mount, unsealed; TP30C: THT horizontal mount, sealed, metal cap | [KNO-CAT-R5] p. 48 |
| TP30G, TP30GA | 0.8 pF | 30 pF | min 650 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP30G: THT horizontal mount, sealed, glass/quartz end; TP30GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP38, TP38C | 0.8 pF | 38 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 750 V | TP38: THT horizontal mount, unsealed; TP38C: THT horizontal mount, sealed, metal cap | [KNO-CAT-R5] p. 48 |
| TP38G, TP38GA | 0.8 pF | 38 pF | min 700 at 1 MHz (setting not stated) | annular band glass, TC ±50 ppm/C | 1250 V | TP38G: THT horizontal mount, sealed, glass/quartz end; TP38GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP10, TP10C | 2 pF | 10 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TP10: THT horizontal mount, unsealed; TP10C: THT horizontal mount, sealed, metal cap, turret terminal | [KNO-CAT-R5] p. 48 |
| TP14, TP14C, TP14CA | 1.5 pF | 14 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP14: THT horizontal mount, unsealed; TP14C: THT horizontal mount, sealed, metal cap, turret terminal; TP14CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP15, TP15C | 1.2 pF | 16 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TP15: THT horizontal mount, unsealed; TP15C: THT horizontal mount, sealed, metal cap, turret terminal | [KNO-CAT-R5] p. 48 |
| TP16, TP16C, TP16CA | 1 pF | 16 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP16: THT horizontal mount, unsealed; TP16C: THT horizontal mount, sealed, metal cap, turret terminal; TP16CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP25, TP25C | 2 pF | 25 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP25: THT horizontal mount, unsealed; TP25C: THT horizontal mount, sealed, metal cap, turret terminal | [KNO-CAT-R5] p. 48 |
| TP28, TP28C, TP28CA | 1 pF | 28 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP28: THT horizontal mount, unsealed; TP28C: THT horizontal mount, sealed, metal cap, turret terminal; TP28CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP36, TP36C, TP36CA | 1 pF | 36 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP36: THT horizontal mount, unsealed; TP36C: THT horizontal mount, sealed, metal cap, turret terminal; TP36CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP42, TP42C, TP42CA | 1 pF | 42 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP42: THT horizontal mount, unsealed; TP42C: THT horizontal mount, sealed, metal cap, turret terminal; TP42CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP52, TP52C, TP52CA | 1 pF | 52 pF | min 800 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP52: THT horizontal mount, unsealed; TP52C: THT horizontal mount, sealed, metal cap, turret terminal; TP52CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP60, TP60C, TP60CA | 1 pF | 60 pF | min 650 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP60: THT horizontal mount, unsealed; TP60C: THT horizontal mount, sealed, metal cap, turret terminal; TP60CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP75, TP75C, TP75CA | 1 pF | 75 pF | min 700 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP75: THT horizontal mount, unsealed; TP75C: THT horizontal mount, sealed, metal cap, turret terminal; TP75CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP90, TP90C, TP90CA | 1 pF | 90 pF | min 600 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP90: THT horizontal mount, unsealed; TP90C: THT horizontal mount, sealed, metal cap, turret terminal; TP90CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP120, TP120C, TP120CA | 1 pF | 120 pF | min 600 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 1000 V | TP120: THT horizontal mount, unsealed; TP120C: THT horizontal mount, sealed, metal cap, turret terminal; TP120CA: THT horizontal mount, sealed, metal cap, larger MIL size | [KNO-CAT-R5] p. 48 |
| TP180, TP180C | 2 pF | 180 pF | min 500 at 1 MHz (setting not stated) | embedded band glass, TC ±150 ppm/C | 500 V | TP180: THT horizontal mount, unsealed; TP180C: THT horizontal mount, sealed, metal cap, turret terminal | [KNO-CAT-R5] p. 48 |
| QP2 | 0.8 pF | 1.8 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 750 V | QP2: THT horizontal mount, unsealed | [KNO-CAT-R5] p. 48 |
| QP2G, QP2GA | 0.8 pF | 1.8 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 1250 V | QP2G: THT horizontal mount, sealed, glass/quartz end; QP2GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| QP6 | 0.6 pF | 5.5 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 750 V | QP6: THT horizontal mount, unsealed | [KNO-CAT-R5] p. 48 |
| QP6G, QP6GA | 0.6 pF | 5.5 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 1250 V | QP6G: THT horizontal mount, sealed, glass/quartz end; QP6GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| QP10 | 0.6 pF | 9.5 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 750 V | QP10: THT horizontal mount, unsealed | [KNO-CAT-R5] p. 48 |
| QP10G, QP10GA | 0.6 pF | 9.5 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 1250 V | QP10G: THT horizontal mount, sealed, glass/quartz end; QP10GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| QP16 | 0.8 pF | 16 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 750 V | QP16: THT horizontal mount, unsealed | [KNO-CAT-R5] p. 48 |
| QP16G, QP16GA | 0.8 pF | 16 pF | min 2000 at 1 MHz (setting not stated) | quartz, TC 0 to +50 ppm/C | 1250 V | QP16G: THT horizontal mount, sealed, glass/quartz end; QP16GA: THT horizontal mount, sealed, larger MIL size | [KNO-CAT-R5] p. 48 |
| KP6 | 0.8 pF | 6 pF | typical 5000 (frequency and setting not stated) | air | 250 V | KP6: lead style P | [KNO-CAT-R5] p. 26 |
| KP8 | 0.8 pF | 8 pF | typical 5000 (frequency and setting not stated) | air | 250 V | KP8: lead style P | [KNO-CAT-R5] p. 26 |
| KP10 | 0.8 pF | 10 pF | typical 5000 (frequency and setting not stated) | air | 125 V | KP10: lead style P | [KNO-CAT-R5] p. 26 |
| KF8, KT8, KJ8, KG8, KM8 | 0.6 pF | 8 pF | typical 5000 (frequency and setting not stated) | air | 250 V | KF8: lead style F; KT8: lead style T; KJ8: lead style J; KG8: lead style G (p. 26, figure 5); KM8: lead style M | [KNO-CAT-R5] p. 26 |
| KF10, KT10, KJ10, KG10, KM10 | 0.6 pF | 10 pF | typical 5000 (frequency and setting not stated) | air | 125 V | KF10: lead style F; KT10: lead style T; KJ10: lead style J; KG10: lead style G (p. 26, figure 5); KM10: lead style M | [KNO-CAT-R5] p. 26 |
| KT6 | 0.6 pF | 6 pF | typical 5000 (frequency and setting not stated) | air | 250 V | KT6: lead style T | [KNO-CAT-R5] p. 26 |
| KP1HV, KT1HV, KJ1HV | 0.2 pF | 1 pF | 780 at 100 MHz, maximum rated C, without terminals (not labelled a minimum) | PTFE, TC 50±50 ppm/C | 1000 V | KP1HV: lead style P; KT1HV: lead style T; KJ1HV: lead style J | [KNO-CAT-R5] p. 33 |
| KP1SD, KT1SD, KJ1SD | 0.2 pF | 1 pF | 780 at 100 MHz, maximum rated C, without terminals (not labelled a minimum) | PTFE, TC 50±50 ppm/C | 250 V | KP1SD: lead style P; KT1SD: lead style T; KJ1SD: lead style J | [KNO-CAT-R5] p. 33 |
| KP4HV, KF4HV, KT4HV, KJ4HV, KM4HV | 0.6 pF | 4 pF | 2000 at 100 MHz, maximum rated C, without terminals (not labelled a minimum) | PTFE, TC 50±50 ppm/C | 1000 V | KP4HV: lead style P; KF4HV: lead style F; KT4HV: lead style T; KJ4HV: lead style J; KM4HV: lead style M | [KNO-CAT-R5] p. 33 |
| KP4SD, KF4SD, KT4SD, KJ4SD, KM4SD | 0.6 pF | 4 pF | 2000 at 100 MHz, maximum rated C, without terminals (not labelled a minimum) | PTFE, TC 50±50 ppm/C | 250 V | KP4SD: lead style P; KF4SD: lead style F; KT4SD: lead style T; KJ4SD: lead style J; KM4SD: lead style M | [KNO-CAT-R5] p. 33 |
| KP10HV, KF10HV, KT10HV, KJ10HV, KM10HV | 1 pF | 9 pF | 2000 at 100 MHz, maximum rated C, without terminals (not labelled a minimum) | PTFE, TC 50±50 ppm/C | 1000 V | KP10HV: lead style P; KF10HV: lead style F; KT10HV: lead style T; KJ10HV: lead style J; KM10HV: lead style M | [KNO-CAT-R5] p. 33 |
