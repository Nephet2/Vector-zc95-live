"""Windows executable entry point; no device output is enabled at startup."""
import json
from pathlib import Path
import sys
import traceback
import server

ASSETS = ('index.html', 'bluetooth.js', 'wifi.js', 'patterns.js', 'curves.js',
          'ribbon.js', 'editor.js', 'vector_wifi.lua')

def main():
    if '--self-test' in sys.argv:
        for name in ASSETS:
            if not (server.ROOT/name).is_file():
                raise RuntimeError('Missing packaged asset: '+name)
        from engine import Engine
        engine = Engine(server.APP_ROOT/'settings-zc95-v3.json')
        if engine.listener_errors:
            raise RuntimeError('; '.join(engine.listener_errors))
        if not (server.APP_ROOT/'starter-settings.json').is_file():
            raise RuntimeError('Starter preset must be beside the executable')
        print(json.dumps({'version':'0.9.2','frozen':bool(getattr(sys,'frozen',False)),
                          'assets':len(ASSETS),'channels':len(engine.config),
                          'settings_folder':str(server.APP_ROOT),'output_started':False}))
        return 0
    return server.main()

if __name__ == '__main__':
    try:
        result = main()
    except Exception:
        traceback.print_exc()
        result = 1
    if result and '--self-test' not in sys.argv and '--no-browser' not in sys.argv:
        try: input('\nVector could not start. Press Enter to close this window...')
        except (EOFError, OSError): pass
    raise SystemExit(result)
