#!/bin/bash
# Shim: the rules file is owned by rules_file.py; prints "created: <path>" or "exists: <path>".
exec python3 "$(dirname "$0")/rules_file.py" ensure "$@"
