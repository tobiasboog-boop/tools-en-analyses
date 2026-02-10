# Test Cases voor V1 vs V2 Backtest

Gebaseerd op Gerrit's feedback over typische fouten van V1.

## Test Case 1: Ventilator vervangen (moet JA zijn)
**Gerrit's opmerking:** "Ventilator is ketelonderdeel, binnen contract"
**Correcte classificatie:** JA

**Werkbon verhaal:**
```
WERKBON #123456
Debiteur: 005102 - Trivire
Totaal kosten: €245.50

=== PARAGRAAF: Storing ===
Storing: Ketel geeft foutmelding
Oorzaak: Ventilator defect

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)
- Storing verhelpen: €115.33 (1.5 uur)
- Ventilator: €110.00 (materiaal)

OPLOSSINGEN:
- Ventilator vervangen
  Toelichting: Ketel gaf foutmelding F28. Ventilator draaide niet meer. Nieuwe ventilator gemonteerd, ketel doet het weer.
```

---

## Test Case 2: Leiding onder ketel repareren (moet NEE zijn)
**Gerrit's opmerking:** "Leiding onder de ketel is NIET binnen de ketelkast, dus buiten contract"
**Correcte classificatie:** NEE

**Werkbon verhaal:**
```
WERKBON #123457
Debiteur: 005102 - Trivire
Totaal kosten: €187.25

=== PARAGRAAF: Storing ===
Storing: Lekkage bij ketel
Oorzaak: Leiding defect

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)
- Reparatie uitvoeren: €95.00 (1.3 uur)
- Leidingmaterialen: €72.08 (materiaal)

OPLOSSINGEN:
- Leiding gerepareerd
  Toelichting: Lekkage ONDER de cv-ketel. Cv-leiding naar radiator was doorgerot. Stuk leiding vervangen, leidingloop ligt deels onder vloer.
```

---

## Test Case 3: Pakking vervangen (moet JA zijn)
**Gerrit's opmerking:** "Pakking is binnen de ketelkast, binnen contract"
**Correcte classificatie:** JA

**Werkbon verhaal:**
```
WERKBON #123458
Debiteur: 005102 - Trivire
Totaal kosten: €98.45

=== PARAGRAAF: Storing ===
Storing: Ketel lekt
Oorzaak: Pakking versleten

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)
- Storing verhelpen: €76.50 (1.05 uur)
- Pakking: €1.78 (materiaal)

OPLOSSINGEN:
- Pakking ververst
  Toelichting: Ketel lekte bij warmtewisselaar. Pakking tussen leidingen was versleten. Nieuwe pakking aangebracht, ketel is weer dicht.
```

---

## Test Case 4: Expansievat vervangen (moet JA zijn)
**Gerrit's opmerking:** "Expansievat staat in contract als X (binnen contract)"
**Correcte classificatie:** JA

**Werkbon verhaal:**
```
WERKBON #123459
Debiteur: 005102 - Trivire
Totaal kosten: €234.15

=== PARAGRAAF: Storing ===
Storing: Druk loopt steeds op
Oorzaak: Expansievat defect

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)
- Storing verhelpen: €153.98 (2.0 uur)
- Expansievat: €60.00 (materiaal)

OPLOSSINGEN:
- Expansievat vervangen
  Toelichting: Waterdruk liep steeds op. Expansievat had geen membraan meer. Nieuw expansievat gemonteerd en systeem bijgevuld.
```

---

## Test Case 5: Gasklep vervangen (moet JA zijn)
**Opmerking:** "Gasklep is ketelonderdeel binnen de ketelkast"
**Correcte classificatie:** JA

**Werkbon verhaal:**
```
WERKBON #123460
Debiteur: 005102 - Trivire
Totaal kosten: €312.50

=== PARAGRAAF: Storing ===
Storing: Ketel start niet
Oorzaak: Gasklep defect

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)
- Storing verhelpen: €124.33 (1.7 uur)
- Gasklep: €168.00 (materiaal)

OPLOSSINGEN:
- Gasklep vervangen
  Toelichting: Ketel probeerde te starten maar kreeg geen gas. Gasklep zat dicht en reageerde niet. Nieuwe gasklep gemonteerd, ketel start normaal.
```

