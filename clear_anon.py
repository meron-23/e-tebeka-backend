from app.core.database import get_db

db = next(get_db())
anon_ref = db.collection('anonymous_searches')
docs = anon_ref.get()
print(f"Found {len(docs)} total anonymous searches.")
for d in docs:
    d.reference.delete()
print("Cleared anonymous searches.")
