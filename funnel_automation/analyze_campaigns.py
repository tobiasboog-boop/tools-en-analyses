"""Analyseer MailerLite campaign performance."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from mailerlite_api_v2 import MailerLiteAPI
from datetime import datetime

print("\n" + "="*70)
print("  MAILERLITE CAMPAIGN PERFORMANCE ANALYSE")
print("="*70 + "\n")

api = MailerLiteAPI()

# Get all campaigns
print("[1/3] Ophalen campaigns...")
campaigns = api.get_campaigns()
print(f"        Gevonden: {len(campaigns)} campaigns\n")

# Filter sent campaigns
sent_campaigns = [c for c in campaigns if c.get('status') == 'sent']

print("="*70)
print(f"{'Campaign':<35} {'Status':<8} {'Open%':>7} {'Click%':>7} {'Opens':>7}")
print("="*70)

# Sort by open rate
sent_campaigns.sort(key=lambda c: c.get('opened', {}).get('rate', 0), reverse=True)

for camp in sent_campaigns:
    name = camp.get('name', 'Unnamed')[:33]
    status = camp.get('status', 'unknown')

    opened = camp.get('opened', {})
    clicked = camp.get('clicked', {})

    open_rate = opened.get('rate', 0) * 100
    click_rate = clicked.get('rate', 0) * 100
    open_count = opened.get('count', 0)

    print(f"{name:<35} {status:<8} {open_rate:>6.1f}% {click_rate:>6.1f}% {open_count:>7}")

# Statistics
print("\n" + "="*70)
print("  STATISTIEKEN")
print("="*70)

avg_open = sum(c.get('opened', {}).get('rate', 0) for c in sent_campaigns) / len(sent_campaigns) * 100
avg_click = sum(c.get('clicked', {}).get('rate', 0) for c in sent_campaigns) / len(sent_campaigns) * 100

print(f"\nGemiddelde open rate:  {avg_open:.1f}%")
print(f"Gemiddelde click rate: {avg_click:.1f}%")

# Best and worst performers
best = max(sent_campaigns, key=lambda c: c.get('opened', {}).get('rate', 0))
worst = min(sent_campaigns, key=lambda c: c.get('opened', {}).get('rate', 0))

print(f"\n🔥 Best presterende campaign:")
print(f"   {best.get('name')}")
print(f"   Open: {best.get('opened', {}).get('rate', 0)*100:.1f}% | Click: {best.get('clicked', {}).get('rate', 0)*100:.1f}%")

print(f"\n❄️  Slechtst presterende campaign:")
print(f"   {worst.get('name')}")
print(f"   Open: {worst.get('opened', {}).get('rate', 0)*100:.1f}% | Click: {worst.get('clicked', {}).get('rate', 0)*100:.1f}%")

# Get account stats
print("\n[2/3] Account totalen...")
stats = api.get_account_stats()

print(f"\nTotaal verzonden:      {stats['sent_emails']:,}")
print(f"Totaal opens:          {stats['opens_count']:,} ({stats['open_rate']*100:.1f}%)")
print(f"Totaal clicks:         {stats['clicks_count']:,} ({stats['click_rate']*100:.1f}%)")
print(f"Bounces:               {stats['bounces_count']:,} ({stats['bounce_rate']*100:.1f}%)")
print(f"Unsubscribes:          {stats['unsubscribed']:,}")

# Top engaged subscribers
print("\n[3/3] Top 10 meest betrokken subscribers...")
subscribers = api.get_all_subscribers(limit=500)

# Sort by engagement (opens + clicks)
subscribers.sort(key=lambda s: s.get('opened', 0) + s.get('clicked', 0), reverse=True)

print("\n" + "-"*70)
print(f"{'Email':<35} {'Opens':>7} {'Clicks':>7} {'Sent':>7} {'Open%':>7}")
print("-"*70)

for i, sub in enumerate(subscribers[:10], 1):
    email = sub.get('email', 'N/A')[:33]
    opens = sub.get('opened', 0)
    clicks = sub.get('clicked', 0)
    sent = sub.get('sent', 0)

    open_rate = (opens / sent * 100) if sent > 0 else 0

    print(f"{email:<35} {opens:>7} {clicks:>7} {sent:>7} {open_rate:>6.1f}%")

print("\n" + "="*70)
print("  ANALYSE COMPLEET")
print("="*70 + "\n")

print("Inzichten:")
print("  - Focus op onderwerpen van best presterende campaigns")
print("  - Analyseer waarom slechtste campaign minder goed presteerde")
print("  - Top 10 subscribers zijn zeer betrokken - directe sales kans!")
print()
