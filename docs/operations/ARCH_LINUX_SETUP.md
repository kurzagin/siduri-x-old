# Arch Linux setup

Required local tools: Python 3.12+ (3.14 tested), Node.js/npm, and Git. Recommended future tools are `uv`, Docker or Podman Compose, PostgreSQL, OBS Studio, PipeWire, and headless VOICEVOX Engine. This host currently lacks the optional container, database, and OBS binaries, so the foundation’s no-dependency Python path is the reproducible baseline.

## Manual installer

From the repository root, review and run:

```bash
./scripts/install_arch_foundation.sh
```

The installer targets Arch Linux and uses `pacman` plus `sudo`. By default it installs Docker and Docker Compose; alternatives are:

```bash
./scripts/install_arch_foundation.sh --container-runtime podman
./scripts/install_arch_foundation.sh --container-runtime none
```

It installs `obs-studio` and its browser plugin, PostgreSQL, PipeWire, `uv`, Node/npm, and development tools. PostgreSQL is initialized only when its data directory is empty and then enabled as a system service. Docker is enabled as a system service and the user is added to its group; log out and back in afterward. The script pulls the pinned CPU VOICEVOX Engine image but does not start containers or the orchestrator.

The Docker group grants root-level privileges to members, so use the Podman option if that tradeoff is unacceptable. The script does not install unofficial TikTok tooling, create cloud accounts, configure OAuth, or write production secrets.
