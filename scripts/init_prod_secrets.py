#!/usr/bin/env python3
"""Initialize per-host Compose secrets without printing values or rotating existing keys."""
import argparse
import os
from pathlib import Path
import secrets

MODEL_KEYS = ('extractor_api_key', 'laya_api_key', 'kev_api_key', 'decision_api_key')


def initialize(directory: Path, role: str):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    if role == 'app':
        missing = [key for key in MODEL_KEYS if not (directory / key).is_file() or not (directory / key).read_text().strip()]
        if missing:
            raise ValueError(f"Copy the GPU host's model keys first; missing files: {', '.join(missing)}")
        names = ('postgres_password',)
    else:
        names = (*MODEL_KEYS, 'llm_api_key')
    for name in names:
        path = directory / name
        if not path.exists():
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, 'w') as output:
                output.write(secrets.token_hex(32) + '\n')
        if not path.read_text().strip():
            raise ValueError(f'Empty secret: {name}. Restore it before starting services.')
    # Compose mounts each file separately. The containers run as UID 10001; the host
    # directory stays 0700 so other host users cannot traverse it or read these files.
    for name in (*MODEL_KEYS, *names):
        (directory / name).chmod(0o444)
    print(f'{role}: secret files ready in {directory}. Existing values preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', required=True, choices=('gpu', 'app'))
    parser.add_argument('--directory', type=Path, default=Path('.secrets-prod'))
    args = parser.parse_args()
    try:
        initialize(args.directory, args.role)
    except ValueError as error:
        parser.exit(1, str(error) + '\n')
