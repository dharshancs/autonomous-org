import os
import requests

TOKEN = os.environ["PERSONAL_GITHUB_TOKEN"]
OWNER = os.environ["REPO_OWNER"]

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

def create_repo(name):
    r = requests.post(
        "https://api.github.com/user/repos",
        headers=headers,
        json={"name": name, "private": False}
    )
    r.raise_for_status()
    return r.json()["name"]
