#!/usr/bin/env python3
"""Diagnose script om te checken waar het probleem zit."""
import os
import time
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

print("=" * 50)
print("CONTRACT CHECKER - DIAGNOSE")
print("=" * 50)

# Test 1: Ollama bereikbaar?
print("\n[1] Test Ollama connectie...")
try:
    start = time.time()
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    elapsed = time.time() - start
    if response.status_code == 200:
        models = response.json().get("models", [])
        print(f"    ✅ Ollama draait ({elapsed:.2f}s)")
        print(f"    Modellen: {[m['name'] for m in models]}")
    else:
        print(f"    ❌ Ollama geeft status {response.status_code}")
except Exception as e:
    print(f"    ❌ Ollama niet bereikbaar: {e}")

# Test 2: Simpele Ollama inference
print("\n[2] Test Ollama inference (simpele vraag)...")
try:
    start = time.time()
    payload = {
        "model": "mistral",
        "messages": [{"role": "user", "content": "Zeg alleen 'OK'"}],
        "stream": False,
        "options": {"temperature": 0.0}
    }
    response = requests.post(
        "http://localhost:11434/api/chat",
        json=payload,
        timeout=60
    )
    elapsed = time.time() - start
    if response.status_code == 200:
        answer = response.json()["message"]["content"]
        print(f"    ✅ Inference werkt ({elapsed:.2f}s)")
        print(f"    Antwoord: {answer[:50]}")
    else:
        print(f"    ❌ Inference fout: {response.status_code}")
except requests.exceptions.Timeout:
    print(f"    ❌ TIMEOUT na 60 seconden - model te langzaam of crashed")
except Exception as e:
    print(f"    ❌ Inference fout: {e}")

# Test 3: Database connectie
print("\n[3] Test database connectie...")
try:
    db_url = (
        f"postgresql+psycopg://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', '1210')}"
    )
    engine = create_engine(db_url)
    start = time.time()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        result.fetchone()
    elapsed = time.time() - start
    print(f"    ✅ Database bereikbaar ({elapsed:.2f}s)")
except Exception as e:
    print(f"    ❌ Database fout: {e}")

# Test 4: WerkbonKetenService
print("\n[4] Test WerkbonKetenService...")
try:
    from werkbon_keten_service import WerkbonKetenService, WerkbonVerhaalBuilder

    service = WerkbonKetenService()

    # Haal een werkbon key op
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT w."HoofdwerkbonDocumentKey"
            FROM werkbonnen."Werkbonnen" w
            JOIN stam."Relaties" r ON r."RelatieKey" = w."DebiteurRelatieKey"
            JOIN contract_checker.contract_relatie cr ON cr.client_id = r."Relatie Code"
            WHERE w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
            LIMIT 1
        """))
        row = result.fetchone()
        if row:
            hoofdwerkbon_key = row[0]
            print(f"    Test met werkbon key: {hoofdwerkbon_key}")

            start = time.time()
            keten = service.get_werkbon_keten(
                hoofdwerkbon_key,
                include_kosten_details=True,
                include_opvolgingen=True,
                include_oplossingen=True
            )
            elapsed = time.time() - start

            if keten:
                print(f"    ✅ Keten geladen ({elapsed:.2f}s)")
                print(f"    - {keten.aantal_werkbonnen} werkbonnen")
                print(f"    - {keten.aantal_paragrafen} paragrafen")

                # Bouw verhaal
                builder = WerkbonVerhaalBuilder()
                start = time.time()
                verhaal = builder.build_verhaal(keten)
                elapsed = time.time() - start
                print(f"    ✅ Verhaal gebouwd ({elapsed:.2f}s)")
                print(f"    - {len(verhaal)} karakters")
            else:
                print(f"    ❌ Geen keten gevonden")
        else:
            print(f"    ❌ Geen werkbon gevonden met contract")

    service.close()
except Exception as e:
    print(f"    ❌ WerkbonKetenService fout: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Volledige classificatie (als alles werkt)
print("\n[5] Test volledige classificatie pipeline...")
try:
    # Haal contract op
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT content FROM contract_checker.contracts WHERE active = true LIMIT 1
        """))
        row = result.fetchone()
        if row:
            contract_text = row[0][:5000]  # Korter voor test
            print(f"    Contract: {len(contract_text)} karakters (afgekapt)")

            # Simpele classificatie prompt
            system_prompt = "Je bent een contract analist. Antwoord met JSON: {\"classificatie\": \"JA\", \"confidence\": 0.9}"
            user_message = f"Contract: {contract_text[:1000]}...\n\nWerkbon: Test storing CV ketel.\n\nClassificeer."

            print("    Ollama aanroepen (kan 1-2 minuten duren op CPU)...")
            start = time.time()

            payload = {
                "model": "mistral",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "stream": False,
                "options": {"temperature": 0.0}
            }

            response = requests.post(
                "http://localhost:11434/api/chat",
                json=payload,
                timeout=180  # 3 minuten max
            )
            elapsed = time.time() - start

            if response.status_code == 200:
                answer = response.json()["message"]["content"]
                print(f"    ✅ Classificatie werkt ({elapsed:.2f}s)")
                print(f"    Antwoord: {answer[:200]}")
            else:
                print(f"    ❌ Classificatie fout: {response.status_code}")
        else:
            print(f"    ❌ Geen contract in database")

except requests.exceptions.Timeout:
    print(f"    ❌ TIMEOUT - classificatie duurt te lang (>3 min)")
    print(f"    → Dit is het probleem! Mistral is te langzaam op jouw hardware.")
    print(f"    → Oplossingen:")
    print(f"       1. Gebruik een cloud API (Anthropic/OpenAI)")
    print(f"       2. Gebruik een sneller model: ollama pull phi3")
    print(f"       3. Draai op een machine met GPU")
except Exception as e:
    print(f"    ❌ Fout: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("DIAGNOSE COMPLEET")
print("=" * 50)
