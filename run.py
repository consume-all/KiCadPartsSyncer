# Dev launcher so you can run without installing the package
import sys
from pathlib import Path
here = Path(__file__).parent
src = here / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))
from KiCadPartsSyncer.app.main import main
if __name__ == "__main__":
    main()
