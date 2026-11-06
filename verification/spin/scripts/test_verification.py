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
    def check(self, prop, samples, expected, phase=0, endless_yellow=False, depth=10000):
        with tempfile.TemporaryDirectory(prefix='traffic-spin-monitor-test-') as directory:
            build = Path(directory)
            shutil.copyfile(SPIN / 'models/properties.pml', build / 'properties.pml')
            body = '\n'.join(f'd_step {{ signal = {value}; observe_second() }};'
                             for value in samples)
            if endless_yellow:
                body += '\ndo :: d_step { signal = 1; observe_second() } od;'
            if prop == 'C1':
                body += 'check_boundary();'
            (build / 'test.pml').write_text(
                '#define MIN_GREEN 10\n'
                f'byte signal=0; int current_phase={phase};\n'
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

    def test_actual_depth_exhaustion(self):
        self.check('G1', [0] * 10 + [1], 'UNKNOWN', depth=2)

    def test_phase_consistency(self):
        self.check('C1', [0], 'PASS')
        self.check('C1', [0], 'FAIL', phase=-1)
        self.check('C1', [2], 'FAIL', phase=0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
