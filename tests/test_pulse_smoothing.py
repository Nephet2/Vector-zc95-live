import unittest

from engine import Engine, defaults, validate


class PulseSmoothingTests(unittest.TestCase):
    def replay(self, window, buffer_enabled=True):
        now = 0.
        engine = Engine(clock=lambda: now)
        rows = defaults()
        rows[0].update(frequency_mode='position', width_mode='position',
                       frequency_min=20, frequency_max=220, width_min=30, width_max=230,
                       frequency_damping_ms=0, width_damping_ms=0,
                       frequency_smoothing_s=window, width_smoothing_s=0)
        rows[1]['frequency_follow_ab'] = True
        engine.configure(dict(channels=rows, crossover=engine.crossover,
                              volume=dict(enabled=buffer_enabled, delay_s=2, ratio=20)))
        output = {}
        for tick in range(181):
            now = tick / 20
            if tick % 10 == 0:
                position = 500 + 2500 * sum(now >= edge for edge in (4., 4.5, 5.))
                engine.ingest(f'L0{position:04d}I50', 'UDP')
            frame = engine.snapshot()
            first, second = frame['channels'][:2]
            if second['state'] == 'PREVIEW':
                self.assertEqual(second['frequency'], first['frequency'])
                self.assertEqual(second['undamped']['frequency'], first['undamped']['frequency'])
            output[now] = first
        return output

    def test_window_smooths_one_axis_without_retiming_motion_or_power(self):
        raw = self.replay(0)
        smooth = self.replay(3)
        for at in raw:
            for axis in ('position', 'power', 'width'):
                self.assertEqual(smooth[at][axis], raw[at][axis])
            self.assertEqual(smooth[at]['undamped']['frequency'], raw[at]['frequency'])
        self.assertGreater(smooth[5.8]['frequency'], raw[5.8]['frequency'])
        self.assertLess(smooth[7.2]['frequency'], raw[7.2]['frequency'])
        values = [smooth[t]['frequency'] for t in (6., 6.25, 6.5, 6.75, 7.)]
        self.assertEqual(values, sorted(set(values)))
        self.assertTrue(all(20 <= frame['frequency'] <= 220 for frame in smooth.values()))

    def test_no_lookahead_uses_original_response(self):
        self.assertEqual(self.replay(3, False), self.replay(0, False))

    def test_damping_reports_target_and_command_separately(self):
        engine = Engine()
        channel = defaults()[0]
        channel.update(width_mode='position', width_min=40, width_max=140,
                       width_damping_ms=1000, width_rest_enabled=False)
        target, command = engine.parameter(channel, 'width', .8, 0, False, 1, 0, .1)
        self.assertEqual(target, 120)
        self.assertGreater(command, 40)
        self.assertLess(command, target)

    def test_old_settings_default_to_off_and_axes_round_trip_independently(self):
        rows = defaults()
        for row in rows:
            del row['width_smoothing_s']
            del row['frequency_smoothing_s']
        self.assertEqual(validate(rows)[0]['frequency_smoothing_s'], 0)
        rows[0].update(width_smoothing_s=1.25, frequency_smoothing_s=3)
        clean = validate(rows)
        self.assertEqual(clean[0]['width_smoothing_s'], 1.25)
        self.assertEqual(clean[0]['frequency_smoothing_s'], 3)
        self.assertEqual(clean[1]['width_smoothing_s'], 0)
