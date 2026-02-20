"""Quick test script."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

print("Starting test...")

try:
    from pipedrive_api import PipedriveAPI
    print("Import successful!")

    api = PipedriveAPI()
    print("API initialized!")

    persons = api.get_persons(limit=5)
    print(f"Got {len(persons)} persons")

    if persons:
        print(f"First person: {persons[0].get('name')}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
