from state_manager import load_state, save_state
from github_tool import create_repo

def run():
    state = load_state()
    stage = state["stage"]

    if stage == "IDEATION":
        print("Moving to BUILDING")
        save_state("BUILDING")

    elif stage == "BUILDING":
        print("Creating repo...")
        repo_name = create_repo("auto-saas-product")
        save_state("DONE", repo_name)

    elif stage == "DONE":
        print("System complete.")

if __name__ == "__main__":
    run()
