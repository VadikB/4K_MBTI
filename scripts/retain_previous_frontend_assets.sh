#!/bin/sh
set -eu

current_dir="${1:?Current frontend asset directory is required}"
previous_dir="${2:?Previous frontend asset directory is required}"
retention_days="${3:-14}"

if [ ! -d "$current_dir" ]; then
  echo "Current frontend asset directory does not exist: $current_dir" >&2
  exit 1
fi
if [ ! -d "$previous_dir" ]; then
  echo "Previous frontend asset directory does not exist: $previous_dir" >&2
  exit 1
fi
case "$retention_days" in
  ''|*[!0-9]*)
    echo "Frontend asset retention must be a non-negative integer." >&2
    exit 1
    ;;
esac

# Copy only files that disappeared from the new build. An explicit existence
# check is portable between the BSD tools used on macOS and GNU tools on test.
find "$previous_dir" -maxdepth 1 -type f -print | while IFS= read -r previous_file; do
  filename="${previous_file##*/}"
  if [ ! -e "$current_dir/$filename" ]; then
    cp -p "$previous_file" "$current_dir/$filename"
  fi
done

find "$current_dir" \
  -maxdepth 1 \
  -type f \
  -mtime "+$retention_days" \
  ! -name 'main.js' \
  -delete
