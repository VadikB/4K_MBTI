#!/bin/sh
set -eu

project_dir="/home/user1/projects/4K-Mbti-Test"
service_name="agent4k-mbti-test.service"
health_url="http://127.0.0.1:8002/users/version"

cd "$project_dir"

previous_commit="$(git rev-parse HEAD)"

rollback() {
  echo "Test deployment failed; rolling back to $previous_commit" >&2
  git restore --worktree web/dist
  git clean -fd web/dist
  git switch --detach "$previous_commit"
  npm ci
  npm run build:web
  sudo -n systemctl restart "$service_name"
  exit 1
}

trap rollback HUP INT TERM

# Old versions of the build did not clean hashed chunks before rebuilding.
git clean -fd web/dist
git switch main
git pull --ff-only origin main || rollback

# Reuse the CPU/ML runtime already installed on the server. Install only direct
# project requirements so pip does not resolve and download a new CUDA stack.
.venv/bin/pip install --no-deps -r requirements.txt || rollback

npm ci || rollback
npm run build:web || rollback

sudo -n systemctl restart "$service_name" || rollback

attempt=0
until curl -fsS "$health_url" >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    rollback
  fi
  sleep 2
done

deployed_commit="$(git rev-parse HEAD)"
echo "Test deployment completed: $deployed_commit"
