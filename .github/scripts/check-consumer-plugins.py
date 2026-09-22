"""Import shipped consumer plugins using the installed foundation loader."""
import importlib
from pathlib import Path
import sys
from dwho.classes.libloader import DwhoLibLoader

name = sys.argv[1]
package = importlib.import_module(name)
root = Path(package.__file__).parent
for kind in ('plugins', 'modules', 'filters'):
    directory = root/kind
    if not directory.is_dir():
        continue
    modules = DwhoLibLoader.load_dir(name + '.' + kind, str(directory))
    assert modules, directory
    print(name, kind, len(modules))
