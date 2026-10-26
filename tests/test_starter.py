import json
from pathlib import Path
import shutil
import tempfile
import unittest
from engine import Engine
ROOT = Path(__file__).resolve().parents[1]
class StarterSettingsTests(unittest.TestCase):
 def test_fresh_install_loads_starter(self):
  with tempfile.TemporaryDirectory(dir=ROOT) as folder:
   root=Path(folder);shutil.copyfile(ROOT/'starter-settings.json',root/'starter-settings.json')
   settings=root/'settings-zc95-v3.json';engine=Engine(settings=settings)
   data=json.loads((root/'starter-settings.json').read_text())
   self.assertEqual(engine.config,data['channels']);self.assertEqual(engine.volume,data['volume'])
   self.assertEqual(engine.listener_errors,[]);self.assertFalse(engine.demo);self.assertFalse(settings.exists())
 def test_existing_settings_win_and_stay_unchanged(self):
  with tempfile.TemporaryDirectory(dir=ROOT) as folder:
   root=Path(folder);shutil.copyfile(ROOT/'starter-settings.json',root/'starter-settings.json')
   data=json.loads((root/'starter-settings.json').read_text());data['channels'][0]['power_max']=51
   settings=root/'settings-zc95-v3.json';settings.write_text(json.dumps(data));before=settings.read_bytes()
   engine=Engine(settings=settings)
   self.assertEqual(engine.config[0]['power_max'],51);self.assertEqual(settings.read_bytes(),before)
   self.assertEqual(engine.listener_errors,[])
if __name__=='__main__':unittest.main()
