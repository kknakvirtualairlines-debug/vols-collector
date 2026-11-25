#!/usr/bin/env python3
"""Releve VATSIM + IVAO; detecte les arrivees sur aeroports LF* (France metropolitaine).

Un lancement = une boucle de DURATION secondes avec un releve toutes les INTERVAL secondes.
L'etat (vols en cours) et les arrivees sont lus/ecrits dans OUT_DIR (state.json, arrivals.csv).
Aucune donnee personnelle n'est conservee: ni nom de pilote, ni CID (la cle est un hash).
"""
import csv, hashlib, json, math, os, sys, time, datetime as dt, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
AIRPORTS_CSV = os.environ.get('AIRPORTS_CSV', os.path.join(HERE, '..', 'airports.csv'))  # OurAirports, telecharge par le workflow
FIELDS = ['key', 'date', 'network', 'callsign', 'aircraft', 'dep', 'arr',
          'arrival_time_utc', 'first_seen_utc', 'duration_min', 'tracking_complete']
FMT = '%Y-%m-%dT%H:%M:%SZ'


def load_airports(path=AIRPORTS_CSV):
    with open(path, encoding='utf-8') as f:
        return {r['ident']: (float(r['latitude_deg']), float(r['longitude_deg']))
                for r in csv.DictReader(f) if r['ident'].startswith('LF') and len(r['ident']) == 4}


def nm(lat1, lon1, lat2, lon2):
    """Distance en milles nautiques (haversine)."""
    p = math.pi / 180
    x = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 6371 / 1.852 * 2 * math.asin(math.sqrt(x))


def make_key(net, cid, callsign, logon):
    return hashlib.sha256(f'{net}|{cid}|{callsign}|{logon}'.encode()).hexdigest()[:16]


def now():
    return dt.datetime.now(dt.timezone.utc)


class Tracker:
    def __init__(self, airports, state=None, known_keys=None):
        self.ap = airports
        self.state = state or {}
        self.known = set(known_keys or [])
        self.new_arrivals = []

    def handle(self, net, key, cs, ac, dep, arr, lat, lon, gs, onground, t=None):
        if not arr or arr not in self.ap:
            return
        t = t or now().strftime(FMT)
        dist = nm(lat, lon, *self.ap[arr])
        s = self.state.get(key)
        if s is None:
            s = self.state[key] = {'net': net, 'cs': cs, 'ac': ac, 'dep': dep, 'arr': arr, 'first_seen': t,
                                   'complete': 1 if gs < 40 else 0, 'airborne': 0, 'arrived': 0}
        if gs > 120 and not onground and dist > 5:
            s['airborne'] = 1
        if not s['arrived'] and s['airborne'] and dist <= 6 and gs < 50:
            s['arrived'] = 1
            if key not in self.known:
                self.known.add(key)
                start = dt.datetime.strptime(s['first_seen'], FMT).replace(tzinfo=dt.timezone.utc)
                dur = int((dt.datetime.strptime(t, FMT).replace(tzinfo=dt.timezone.utc) - start).total_seconds() / 60)
                self.new_arrivals.append({'key': key, 'date': t[:10], 'network': net, 'callsign': cs, 'aircraft': ac,
                                          'dep': dep, 'arr': arr, 'arrival_time_utc': t, 'first_seen_utc': s['first_seen'],
                                          'duration_min': dur, 'tracking_complete': s['complete']})
        s.update(last_seen=t, arr=arr, dep=dep)

    def prune(self, days=2):
        limit = (now() - dt.timedelta(days=days)).strftime(FMT)
        self.state = {k: v for k, v in self.state.items() if v.get('last_seen', '') >= limit}


def poll(tr):
    import requests
    try:
        v = requests.get('https://data.vatsim.net/v3/vatsim-data.json', timeout=30).json()
        for p in v['pilots']:
            fp = p.get('flight_plan') or {}
            tr.handle('VATSIM', make_key('V', p['cid'], p['callsign'], p['logon_time']), p['callsign'],
                      fp.get('aircraft_short') or fp.get('aircraft'), fp.get('departure'), fp.get('arrival'),
                      p['latitude'], p['longitude'], p['groundspeed'], p['groundspeed'] < 40 and p['altitude'] < 5000)
    except Exception:
        traceback.print_exc()
    try:
        i = requests.get('https://api.ivao.aero/v2/tracker/whazzup', timeout=30).json()
        for p in i['clients']['pilots']:
            fp = p.get('flightPlan') or {}
            lt = p.get('lastTrack') or {}
            if not lt:
                continue
            tr.handle('IVAO', make_key('I', p['userId'], p['callsign'], p['createdAt']), p['callsign'], fp.get('aircraftId'),
                      fp.get('departureId'), fp.get('arrivalId'), lt['latitude'], lt['longitude'], lt['groundSpeed'],
                      lt.get('onGround', False))
    except Exception:
        traceback.print_exc()


def load(out):
    sp, ap = os.path.join(out, 'state.json'), os.path.join(out, 'arrivals.csv')
    state = json.load(open(sp)) if os.path.exists(sp) else {}
    keys = [r['key'] for r in csv.DictReader(open(ap, encoding='utf-8'))] if os.path.exists(ap) else []
    return state, keys


def save(out, tr):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'state.json'), 'w') as f:
        json.dump(tr.state, f, sort_keys=True)
    ap = os.path.join(out, 'arrivals.csv')
    new = not os.path.exists(ap)
    with open(ap, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        w.writerows(tr.new_arrivals)
    tr.new_arrivals = []


def main():
    out = os.environ.get('OUT_DIR', 'out')
    duration = int(os.environ.get('DURATION', '1620'))
    interval = int(os.environ.get('INTERVAL', '120'))
    state, keys = load(out)
    tr = Tracker(load_airports(), state, keys)
    end = time.time() + duration
    while True:
        s = time.time()
        poll(tr)
        tr.prune()
        save(out, tr)  # sauvegarde a chaque releve: rien n'est perdu si le job est coupe
        if time.time() + interval > end:
            break
        time.sleep(max(5, interval - (time.time() - s)))


if __name__ == '__main__':
    sys.exit(main())
