# Release process

1. Review the diff for secrets, personal data, raw captures, unofficial clients, and unintended public actions.
2. Run the Python test suite, TypeScript typecheck/build, and `git diff --check`.
3. Verify the orchestrator starts on loopback with platform workers disabled by default.
4. Record external verification status for OBS, VOICEVOX, YouTube, and Twitch.
5. Release only after operator approval of credentialed or public-action changes; retain audit evidence and rollback instructions.
