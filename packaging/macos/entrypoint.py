import sys
from antigravity_migrator.cli import app

if __name__ == "__main__":
    if any(arg.startswith("-psn_") for arg in sys.argv):
        sys.argv = [arg for arg in sys.argv if not arg.startswith("-psn_")]
    app()