---

## Test Case 6: Radiator vervangen (moet NEE zijn)
**Opmerking:** "Contract zegt expliciet: radiator vervangen - berekenen"
**Correcte classificatie:** NEE

**Werkbon verhaal:**
```
WERKBON #123461
Debiteur: 005102 - Trivire
Totaal kosten: €456.80

=== PARAGRAAF: Storing ===
Storing: Radiator lekt
Oorzaak: Radiator doorgerot

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)
- Radiator vervangen arbeid: €169.00 (vast tarief TR002)
- Radiator materiaal 1200W: €228.00 (12 x €19 per 100W, TR003)
- Aansluitmateriaal: €39.63 (materiaal)

OPLOSSINGEN:
- Radiator vervangen
  Toelichting: Oude radiator in slaapkamer lekte onderaan. Radiator was doorgerot. Oude radiator eraf, nieuwe radiator (1200W) gemonteerd en systeem bijgevuld.
```

---

## Test Case 7: Pomp van de ketel vervangen (moet JA zijn)
**Opmerking:** "Pomp van de ketel is expliciet ketelonderdeel"
**Correcte classificatie:** JA

**Werkbon verhaal:**
```
WERKBON #123462
Debiteur: 005102 - Trivire
Totaal kosten: €287.45

=== PARAGRAAF: Storing ===
Storing: Ketel wordt niet warm
Oorzaak: Pomp defect

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)
- Storing verhelpen: €132.28 (1.8 uur)
- Pomp: €135.00 (materiaal)

OPLOSSINGEN:
- Pomp vervangen
  Toelichting: Ketel brandt maar water wordt niet warm. Pomp van de ketel draaide niet meer. Nieuwe circulatiepomp in ketel gemonteerd.
```

---

## Test Case 8: Verstopping leidingen (moet NEE zijn)
**Opmerking:** "Contract: onderblokken door verstopping - berekenen"
**Correcte classificatie:** NEE

**Werkbon verhaal:**
```
WERKBON #123463
Debiteur: 005102 - Trivire
Totaal kosten: €198.75

=== PARAGRAAF: Storing ===
Storing: Radiator wordt niet warm
Oorzaak: Verstopping

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)
- Doorspuiten leidingen: €178.58 (2.4 uur)

OPLOSSINGEN:
- Installatie doorgespoeld
  Toelichting: Radiator woonkamer werd niet warm. Onderblok zat verstopt. Systeem doorgespoeld, veel vuil eruit gekomen. Radiator doet het weer.
```

---

## Test Case 9: CV-leiding binnen 2m van ketel (moet JA zijn - EDGE CASE)
**Opmerking:** "Contract: cv-leiding < 2m binnen contract"
**Correcte classificatie:** JA

**Werkbon verhaal:**
```
WERKBON #123464
Debiteur: 005102 - Trivire
Totaal kosten: €145.30

=== PARAGRAAF: Storing ===
Storing: Lekkage bij ketel
Oorzaak: Cv-leiding lek

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)
- Reparatie: €89.13 (1.2 uur)
- Leidingmateriaal: €36.00 (materiaal)

OPLOSSINGEN:
- Cv-leiding gerepareerd
  Toelichting: Kleine lekkage direct naast de ketel (50 cm vanaf ketel). Stukje cv-leiding dat uit de ketel komt was lek. Leidingstuk vervangen.
```

---

## Test Case 10: Niet thuis geweest (moet TWIJFEL zijn)
**Opmerking:** "Kan niet beoordelen wat er aan de hand was"
**Correcte classificatie:** TWIJFEL

**Werkbon verhaal:**
```
WERKBON #123465
Debiteur: 005102 - Trivire
Totaal kosten: €20.17

=== PARAGRAAF: Storing ===
Storing: Ketel doet het niet
Oorzaak: Onbekend

KOSTENREGELS:
- Reistijd werkbon: €20.17 (0.28 uur)

OPLOSSINGEN:
- Niet thuis geweest
  Toelichting: Bewoner niet thuis aangetroffen. Niet binnen geweest. Nieuwe afspraak gemaakt.
```
