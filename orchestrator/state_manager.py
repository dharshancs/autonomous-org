import os
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def load_state():
    response = supabase.table("system_state").select("*").eq("id", 1).execute()
    return response.data[0]

def save_state(stage, repo_url=None):
    update_data = {"stage": stage}
    if repo_url:
        update_data["repo_url"] = repo_url
    supabase.table("system_state").update(update_data).eq("id", 1).execute()
