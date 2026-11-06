#!/usr/bin/env python3
"""Boundary and fault-injection checks for monitors and result classification.

Synthetic signals deliberately include behaviors absent from a correct controller,
so a vacuous/disconnected monitor cannot pass this test suite.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from run_spin import classify, SPIN


class ResultClassification(unittest.TestCase):
    def test_completed_search(self):
        self.assertEqual(classify('Full statespace search\nerrors: 0', 0), 'PASS')

    def test_violation_exit_zero(self):
        self.assertEqual(classify('pan: assertion violated x\nSearch not completed\nerrors: 1', 0), 'FAIL')

    def test_incomplete_searches(self):
        for text in ['max search depth too small', 'reached -DMEMLIM bound',
                     'Full statespace search\nSearch not completed\nerrors: 0']:
            self.assertEqual(classify(text, 1 if 'MEMLIM' in text else 0), 'UNKNOWN')

    def test_errors_and_cycles(self):
        self.assertEqual(classify('pan: acceptance cycle\nerrors: 1', 0), 'FAIL')
        self.assertEqual(classify('syntax error', 1), 'ERROR')
        self.assertEqual(classify('Full statespace search\ninvalid end state\nerrors: 1', 0), 'ERROR')


class MonitorFaultInjection(unittest.TestCase):
    def check(self, prop, samples, expected, phase=0, endless_yellow=False, depth=10000, controller_age=0, yellow=3):
        with tempfile.TemporaryDirectory(prefix='traffic-spin-monitor-test-') as directory:
            build = Path(directory)
            shutil.copyfile(SPIN / 'models/properties.pml', build / 'properties.pml')
            body = '\n'.join(f'd_step {{ signal = {value}; observe_second() }};'
                             for value in samples)
            if endless_yellow:
                body += '\ndo :: d_step { signal = 1; observe_second() } od;'
            if prop in ('C1', 'G2'):
                body += 'check_boundary();'
            (build / 'test.pml').write_text(
                f'#define MIN_GREEN 10\n#define MAX_GREEN 60\n#define YELLOW_TIME {yellow}\n'
                f'byte signal=0; int current_phase={phase}; int phase_duration={controller_age};\n'
                '#include "properties.pml"\ninit {\n' + body + '\n}\n')
            commands = [['spin', f'-DCHK_{prop}', '-a', 'test.pml'],
                        ['cc', '-O2', '-o', 'pan', 'pan.c'],
                        ['./pan', f'-m{depth}', '-w16', '-b'] + (['-a'] if prop == 'T2' else [])]
            for command in commands:
                result = subprocess.run(command, cwd=build, capture_output=True,
                                        text=True, timeout=30)
                if command[0] != './pan':
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(classify(result.stdout + result.stderr, result.returncode),
                             expected, result.stdout + result.stderr)

    def test_signal_codebook(self):
        self.check('S1', [0, 1, 2, 3], 'PASS')
        self.check('S1', [4], 'FAIL')

    def test_yellow_is_observed_in_both_directions(self):
        self.check('T1', [0, 2], 'FAIL')
        self.check('T1', [0, 1, 2, 0], 'FAIL')
        self.check('T1', [0, 1, 2, 3, 0], 'PASS')

    def test_yellow_duration_and_target(self):
        self.check('T2', [0, 1, 1, 2], 'FAIL')
        self.check('T2', [0, 1, 1, 1, 2], 'PASS')
        self.check('T2', [0, 1, 1, 1, 0], 'FAIL')
        self.check('T2', [0, 1], 'FAIL', endless_yellow=True)

    def test_minimum_green_boundary(self):
        self.check('G1', [0] * 9 + [1], 'FAIL')
        self.check('G1', [0] * 10 + [1], 'PASS')

    def test_maximum_green_boundary(self):
        for direction in (0, 2):
            self.check('G2', [direction] * 60, 'PASS')
            self.check('G2', [direction] * 61, 'FAIL')
        self.check('G2', [0] * 60 + [1] * 3 + [2] * 60, 'PASS')
        self.check('G2', [0] * 60 + [1] * 3 + [0] * 60, 'PASS')

    def test_controller_maximum_boundary(self):
        self.check('G2', [0], 'PASS', controller_age=60)
        self.check('G2', [0], 'FAIL', controller_age=61)

    def test_wait_boundary_both_directions(self):
        for served in (0, 2):
            self.check('L1', [served] * 66, 'PASS')
            self.check('L1', [served] * 67, 'FAIL')

    def test_wait_resets_and_counts_yellow(self):
        self.check('L1', [0] * 66 + [2] + [0] * 66, 'PASS')
        self.check('L1', [0] * 63 + [1] * 3, 'PASS')
        self.check('L1', [0] * 63 + [1] * 4, 'FAIL')
        self.check('L1', [0] * 60, 'PASS', yellow=0)
        self.check('L1', [0] * 61, 'FAIL', yellow=0)

    def test_actual_depth_exhaustion(self):
        self.check('G1', [0] * 10 + [1], 'UNKNOWN', depth=2)

    def test_phase_consistency(self):
        self.check('C1', [0], 'PASS')
        self.check('C1', [0], 'FAIL', phase=-1)
        self.check('C1', [2], 'FAIL', phase=0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
