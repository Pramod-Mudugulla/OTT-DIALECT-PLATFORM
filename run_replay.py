"""Convenience runner script for One User, One Agent replay."""
import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from submission.src.cli import run_full_replay

if __name__ == "__main__":
    run_full_replay()
