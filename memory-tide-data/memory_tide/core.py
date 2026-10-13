import hashlib
import json
import math
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Shanghai')
SOURCE = 'bhwa233/weibo-trending-hot-history'
REPO = 'https://github.com/' + SOURCE


def now():
    return datetime.now(TZ).isoformat(timespec='seconds')


def time_iso(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ).isoformat(timespec='seconds')


def epoch(value):
    return int(datetime.fromisoformat(time_iso(value)).timestamp())


def finite_number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        return None
    try:
        number=float(value)
        return number if math.isfinite(number) else None
    except OverflowError:
        return None


def iter_slots(db, start, end, source=SOURCE):
    """Requested hour grid, including explicitly unknown coverage boundaries."""
    start=time_iso(start);end=time_iso(end)
    if epoch(start)>epoch(end):raise ValueError('start must be <= end')
    stored={r['epoch']:dict(r) for r in db.execute('SELECT * FROM slots WHERE source=? AND epoch BETWEEN ? AND ?',
                                                (source,epoch(start),epoch(end)))}
    bounds=db.execute('SELECT min(epoch),max(epoch) FROM slots WHERE source=?',(source,)).fetchone()
    dt=datetime.fromisoformat(start)
    if dt.minute or dt.second:dt=dt.replace(minute=0,second=0)+timedelta(hours=1)
    while dt.timestamp()<=epoch(end):
        e=int(dt.timestamp())
        if e in stored:yield stored[e]
        else:
            outside=bounds[0] is None or e<bounds[0] or e>bounds[1]
            yield dict(source=source,timestamp=dt.isoformat(timespec='seconds'),epoch=e,
                       status='outside_source_coverage' if outside else 'missing_snapshot',file_id=None,
                       row_count=0,ranked_count=0,complete=0,quality='["no_source_coverage"]' if outside else '[]')
        dt+=timedelta(hours=1)


def clean_title(value):
    if not isinstance(value, str):
        return ''
    value = unicodedata.normalize('NFC', value)
    # Preserve semantic emoji/script joiners; whitespace controls become spaces.
    value = ''.join(' ' if c.isspace() else c for c in value
                    if c.isspace() or unicodedata.category(c) not in ('Cc', 'Cf') or c in '\u200c\u200d')
    return re.sub(r'\s+', ' ', value).strip()


def topic_id(title):
    return 'weibo:' + hashlib.sha256(('weibo\0' + clean_title(title)).encode()).hexdigest()


def normalize(raw, timestamp):
    if not isinstance(raw, dict) or not (title := clean_title(raw.get('title'))):
        return None
    flags = ['hour_precision']
    if title != raw.get('title'):
        flags.append('title_normalized')
    url = raw.get('url') if isinstance(raw.get('url'), str) else None
    params = parse_qs(urlparse(url or '').query)
    nested = parse_qs(params.get('extparam', [''])[0])
    # File order is a heat sort, NOT the original Weibo ranking.
    val = (nested.get('band_rank') or params.get('band_rank') or nested.get('realpos') or [None])[0]
    try:
        rank = int(val)
        if not 1 <= rank <= 50:
            rank = None
            flags.append('invalid_rank')
    except (TypeError, ValueError):
        rank = None
        flags.append('missing_rank')
    raw_heat = raw.get('hot')
    heat = finite_number(raw_heat)
    if heat is None or heat < 0:
        heat = None
        flags.append('invalid_heat' if raw_heat is not None else 'missing_heat')
    elif heat == 0:
        heat = None
        flags.append('source_zero_ambiguous')
    if heat is not None and heat > 100_000_000:
        flags.append('extreme_heat_review')
    if raw.get('ads'):
        flags.append('advertisement')
    return dict(topic_id=topic_id(title), title=title, timestamp=time_iso(timestamp), rank=rank,
                heat=heat, raw_heat=raw_heat, platform='weibo', source=SOURCE, url=url,
                is_ad=int(bool(raw.get('ads'))), quality=flags)


SCHEMA = '''
CREATE TABLE IF NOT EXISTS sources(source TEXT PRIMARY KEY, platform TEXT, repository_url TEXT,
 license TEXT, sampling_seconds INTEGER, timestamp_precision TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS import_runs(id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT,
 archive_path TEXT, archive_sha256 TEXT, revision TEXT, files_added INTEGER, records_added INTEGER);
CREATE TABLE IF NOT EXISTS raw_files(id INTEGER PRIMARY KEY, source TEXT, path TEXT, revision TEXT,
 sha256 TEXT, bytes INTEGER, imported_at TEXT, timestamp TEXT, status TEXT, record_count INTEGER,
 UNIQUE(source,path));
CREATE TABLE IF NOT EXISTS raw_records(id INTEGER PRIMARY KEY, file_id INTEGER REFERENCES raw_files(id),
 ordinal INTEGER, payload TEXT, status TEXT, UNIQUE(file_id,ordinal));
CREATE TABLE IF NOT EXISTS topics(topic_id TEXT PRIMARY KEY, platform TEXT, title TEXT);
CREATE TABLE IF NOT EXISTS topic_relations(left_id TEXT REFERENCES topics(topic_id),
 right_id TEXT REFERENCES topics(topic_id), relation TEXT, confidence REAL, evidence TEXT,
 status TEXT, PRIMARY KEY(left_id,right_id,relation));
CREATE TABLE IF NOT EXISTS snapshots(source TEXT REFERENCES sources(source), timestamp TEXT,
 epoch INTEGER, topic_id TEXT REFERENCES topics(topic_id), rank INTEGER, heat REAL, raw_heat REAL,
 url TEXT, is_ad INTEGER, quality TEXT, raw_record_id INTEGER REFERENCES raw_records(id),
 PRIMARY KEY(source,timestamp,topic_id));
CREATE TABLE IF NOT EXISTS slots(source TEXT, timestamp TEXT, epoch INTEGER, status TEXT,
 file_id INTEGER REFERENCES raw_files(id), row_count INTEGER, ranked_count INTEGER,
 complete INTEGER, quality TEXT, PRIMARY KEY(source,timestamp));
CREATE TABLE IF NOT EXISTS changes(source TEXT, timestamp TEXT, topic_id TEXT, previous_timestamp TEXT,
 observed_interval_seconds INTEGER, observed_interval_delta REAL, observed_interval_per_hour REAL,
 heat_delta REAL, heat_pct REAL, heat_per_hour REAL, hour_delta REAL, rank_delta INTEGER,
 phase TEXT, quality TEXT, PRIMARY KEY(source,timestamp,topic_id));
CREATE TABLE IF NOT EXISTS lifecycles(source TEXT, topic_id TEXT, first_seen TEXT, last_seen TEXT,
 peak_heat REAL, peak_timestamp TEXT, best_rank INTEGER, observations INTEGER,
 observed_span_seconds INTEGER, adjacent_observed_seconds INTEGER, confirmed_reentries INTEGER,
 unknown_gaps INTEGER, left_censored INTEGER, right_censored INTEGER,
 PRIMARY KEY(source,topic_id));
CREATE INDEX IF NOT EXISTS snapshot_topic_time ON snapshots(source,topic_id,epoch);
CREATE INDEX IF NOT EXISTS slot_epoch ON slots(source,epoch);
'''


def connect(path):
    path = str(path)
    if path != ':memory:':
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=NORMAL')
    db.executescript(SCHEMA)
    db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,?)',
               (SOURCE, 'weibo', REPO, 'MIT (upstream repository)', 3600, 'hour',
                'Mobile hot-search index; missing slots and ambiguous source zeros remain null.'))
    db.commit()
    return db
