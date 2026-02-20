# 🎯 Funnel Automation - Gebruikshandleiding

## 🚀 Quick Start

### Dagelijks Gebruik

**1. Bereken lead scores:**
```bash
cd c:/projects/tools_en_analyses/funnel_automation
python score_leads_complete.py
```

**2. Bekijk resultaten in dashboard:**
```bash
streamlit run dashboard.py
```

**3. Update Pipedrive (optioneel):**
```bash
python update_pipedrive_scores.py
```

---

## 📊 Wat Krijg Je?

### CSV Export
- Alle leads met scores
- CRM score + Email score breakdown
- Sorteer op totale score
- Filter op segment

### Dashboard
- 📈 Real-time statistieken
- 🔍 Filter functionaliteit
- 📥 Download gefilterde data
- 🏆 Top 10 leads visualisatie

### Pipedrive Update
- Scores verschijnen in custom fields
- Automatisch segment label
- Last scored date

---

## 🎯 Lead Segmenten

### 🔥 Warme Leads (80-100 punten)
**Actie:** Direct bellen!
- Recent contact (laatste 7 dagen)
- Actieve deals in late stage
- Hoge email engagement
- Meerdere clicks in emails

### 🟡 Lauwe Leads (40-79 punten)
**Actie:** Nurturing campagne
- Enige activiteit (laatste 14-30 dagen)
- Deals in early/mid stage
- Matige email opens
- Follow-up nodig

### 🧊 Koude Leads (0-39 punten)
**Actie:** Content marketing
- Weinig/geen activiteit
- Geen actieve deals
- Lage/geen email engagement
- Long-term nurturing

---

## 📈 Score Breakdown

Elke lead krijgt punten voor:

**Pipedrive CRM (max 70):**
- Recent contact: 0-30 punten
- Deal status: 0-35 punten
- Activiteit frequentie: 0-20 punten
- Email engagement: 0-15 punten

**MailerLite Email (max 30):**
- Open rate: 0-15 punten
- Click rate: 0-15 punten

**Totaal: 0-100 punten**

---

## 🔄 Workflow

```
1. Run score_leads_complete.py
   ↓
2. Check resultaten in CSV
   ↓
3. Open dashboard voor visueel overzicht
   ↓
4. Filter op "Warm" voor actie
   ↓
5. Bel top leads!
   ↓
6. (Optioneel) Update Pipedrive met nieuwe scores
```

---

## 💡 Tips

1. **Run weekly** voor verse data
2. **Focus op Warm leads** first
3. **Check email engagement** in MailerLite export
4. **Update scores in Pipedrive** voor team visibility
5. **Export filtered CSV** voor calling lists

---

## 📞 Volgende Stappen

Na scoring:
- [ ] Bel warme leads (80+ score)
- [ ] Setup nurturing voor lauwe leads
- [ ] Plan content voor koude leads
- [ ] Track conversies in Pipedrive
- [ ] Re-run wekelijks voor nieuwe scores
