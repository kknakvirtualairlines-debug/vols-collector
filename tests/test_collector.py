import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'collector'))
import collector as c

AP = {'LFPG': (49.0097, 2.5479)}


def test_nm_zero_and_known_distance():
    assert c.nm(49, 2, 49, 2) == 0
    assert 59 < c.nm(0, 0, 1, 0) < 61  # 1 degre de latitude ~ 60 NM


def test_key_has_no_raw_identifier():
    k = c.make_key('V', 1234567, 'AFR1', '2026-01-01')
    assert len(k) == 16 and '1234567' not in k


def test_arrival_detected_once():
    tr = c.Tracker(AP)
    tr.handle('VATSIM', 'k', 'AFR1', 'A320', 'EGLL', 'LFPG', 49.5, 3.5, 250, False, '2026-01-01T10:00:00Z')
    tr.handle('VATSIM', 'k', 'AFR1', 'A320', 'EGLL', 'LFPG', 49.0097, 2.5479, 20, True, '2026-01-01T10:40:00Z')
    tr.handle('VATSIM', 'k', 'AFR1', 'A320', 'EGLL', 'LFPG', 49.0097, 2.5479, 5, True, '2026-01-01T10:42:00Z')
    assert len(tr.new_arrivals) == 1
    a = tr.new_arrivals[0]
    assert a['arr'] == 'LFPG' and a['duration_min'] == 40 and a['tracking_complete'] == 0


def test_no_arrival_if_never_airborne():
    tr = c.Tracker(AP)
    tr.handle('IVAO', 'k', 'X1', 'C172', 'LFPG', 'LFPG', 49.0097, 2.5479, 0, True, '2026-01-01T10:00:00Z')
    assert tr.new_arrivals == []


def test_ignores_non_french_arrival():
    tr = c.Tracker(AP)
    tr.handle('IVAO', 'k', 'X1', 'C172', 'LFPG', 'EGLL', 51.4, -0.4, 0, True)
    assert tr.state == {}


def test_known_key_not_duplicated():
    tr = c.Tracker(AP, known_keys=['k'])
    tr.handle('IVAO', 'k', 'X1', 'A320', 'EGLL', 'LFPG', 49.5, 3.5, 250, False, '2026-01-01T10:00:00Z')
    tr.handle('IVAO', 'k', 'X1', 'A320', 'EGLL', 'LFPG', 49.0097, 2.5479, 10, True, '2026-01-01T10:30:00Z')
    assert tr.new_arrivals == []
