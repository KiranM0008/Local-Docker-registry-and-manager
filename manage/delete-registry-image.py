import configparser
import requests
import subprocess
from datetime import datetime, timedelta, timezone
import re
import signal
import sys
import os
import logging

# Graceful interrupt handling
def handle_interrupt(signal, frame):
    logging.info("Script interrupted. Exiting gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_interrupt)

# Load configuration
config = configparser.ConfigParser(interpolation=None)
config.read('config.ini')

# Parse configuration
REGISTRY = config['DEFAULT']['REGISTRY']
DEFAULT_DAYS_THRESHOLD = int(config['DEFAULT']['DEFAULT_DAYS_THRESHOLD'])
DEFAULT_RECENT_IMAGES = int(config['DEFAULT']['DEFAULT_RECENT_IMAGES'])
EXCLUDE_REPOS = config['DEFAULT']['EXCLUDE_REPOS'].split(',')
REPOSITORY_PATH = config['DEFAULT'].get('REPOSITORY_PATH', "/var/lib/registry/docker/registry/v2/repositories")
LOG_FILE = config['DEFAULT'].get('LOG_FILE', 'docker_registry_cleanup.log')

SPECIFIC_RECENT_IMAGES = {
    key: int(value)
    for key, value in config.items('SPECIFIC_RECENT_IMAGES')
    if key not in config['DEFAULT']
}

SPECIFIC_DAYS_THRESHOLD = {
    key: int(value)
    for key, value in config.items('SPECIFIC_DAYS_THRESHOLD')
    if key not in config['DEFAULT']
}

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Utility functions
def fetch_repositories():
    response = requests.get(f"{REGISTRY}/v2/_catalog")
    response.raise_for_status()
    return response.json().get("repositories", [])

def fetch_image_tags(repository):
    response = requests.get(f"{REGISTRY}/v2/{repository}/tags/list")
    if response.status_code != 200:
        return []
    return response.json().get("tags", [])

def fetch_manifest_and_config_digest(repository, tag):
    """Fetch the manifest, Docker-Content-Digest, and config.digest."""
    url = f"{REGISTRY}/v2/{repository}/manifests/{tag}"
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        manifest = response.json()
        digest = response.headers.get("Docker-Content-Digest")
        config_digest = manifest.get("config", {}).get("digest")
        if not config_digest:
            return None, None, None
        return manifest, digest, config_digest
    return None, None, None

def fetch_creation_date(repository, config_digest):
    """Fetch the creation date of an image from the config blob."""
    url = f"{REGISTRY}/v2/{repository}/blobs/{config_digest}"
    response = requests.get(url)
    if response.status_code == 200:
        blob_data = response.json()
        created_date = blob_data.get("created")
        if created_date:
            fixed_date = re.sub(r'(?<=\+\d{2}):(\d)$', r'0\1', created_date[:-1])
            dt = datetime.fromisoformat(fixed_date)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # Ensure timezone awareness
    return None

def delete_image(repository, tag, digest):
    """Delete an image using its manifest digest."""
    url = f"{REGISTRY}/v2/{repository}/manifests/{digest}"
    response = requests.delete(url)
    if response.status_code == 202:
        logging.info(f"Deleted image: {repository}:{tag} - Digest: {digest}")

# Garbage Collection
def run_garbage_collection():
    """Run Docker Registry garbage collection without dry-run mode."""
    try:
        subprocess.run([
            "docker", "exec", "docker-registry", "registry",
            "garbage-collect", "/etc/docker/registry/config.yml"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        logging.info("Garbage collection completed successfully.")
    except subprocess.CalledProcessError:
        logging.error("Garbage collection failed.")

# Remove orphaned repositories
def remove_empty_repositories():
    """Check for repositories that have no tags left and ensure they are removed."""
    repositories = fetch_repositories()
    for repo in repositories:
        tags = fetch_image_tags(repo)
        if not tags:
            logging.info(f"Removing orphaned repository: {repo}")
            try:
                repo_path = os.path.join(REPOSITORY_PATH, repo)
                if os.path.exists(repo_path):
                    subprocess.run(["rm", "-rf", repo_path], check=True)
                    logging.info(f"Orphaned repository {repo} manually removed.")
            except Exception as e:
                logging.error(f"Failed to remove orphaned repository {repo}. {e}")

# Main logic
def process_repository(repository):
    if repository in EXCLUDE_REPOS:
        return

    tags = fetch_image_tags(repository)
    if not tags:
        logging.info(f"Skipping {repository} - No images found in this repository.")
        return

    recent_count = SPECIFIC_RECENT_IMAGES.get(repository, DEFAULT_RECENT_IMAGES)
    days_threshold = SPECIFIC_DAYS_THRESHOLD.get(repository, DEFAULT_DAYS_THRESHOLD)

    tag_details = []
    for tag in tags:
        manifest, digest, config_digest = fetch_manifest_and_config_digest(repository, tag)
        if not manifest or not digest or not config_digest:
            continue

        creation_date = fetch_creation_date(repository, config_digest)
        if not creation_date:
            continue

        tag_details.append((tag, creation_date, digest))

    if not tag_details:
        logging.info(f"Skipping {repository} - No eligible images for deletion.")
        return

    tag_details.sort(key=lambda x: x[1], reverse=True)
    recent_tags = {tag for tag, _, _ in tag_details[:recent_count]}
    threshold_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)

    deleted_count = 0
    for tag, creation_date, digest in tag_details:
        if tag in recent_tags:
            continue

        if creation_date < threshold_date:
            delete_image(repository, tag, digest)
            deleted_count += 1

    if deleted_count == 0:
        logging.info(f"Skipping {repository} - All images are within retention policy.")

# Entry point
def main():
    try:
        repositories = fetch_repositories()
        for repo in repositories:
            process_repository(repo)
        run_garbage_collection()
        remove_empty_repositories()
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    main()
