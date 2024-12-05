import logging
import subprocess
import os

from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException


from backend.open_webui.apps.git.main import (
    RepoInput,
    clone_or_update_repo,
    get_current_repo_ref,
    get_repo_metadata,
    update_repo,
    repo_store,
)

from open_webui.env import (
    GITHUB_PAT_TOKEN,
    SRC_LOG_LEVELS,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


router = APIRouter()


@router.post("/update-repo/{repo_id}")
async def manual_update_repo(repo_id: str):
    repo_metadata = get_repo_metadata(repo_id)
    if repo_metadata is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    try:
        update_repo(repo_metadata)
        return {"message": "Repository updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update repository: {e}")


@router.post("/sync-repo/")
async def add_repo_to_sync(input_data: RepoInput):
    # Validate URL
    parsed_url = urlparse(input_data.repo_url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise HTTPException(status_code=400, detail="Invalid repository URL.")

    # Use the repo URL and hash it for unique local storage
    repo_id = str(
        abs(hash(input_data.repo_url + input_data.branch))
    )  # Include branch in the hash

    # Create a directory for the repo if it doesn't exist
    cache_dir = f"./cache/{repo_id}"
    os.makedirs(cache_dir, exist_ok=True)

    # Use provided access token or default to GITHUB_PAT_TOKEN
    access_token = input_data.access_token or GITHUB_PAT_TOKEN

    # Save the repo details (you could use a database)
    repo_metadata = {
        "repo_url": input_data.repo_url,
        "access_token": access_token,
        "cache_dir": cache_dir,
        "branch": input_data.branch,
    }

    # Store in a data store; for this example, we'll use an in-memory dict
    repo_store[repo_id] = repo_metadata

    try:
        # Perform the initial clone
        clone_or_update_repo(repo_metadata)
        return {"message": "Repository added for sync", "repo_id": repo_id}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to clone repository: {e}")


@router.get("/repo-ref/{repo_id}")
async def get_repo_ref(repo_id: str):
    repo_metadata = get_repo_metadata(repo_id)
    if repo_metadata is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    try:
        current_ref = get_current_repo_ref(repo_metadata["cache_dir"])
        return {"current_ref": current_ref}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get repository ref: {e}"
        )
