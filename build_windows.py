"""Build a portable Windows folder using PyInstaller 6.22.3."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ASSETS = ('index.html', 'bluetooth.js', 'wifi.js', 'patterns.js', 'curves.js',
          'ribbon.js', 'editor.js', 'vector_wifi.lua')

def main():
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir',
               '--console', '--name', 'Vector-ZC95', '--noupx',
               '--distpath', str(ROOT/'windows-dist'),
               '--workpath', str(ROOT/'windows-build'/'work'),
               '--specpath', str(ROOT/'windows-build')]
    for name in ASSETS:
        command += ['--add-data', str(ROOT/name)+':.']
    command += [str(ROOT/'windows_launcher.py')]
    subprocess.run(command, cwd=ROOT, check=True)
    output = ROOT/'windows-dist'/'Vector-ZC95'
    for source in ROOT.iterdir():
        if source.is_file() and (source.suffix in ('.py','.js','.html','.lua','.md','.bat') or source.name in ('LICENSE','starter-settings.json','START_HERE.txt','.gitignore')):
            shutil.copyfile(source, output/source.name)
    shutil.copyfile(Path(sys.base_prefix)/'LICENSE.txt', output/'_internal'/'PYTHON_LICENSE.txt')
    print('Executable:', output/'Vector-ZC95.exe')
    print('Keep the _internal folder with the executable. Include starter-settings.json beside it.')

if __name__ == '__main__':
    main()
