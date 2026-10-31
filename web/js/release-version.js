const VERSION_RE = /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/;

export const isReleaseVersion = (value) => typeof value === 'string' && VERSION_RE.test(value);

export const resolveReleaseVersion = (runtimeVersion, frontendVersion) => {
  if (!isReleaseVersion(frontendVersion)) return null;
  if (isReleaseVersion(runtimeVersion) && runtimeVersion !== frontendVersion) {
    console.error(`Release mismatch: frontend ${frontendVersion}, backend ${runtimeVersion}`);
  }
  return frontendVersion;
};

export const renderReleaseVersion = (root, version) => {
  const valid = isReleaseVersion(version);
  root.querySelectorAll('[data-app-release-badge]').forEach((badge) => {
    badge.classList.toggle('release-version-invalid', !valid);
  });
  if (!valid) return;
  root.querySelectorAll('[data-app-release-number]').forEach((target) => {
    target.textContent = version;
  });
};
