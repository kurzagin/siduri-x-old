#!/usr/bin/env bash
set -euo pipefail

# Siduri Phase 0/1 host setup. This script is intentionally not run by Codex.
# It installs local tooling only; it does not deploy Siduri or request secrets.

usage() {
  cat <<'EOF'
Usage: scripts/install_arch_foundation.sh [--container-runtime docker|podman|none]

Installs the Arch Linux tools needed for Siduri's local foundation:
  Python, uv, Node/npm, Git, PostgreSQL, OBS Studio, PipeWire, and Docker or Podman.

The script initializes/starts PostgreSQL and the selected container service.
It pulls the VOICEVOX Engine image but does not start the Siduri Compose stack.
Log out/in after the script if it adds your user to the docker group.
EOF
}

runtime="${SIDURI_CONTAINER_RUNTIME:-docker}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --container-runtime)
      [[ $# -ge 2 ]] || { echo "Missing value for --container-runtime" >&2; exit 2; }
      runtime="$2"
      shift 2
      ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ "$(uname -s)" == "Linux" ]] || { echo "This installer targets Arch Linux." >&2; exit 1; }
[[ -r /etc/arch-release ]] || { echo "Arch Linux was not detected (/etc/arch-release missing)." >&2; exit 1; }
command -v pacman >/dev/null || { echo "pacman is required." >&2; exit 1; }
command -v sudo >/dev/null || { echo "sudo is required." >&2; exit 1; }
[[ "$runtime" == docker || "$runtime" == podman || "$runtime" == none ]] || {
  echo "Container runtime must be docker, podman, or none." >&2
  exit 2
}

echo "==> Updating Arch package databases and system packages"
sudo pacman -Syu --needed

packages=(
  base-devel curl git python python-pip uv nodejs npm
  postgresql obs-studio obs-studio-plugin-browser
  pipewire pipewire-pulse wireplumber
)
if [[ "$runtime" == docker ]]; then
  packages+=(docker docker-compose)
elif [[ "$runtime" == podman ]]; then
  packages+=(podman podman-compose)
fi

echo "==> Installing: ${packages[*]}"
sudo pacman -S --needed "${packages[@]}"

echo "==> Initializing PostgreSQL if needed"
if [[ ! -f /var/lib/postgres/data/PG_VERSION ]]; then
  sudo install -d -o postgres -g postgres -m 700 /var/lib/postgres/data
  sudo -u postgres initdb -D /var/lib/postgres/data
fi
sudo systemctl enable --now postgresql.service

echo "==> Creating the local Siduri PostgreSQL role/database if absent"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='siduri'" | grep -q 1; then
  sudo -u postgres createuser --login siduri
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='siduri'" | grep -q 1; then
  sudo -u postgres createdb --owner=siduri siduri
fi

if [[ "$runtime" == docker ]]; then
  echo "==> Enabling Docker"
  sudo systemctl enable --now docker.service
  sudo groupadd --force docker
  if ! id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
    sudo usermod -aG docker "$USER"
    echo "    Added $USER to the docker group; log out/in before using Docker without sudo."
  fi
  echo "==> Pulling VOICEVOX Engine image (not starting it)"
  sudo docker compose --profile optional pull voicevox
elif [[ "$runtime" == podman ]]; then
  echo "==> Podman is installed. Compose commands use podman-compose."
  echo "    Pull the VOICEVOX image manually when ready: podman pull voicevox/voicevox_engine:cpu-ubuntu20.04-latest"
else
  echo "==> Skipping container runtime and VOICEVOX image pull"
fi

cat <<'EOF'

==> Foundation setup complete
Next steps from the Siduri repository:
  python -m unittest discover -s tests -v
  npm install
  npm run typecheck
  npm run build
  python -m apps.orchestrator.src.siduri_orchestrator.server

To start PostgreSQL and VOICEVOX later with Docker:
  docker compose --profile optional up -d postgres voicevox

No cloud credentials, OAuth, platform clients, or production deployment were configured.
EOF
