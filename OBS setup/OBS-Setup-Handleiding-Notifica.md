# OBS Studio setup-handleiding

**Doel:** schermopnames met webcam-overlay maken van Power BI-dashboards, direct klaar voor upload naar Vimeo.

---

## 1. Installatie

Download OBS Studio gratis via [obsproject.com](https://obsproject.com). Beschikbaar voor Windows, Mac en Linux. Installeer met standaardinstellingen.

---

## 2. Eenmalige configuratie (circa 15 minuten)

### 2.1 Output-instellingen

Ga naar **Instellingen → Output**:

| Instelling | Waarde |
|---|---|
| Output Mode | Simple |
| Recording Quality | High Quality, Medium File Size |
| Recording Format | mp4 |
| Encoder | x264 (of Hardware indien beschikbaar) |

### 2.2 Video-instellingen

Ga naar **Instellingen → Video**:

| Instelling | Waarde |
|---|---|
| Base (Canvas) Resolution | 1920x1080 |
| Output (Scaled) Resolution | 1920x1080 |
| FPS | 30 |

---

## 3. Scene inrichten

Dit is het hart van de setup. Je maakt één scene aan die je voor elke opname hergebruikt.

### 3.1 Nieuwe scene aanmaken

1. Klik in het paneel **Scenes** (linksonder) op het **+** icoon.
2. Noem de scene **"Dashboard opname"** (of een naam naar keuze).

### 3.2 Bron 1 — Schermopname (je dashboard)

1. Klik in het paneel **Sources** op het **+** icoon.
2. Kies **Display Capture** (volledig scherm) of **Window Capture** (alleen je browser).
3. **Tip:** gebruik Window Capture op je browser met het Power BI-dashboard. Dan worden notificaties en andere vensters niet zichtbaar.

### 3.3 Bron 2 — Webcam-overlay

1. Klik opnieuw op **+** in Sources.
2. Kies **Video Capture Device** en selecteer je webcam.
3. De webcam verschijnt als groot venster over je scherm. Versleep en verklein het naar **links onderin**.
4. Aanbevolen formaat: circa **300×200 pixels** — klein genoeg om het dashboard niet te blokkeren, groot genoeg om je gezicht te zien.
5. **Optioneel:** klik rechts op de webcam-bron → Filters → Effect Filters → + → "Rounded corners" voor een moderne, ronde look (net als bij Loom).

### 3.4 Bron 3 — Notifica-logo (optioneel)

1. Klik op **+** in Sources → **Image**.
2. Selecteer het Notifica-logo (bij voorkeur PNG met transparante achtergrond).
3. Positioneer rechts onderin of rechts bovenin. Maak het subtiel klein.

### 3.5 Bronvolgorde in het Sources-paneel

De volgorde bepaalt wat boven- of onderop ligt. Van boven naar beneden:

| Positie | Bron | Toelichting |
|---|---|---|
| 1 (bovenop) | Logo (Image) | Altijd zichtbaar bovenop alles |
| 2 | Webcam (Video Capture) | Boven het dashboard |
| 3 (onderop) | Scherm (Display/Window) | Vult het volledige canvas |

---

## 4. Audio-instellingen

Ga naar **Instellingen → Audio**:

- **Mic/Auxiliary Audio:** selecteer je microfoon of headset. Een externe USB-microfoon of headset geeft veel beter geluid dan een ingebouwde laptopmicrofoon.
- **Desktop Audio:** zet op "Disabled" tenzij je systeemgeluid wilt opnemen.

Test je audio door te praten en te kijken of de groene balken bewegen in de **Audio Mixer** (onderaan het hoofdscherm).

---

## 5. Opnameworkflow (per video)

Na de eenmalige setup is dit het enige wat je per opname hoeft te doen:

| Stap | Actie | Tijd |
|---|---|---|
| 1 | Open je Power BI-dashboard in de browser | 30 sec |
| 2 | Open OBS en controleer of je scene er goed uitziet | 15 sec |
| 3 | Leg je script naast je scherm (tweede scherm of print) | 10 sec |
| 4 | Klik op "Start Recording" (rechtsonder in OBS) | 1 sec |
| 5 | Wacht 3 seconden stilte (makkelijker knippen later) | 3 sec |
| 6 | Volg je script: praat en klik door de dashboards | 3–8 min |
| 7 | Klik op "Stop Recording" | 1 sec |
| 8 | Upload het MP4-bestand naar Vimeo | 2 min |

**Totale doorlooptijd per video (exclusief spreektijd): circa 3 minuten.**

---

## 6. Tips voor een professioneel resultaat

### Belichting

Zorg dat je gezicht goed verlicht is — bij voorkeur met een lichtbron vóór je (niet achter je). Een simpele bureaulamp gericht op je gezicht maakt al een enorm verschil. Vermijd achtergrondlicht (raam achter je) dat je gezicht donker maakt.

### Audio

Een externe microfoon (bijvoorbeeld een USB-condensatormicrofoon of een goede headset) verbetert de audiokwaliteit drastisch. Neem op in een rustige ruimte en vermijd echo door zachte materialen om je heen.

### Dashboard voorbereiding

- Zet je browser op 100% zoom en gebruik fullscreen (F11).
- Sluit alle tabbladen behalve het dashboard.
- Zet notificaties uit (Windows: Focus Assist / Mac: Do Not Disturb).
- Zorg dat het dashboard volledig geladen is vóór je begint met opnemen.

### Spreektempo

Praat iets langzamer dan je normaal zou doen. Pauzeer kort na elke klik zodat kijkers kunnen zien wat er verandert op het scherm. Als je je verspreekt: pauzeer even, en begin de zin opnieuw — dat stukje kun je er in Vimeo eenvoudig uitknippen.

---

## 7. Upload naar Vimeo

Na het stoppen van de opname vind je het MP4-bestand in de map die OBS gebruikt (standaard: je Video's-map). Controleer dit via **Instellingen → Output → Recording Path**.

1. Ga naar **vimeo.com** en log in.
2. Klik op **New Video → Upload**.
3. Sleep je MP4-bestand erin of klik om te selecteren.
4. Vul titel en beschrijving in.
5. Stel privacy in op **"Only people with the private link"** als de video's alleen voor klanten bedoeld zijn.
6. Gebruik Vimeo's **Showcase-functie** om per klant of per onderwerp een branded videopagina te maken — dit is jullie "website vanuit Vimeo".

---

## 8. Snelle referentiekaart

Handige OBS-sneltoetsen (instelbaar via **Instellingen → Hotkeys**):

| Actie | Aanbevolen sneltoets |
|---|---|
| Start/stop opname | Ctrl + Shift + R |
| Pauze opname | Ctrl + Shift + P |
| Webcam aan/uit (mute) | Ctrl + Shift + W |

Met deze sneltoetsen hoef je tijdens de opname niet meer naar OBS te wisselen.
