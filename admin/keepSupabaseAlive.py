from supabase import create_client
import os

client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)

response = (
    client.table("athletes")
    .select("name")
    .limit(1)
    .execute()
)

print("Supabase ping successful!")
print(response.data)
