"""Deploy the locally checked-out commit after its trusted CI publication."""

import base64
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


REPOSITORY = "sonecjak/laba0oblaka"
API = f"https://api.github.com/repos/{REPOSITORY}"
IMAGE = f"ghcr.io/{REPOSITORY}"
COMPOSE_FILE = Path(__file__).with_name("compose.yml").resolve()


def github(path, token=None, data=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        API + path,
        data=None if data is None else json.dumps(data).encode(),
        headers=headers,
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def wait_for_request(commit, token):
    deadline = time.monotonic() + 2400
    print(f"Waiting for the CI deploy job for {commit}\n", flush=True)
    while time.monotonic() < deadline:
        try:
            statuses = github(f"/statuses/{commit}", token)
        except URLError as error:
            if getattr(error, "code", None) not in {404, 422}:
                raise
            # The local commit can be unknown to GitHub until it is pushed.
            statuses = []

        seen_contexts = set()
        for status in statuses:
            context = status["context"]
            if context in seen_contexts:
                continue
            seen_contexts.add(context)
            digest = status.get("description") or ""
            run_match = re.fullmatch(r"lab3/mac-deploy/([0-9]+)/([0-9]+)", context)
            if (
                run_match
                and status["state"] == "pending"
                and (status.get("creator") or {}).get("login") == "github-actions[bot]"
                and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
            ):
                run_id, attempt = run_match.groups()
                run = github(f"/actions/runs/{run_id}")
                if (
                    run["status"] == "in_progress"
                    and run["event"] == "push"
                    and run["head_branch"] == "main"
                    and run["head_sha"] == commit
                    and str(run["run_attempt"]) == attempt
                    and run["path"].split("@", 1)[0] == ".github/workflows/ci.yml"
                ):
                    return context, digest
        time.sleep(10)
    raise RuntimeError("No deploy request arrived from CI.")


def deploy(username, token, password, digest):
    # Use the current local engine even with temporary registry credentials.
    docker_host = os.environ.get("DOCKER_HOST") or subprocess.check_output(
        ["docker", "context", "inspect", "--format", '{{ (index .Endpoints "docker").Host }}'],
        text=True,
    ).strip()
    if not docker_host.startswith("unix://"):
        raise RuntimeError("Select the local Docker Desktop context before deployment.")

    with tempfile.TemporaryDirectory() as config:
        credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
        config_file = Path(config) / "config.json"
        config_file.touch(mode=0o600)
        config_file.write_text(json.dumps({"auths": {"ghcr.io": {"auth": credentials}}}))
        env = os.environ.copy()
        env.pop("DOCKER_CONTEXT", None)
        env.update(
            DOCKER_HOST=docker_host,
            DOCKER_CONFIG=config,
            DB_PASSWORD=password,
            NOTES_IMAGE=f"{IMAGE}@{digest}",
            NOTES_PLATFORM="linux/amd64",
        )
        compose = [
            "docker", "compose", "-p", "notes-lab3-local", "-f", str(COMPOSE_FILE),
        ]
        subprocess.run([*compose, "pull", "backend"], env=env, check=True)
        subprocess.run(
            [*compose, "up", "-d", "--no-build", "--wait", "--wait-timeout", "180"],
            env=env,
            check=True,
        )
        subprocess.run([*compose, "ps"], env=env, check=True)

    response = subprocess.check_output(
        ["curl", "-fsS", "-i", "--max-time", "10", "http://127.0.0.1:18080/api/health"],
        text=True,
    )
    print(response, end="" if response.endswith("\n") else "\n", flush=True)
    headers, _, body = response.partition("\n\n")
    status_code = headers.splitlines()[0].split()[1]
    health = json.loads(body)
    if status_code != "200" or health.get("status") != "ok" or health.get("backend") != "lab3":
        raise RuntimeError("Unexpected response from /api/health.")
    return f"HTTP {status_code} /api/health {body.strip()}"


def main():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    username = input("GitHub login: ").strip()
    token = getpass.getpass("GitHub token (input hidden): ").strip()
    password = getpass.getpass("Password of the local PostgreSQL volume (input hidden): ")
    if not all((username, token, password)):
        raise SystemExit("GitHub login, token and PostgreSQL password are required.")
    context, digest = wait_for_request(commit, token)
    if github("/branches/main", token)["commit"]["sha"] != commit:
        # A newer push superseded this request.
        github(
            f"/statuses/{commit}", token,
            {"state": "failure", "context": context, "description": "Commit is no longer main HEAD"},
        )
        raise SystemExit("This commit is no longer the tip of main.")
    try:
        health = deploy(username, token, password, digest)
    except (subprocess.CalledProcessError, ValueError, RuntimeError, OSError) as error:
        github(
            f"/statuses/{commit}", token,
            {"state": "failure", "context": context, "description": "Deploy or curl failed on the Mac"},
        )
        raise SystemExit(f"Deploy or curl failed on the Mac: {type(error).__name__}") from error
    github(f"/statuses/{commit}", token, {"state": "success", "context": context, "description": health})
    print(f"DEPLOYED_TAG={IMAGE}:{commit}\nResult sent to GitHub.", flush=True)


if __name__ == "__main__":
    main()
