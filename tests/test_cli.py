import pytest

from arbscan.cli import main


def test_replay_then_gates(fixtures, tmp_path, capsys):
    db = str(tmp_path / 'scan.db')
    main(['replay', str(fixtures / 'synthetic_ou_demo.jsonl'), '--db', db])
    out = capsys.readouterr().out
    assert '2 arb episodes' in out and 'smarkets:back:under' in out and 'smarkets:lay:over' in out
    main(['gates', '--db', db])
    out = capsys.readouterr().out
    assert 'G4 lifetime' in out and '18.0 / 20.0' in out    # only the +0.74% one clears the 0.5% bar
    with pytest.raises(SystemExit):
        main(['replay', str(fixtures / 'synthetic_ou_demo.jsonl'), '--db', db])
    main(['replay', str(fixtures / 'synthetic_ou_demo.jsonl'), '--db', db, '--reset'])


def test_scan_report_snapshot(fixtures, capsys):
    main(['scan', str(fixtures / 'bayern_arsenal_2026-10-21.jsonl'), '--max-age', '120', '--top', '3'])
    out = capsys.readouterr().out
    assert all(roi in out for roi in ('-0.61%', '-0.71%', '-1.03%', '-1.51%'))    # report: B, A2, B2, C
