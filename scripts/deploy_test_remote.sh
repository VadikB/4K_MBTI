#!/bin/sh
set -eu

project_dir="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
case "$project_dir" in
  /home/user1/projects/Agent4K-Test|/home/user1/projects/4K-Mbti-Test|/home/vadim_bogachev/projects/Agent4K-Test) ;;
  *) echo "Refusing deployment outside the configured test checkouts" >&2; exit 1 ;;
esac
deploy_commit="${1:-}"
if [ -n "$deploy_commit" ]; then
  case "$deploy_commit" in
    *[!0-9a-f]*) echo "Invalid deploy commit" >&2; exit 1 ;;
  esac
  test "${#deploy_commit}" -eq 40 || { echo "Invalid deploy commit" >&2; exit 1; }
fi
service_name="agent4k-test.service"
health_url="http://127.0.0.1:8002/users/version"
asset_url="http://127.0.0.1:8002/web/dist/main.js"

cd "$project_dir"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Refusing deployment with tracked local changes" >&2
  exit 1
fi
if [ -n "$deploy_commit" ]; then
  git merge-base --is-ancestor "$deploy_commit" origin/main
  git merge-base --is-ancestor HEAD "$deploy_commit" || {
    echo "Refusing a deploy commit behind or divergent from the current checkout" >&2
    exit 1
  }
fi
previous_commit="$(git rev-parse HEAD)"
frontend_asset_backup_dir="$(mktemp -d)"
public_origin_backup="$(mktemp)"
had_public_origin=0
if [ -f .public-origin.json ]; then
  cp .public-origin.json "$public_origin_backup"
  had_public_origin=1
fi

if [ -d web/dist ]; then
  cp -a web/dist/. "$frontend_asset_backup_dir/"
fi

cleanup_frontend_asset_backup() {
  rm -rf "$frontend_asset_backup_dir"
  rm -f "$public_origin_backup"
}

rollback() {
  echo "Test deployment failed; rolling back to $previous_commit" >&2
  if [ "$had_public_origin" -eq 1 ]; then
    cp "$public_origin_backup" .public-origin.json
  else
    rm -f "$project_dir/.public-origin.json"
  fi
  git restore --worktree web/dist
  git clean -fd web/dist
  git switch --detach "$previous_commit"
  npm ci --include=dev
  npm run build:web
  sudo -n systemctl restart "$service_name"
  cleanup_frontend_asset_backup
  exit 1
}

trap rollback HUP INT TERM

# Old versions of the build did not clean hashed chunks before rebuilding.
git clean -fd web/dist || rollback
git switch main || rollback
if [ -n "$deploy_commit" ]; then
  git merge --ff-only "$deploy_commit" || rollback
  test "$(git rev-parse HEAD)" = "$deploy_commit" || rollback
else
  git pull --ff-only origin main || rollback
fi

.venv/bin/python scripts/configure_public_origin.py \
  --origin https://test.4k-assistant.ru --root "$project_dir" || rollback

# Reuse the CPU/ML runtime already installed on the server. Install only direct
# project requirements so pip does not resolve and download a new CUDA stack.
.venv/bin/pip install --no-deps -r requirements.txt || rollback

npm ci --include=dev || rollback
npm run build:web || rollback

# An already open browser tab can still execute the previous in-memory
# entrypoint after a deployment. Keep its content-addressed chunks available
# during the transition, but never replace files from the new build.
sh scripts/retain_previous_frontend_assets.sh \
  web/dist \
  "$frontend_asset_backup_dir" \
  14 || rollback

sudo -n systemctl restart "$service_name" || rollback

attempt=0
until curl -fsS "$health_url" >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    rollback
  fi
  sleep 2
done

expected_version="$(.venv/bin/python -c 'import tomllib; from pathlib import Path; print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])')"
actual_version="$(curl -fsS "$health_url" | .venv/bin/python -c 'import json, sys; print(json.load(sys.stdin)["version"])')" || rollback
if [ "$actual_version" != "$expected_version" ]; then
  echo "Backend release does not match checked-out product release" >&2
  rollback
fi
actual_origin="$(curl -fsS "$health_url" | .venv/bin/python -c 'import json, sys; print(json.load(sys.stdin)["public_origin"])')" || rollback
if [ "$actual_origin" != "https://test.4k-assistant.ru" ]; then
  echo "Backend effective public origin does not match test deployment" >&2
  rollback
fi
curl -fsS "$asset_url" | cmp -s - web/dist/main.js || rollback

deployed_commit="$(git rev-parse HEAD)"
cleanup_frontend_asset_backup
echo "Test deployment completed: $deployed_commit"
