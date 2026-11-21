import unittest

from engine import Engine, defaults


class PowerSmoothingTests(unittest.TestCase):
    def replay(self, window, buffered=True):
        now = 0.
        engine = Engine(clock=lambda: now)
        rows = defaults()
        rows[0].update(power_mode='vector', power_min=10, power_max=80,
                       power_rest_enabled=True, power_rest=30, power_ramp_s=.5,
                       power_smoothing_s=window)
        engine.configure(dict(channels=rows, crossover=engine.crossover,
                              volume=dict(enabled=buffered, delay_s=2, ratio=20)))
        frames = []
        for tick in range(261):
            now = tick / 20
            if tick % 5 == 0 and now < 10:
                position = 8500 if 2 <= now < 6 and tick % 10 == 5 else 1500
                engine.ingest(f'L0{position:04d}I250', 'UDP')
            frames.append(engine.snapshot()['channels'][0])
        return frames

    def test_rolling_power_smooths_rest_transition_before_curve(self):
        raw, smooth = self.replay(0), self.replay(4)
        for before, after in zip(raw, smooth):
            self.assertEqual(after['undamped']['power'], before['power'])
            for field in ('position', 'weight', 'frequency', 'width', 'state'):
                self.assertEqual(before[field], after[field])
            if after['state'] == 'PREVIEW':
                self.assertGreaterEqual(after['envelope'], 10)
                self.assertLessEqual(after['envelope'], 80)
                expected = 10 + (after['envelope'] - 10) * after['weight'] / 100
                self.assertAlmostEqual(after['power'], expected, delta=.015)
        self.assertGreater(smooth[75]['envelope'], raw[75]['envelope'])
        self.assertLess(smooth[155]['envelope'], raw[155]['envelope'])
        for frames in (raw, smooth):
            self.assertEqual(frames[-1]['power'], 0)
        raw_drop = max(a['envelope'] - b['envelope'] for a, b in zip(raw[145:180], raw[146:181]))
        smooth_drop = max(a['envelope'] - b['envelope'] for a, b in zip(smooth[145:180], smooth[146:181]))
        self.assertGreater(raw_drop, 20)
        self.assertLess(smooth_drop, 5)

    def test_no_lookahead_retains_existing_response(self):
        self.assertEqual(self.replay(0, False), self.replay(4, False))
