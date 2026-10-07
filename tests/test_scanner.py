from contextlib import redirect_stdout, redirect_stderr
from datetime import date, timedelta
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scanner.core import Bar, Rules, evaluate, scan, validate
from scanner.data import fetch_alpha, load_csv, parse_alpha
from scanner.__main__ import main


AS_OF = date(2026, 10, 6)


def history():
    return [Bar(AS_OF - timedelta(days=21-i), 10.0, 200_000) for i in range(20)] + [
        Bar(AS_OF - timedelta(days=1), 12.0, 400_000)]


class ScannerTests(unittest.TestCase):
    def test_exact_metrics_exclude_signal_day_from_baseline(self):
        row = evaluate('TEST', 'CAD', history(), AS_OF, Rules())
        self.assertEqual(row['score'], 5)
        self.assertEqual(row['momentum_5d_pct'], 20)
        self.assertEqual(row['relative_volume'], 2)
        self.assertEqual(row['avg_turnover_20d'], 2_000_000)

    def test_no_lookahead_or_partial_same_day(self):
        bars = history()
        expected = evaluate('TEST', 'USD', bars, AS_OF, Rules())
        bars += [Bar(AS_OF, 1000, 999999), Bar(AS_OF+timedelta(days=1), 1, 0)]
        self.assertEqual(evaluate('TEST', 'USD', bars, AS_OF, Rules()), expected)

    def test_bad_histories_excluded_with_reason(self):
        for bars in (history()[:20], [Bar(b.date-timedelta(days=10), b.close, b.volume) for b in history()],
                     [Bar(b.date, b.close, 0) for b in history()]):
            candidates, excluded = scan({('TEST', 'CAD'): bars}, AS_OF, Rules())
            self.assertEqual(candidates, [])
            self.assertTrue(excluded[0]['reason'])

    def test_validation_rejects_duplicates_nonfinite_and_negative(self):
        for bars in ([history()[0]]*2, [Bar(AS_OF, float('nan'), 1)],
                     [Bar(AS_OF, float('inf'), 1)], [Bar(AS_OF, 0, 1)],
                     [Bar(AS_OF, 10, -1)]):
            with self.assertRaises(ValueError): validate(bars)
        with self.assertRaises(ValueError): Rules(min_turnover=float('nan'))

    def test_deterministic_ties(self):
        rows, _ = scan({('Z', 'USD'):history(), ('A', 'CAD'):history()}, AS_OF, Rules())
        self.assertEqual([r['symbol'] for r in rows], ['A', 'Z'])

    def test_demo_and_real_csv_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'report.json'
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--demo', '--out', str(out)]), 0)
            report = json.loads(out.read_text())
            self.assertIn('SYNTHETIC', report['source'])
            self.assertEqual(report['candidates'][0]['symbol'], 'DEMO-UP')
            self.assertEqual(len(report['excluded']), 2)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--csv', 'examples/demo.csv', '--as-of', '2026-10-06']), 0)

    def test_malformed_csv_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bad.csv'
            for content in ('x,y\n1,2\n', 'symbol,currency,date,close,volume\nT,CAD,2026-10-05,nan,5\n',
                            'symbol,currency,date,close,volume\nT,CAD,2026-10-05,5,5\nT,USD,2026-10-04,5,5\n'):
                path.write_text(content)
                with self.assertRaises(ValueError): load_csv(path)

    def test_provider_contract_and_quota(self):
        bars = parse_alpha({'Time Series (Daily)': {'2026-10-05': {'4. close':'12', '5. volume':'400000'}}})
        self.assertEqual(bars, [Bar(date(2026,10,5),12,400000)])
        for payload in ({'Note':'quota'}, {'Information':'upgrade'}, {'Error Message':'invalid'}, [],
                        {'Time Series (Daily)': {'bad':{}}}):
            with self.assertRaises(ValueError): parse_alpha(payload)

    def test_live_partial_failure_does_not_fake_success_or_leak_key(self):
        good = {'Time Series (Daily)': {str(b.date): {'4. close':str(b.close), '5. volume':str(b.volume)} for b in history()}}
        with patch.dict(os.environ, {'ALPHAVANTAGE_API_KEY':'SECRET'}), patch('scanner.data.urlopen') as http:
            http.return_value.__enter__.side_effect = [io.StringIO(json.dumps(good)), io.StringIO('{"Note":"SECRET quota"}')]
            with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as output:
                out = Path(tmp)/'result.json'
                code = main(['--alpha-vantage','--symbols','IBM,MSFT','--as-of',str(AS_OF),'--out',str(out)])
                report = json.loads(out.read_text())
                self.assertEqual(code, 2)
                self.assertEqual(report['status'], 'partial')
                self.assertEqual(len(report['candidates']),1)
                self.assertEqual(report['errors'][0]['symbol'],'MSFT')
                self.assertNotIn('SECRET', output.getvalue()+out.read_text())

    def test_missing_key_and_invalid_args_fail(self):
        with patch.dict(os.environ, {}, clear=True), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--alpha-vantage','--symbols','IBM']), 2)
            self.assertEqual(main(['--demo','--min-price','-1']),2)
            self.assertEqual(main(['--alpha-vantage']),2)

    def test_module_entrypoint(self):
        result = subprocess.run([sys.executable, '-m', 'scanner', '--demo'], capture_output=True, text=True)
        self.assertEqual(result.returncode,0, result.stderr)
        self.assertIn('DEMO-UP',result.stdout)


if __name__ == '__main__':
    unittest.main()
