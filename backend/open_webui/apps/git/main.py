import os
import subprocess

from apscheduler.schedulers.background import BackgroundScheduler
from pydantic import BaseModel
from urllib.parse import urlparse


from open_webui.config import GITHUB_SYNC_INTERVAL, GITHUB_SYNC_AUTO_UPDATE


class RepoInput(BaseModel):
    repo_url: str
    access_token: str = None  # Optional if the repo is public
    branch: str = "main"  # Default branch, can be tag or specific ref


def get_current_repo_ref(cache_dir):
    result = subprocess.run(
        ["git", "-C", cache_dir, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    current_ref = result.stdout.strip()
    return current_ref


def get_remote_repo_latest_ref(repo_url, access_token=None, branch="master"):
    if access_token:
        parsed_url = urlparse(repo_url)
        netloc_with_auth = f"{access_token}@{parsed_url.netloc}"
        repo_url_with_auth = parsed_url._replace(netloc=netloc_with_auth).geturl()
    else:
        repo_url_with_auth = repo_url

    result = subprocess.run(
        ["git", "ls-remote", repo_url_with_auth, branch],
        capture_output=True,
        text=True,
        check=True,
    )
    latest_ref = result.stdout.split()[0]
    return latest_ref


def is_update_available(repo_metadata):
    current_ref = get_current_repo_ref(repo_metadata["cache_dir"])
    latest_ref = get_remote_repo_latest_ref(
        repo_metadata["repo_url"],
        access_token=repo_metadata.get("access_token"),
        branch=repo_metadata.get("branch", "master"),
    )
    return current_ref != latest_ref


def update_repo(repo_metadata):
    cache_dir = repo_metadata["cache_dir"]
    branch = repo_metadata.get("branch", "master")
    subprocess.run(
        ["git", "-C", cache_dir, "pull", "--depth", "1", "origin", branch], check=True
    )


def clone_or_update_repo(metadata):
    repo_url = metadata["repo_url"]
    access_token = metadata.get("access_token")
    cache_dir = metadata["cache_dir"]
    branch = metadata.get("branch", "master")  # Default branch

    if access_token:
        parsed_url = urlparse(repo_url)
        netloc_with_auth = f"{access_token}@{parsed_url.netloc}"
        repo_url_with_auth = parsed_url._replace(netloc=netloc_with_auth).geturl()
    else:
        repo_url_with_auth = repo_url

    if not os.listdir(cache_dir):
        # Clone the repo if it's not already cloned
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                branch,
                repo_url_with_auth,
                cache_dir,
            ],
            check=True,
        )
    else:
        # Update the shallow clone with a fetch
        subprocess.run(
            ["git", "-C", cache_dir, "fetch", "--depth", "1", "origin", branch],
            check=True,
        )


repo_store = {}


def get_repo_metadata(repo_id):
    return repo_store.get(repo_id)


def get_all_tracked_repos():
    return repo_store.values()


scheduler = BackgroundScheduler()
scheduler.start()


@scheduler.scheduled_job("interval", hours=GITHUB_SYNC_INTERVAL)
def check_for_repo_updates():
    # Fetch tracked repositories (from a database or in-memory store)
    for repo_metadata in get_all_tracked_repos():
        try:
            if is_update_available(repo_metadata):
                if GITHUB_SYNC_AUTO_UPDATE:
                    update_repo(repo_metadata)
                    print(f"Repository '{repo_metadata['repo_url']}' updated.")
                else:
                    print(
                        f"Update available for '{repo_metadata['repo_url']}', but auto-update is disabled."
                    )
            else:
                print(f"No updates for '{repo_metadata['repo_url']}'.")
        except Exception as e:
            print(f"Error checking updates for '{repo_metadata['repo_url']}': {e}")
