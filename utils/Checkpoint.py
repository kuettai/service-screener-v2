import json
import os
import shutil
from datetime import datetime, timezone

import constants as _C


class Checkpoint:
    """Disk-backed checkpoint store for resumable scans.

    One append-only JSONL file per (account, service, region, objType), plus
    one manifest.json describing the scope a checkpoint was collected for.
    See docs/feature_checkpoints.md for the design.
    """

    CHECKPOINT_DIR = _C.FORK_DIR + '/checkpoint'
    MANIFEST_PATH = CHECKPOINT_DIR + '/manifest.json'
    SCHEMA_VERSION = 1

    ## In-memory index per jsonl path, loaded lazily once per worker process.
    _cache = {}

    @staticmethod
    def _itemFilePath(acctId, service, region, objType):
        safeAcct = str(acctId).replace('/', '_')
        return os.path.join(Checkpoint.CHECKPOINT_DIR, safeAcct, service, region, objType + '.jsonl')

    @staticmethod
    def _load(path):
        if path in Checkpoint._cache:
            return Checkpoint._cache[path]

        index = {}
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        index[record['id']] = record
                    except (json.JSONDecodeError, KeyError):
                        ## Tolerate a truncated last line (process killed mid-append)
                        continue

        Checkpoint._cache[path] = index
        return index

    @staticmethod
    def isDone(acctId, service, region, objType, resourceId):
        path = Checkpoint._itemFilePath(acctId, service, region, objType)
        return resourceId in Checkpoint._load(path)

    @staticmethod
    def getCached(acctId, service, region, objType, resourceId):
        path = Checkpoint._itemFilePath(acctId, service, region, objType)
        return Checkpoint._load(path).get(resourceId)

    @staticmethod
    def markDone(acctId, service, region, objType, resourceId, results, info):
        path = Checkpoint._itemFilePath(acctId, service, region, objType)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        record = {'id': resourceId, 'results': results, 'info': info}
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
            f.flush()

        Checkpoint._load(path)[resourceId] = record

    @staticmethod
    def registerAndFilter(acctId, service, region, objType, items, idFn):
        """Record the full universe of items seen this pass and return only
        the subset not already marked done. Call this before any expensive
        per-item detail fetch, not after."""
        path = Checkpoint._itemFilePath(acctId, service, region, objType)
        done = Checkpoint._load(path)
        return [item for item in items if idFn(item) not in done]

    ## ---- Manifest ----

    @staticmethod
    def buildManifest(services, regions, filters, crossAccounts, accounts):
        return {
            'schemaVersion': Checkpoint.SCHEMA_VERSION,
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'services': sorted(services),
            'regions': sorted(regions),
            'filters': filters or [],
            'crossAccounts': bool(crossAccounts),
            'accounts': sorted(str(a) for a in accounts),
        }

    @staticmethod
    def loadManifest():
        if not os.path.exists(Checkpoint.MANIFEST_PATH):
            return None
        try:
            with open(Checkpoint.MANIFEST_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def writeManifest(manifest):
        os.makedirs(Checkpoint.CHECKPOINT_DIR, exist_ok=True)
        with open(Checkpoint.MANIFEST_PATH, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

    @staticmethod
    def diffManifest(existing, requested):
        diffs = []
        for key in ('schemaVersion', 'services', 'regions', 'filters', 'crossAccounts', 'accounts'):
            if existing.get(key) != requested.get(key):
                diffs.append((key, existing.get(key), requested.get(key)))
        return diffs

    @staticmethod
    def resetAll():
        if os.path.exists(Checkpoint.CHECKPOINT_DIR):
            shutil.rmtree(Checkpoint.CHECKPOINT_DIR)
        Checkpoint._cache.clear()

    @staticmethod
    def _promptResume(existing):
        print()
        print("Found an incomplete scan matching this request:")
        print("  services: {}".format(', '.join(existing.get('services', []))))
        print("  regions:  {}".format(', '.join(existing.get('regions', []))))
        print("  accounts: {}".format(', '.join(existing.get('accounts', []))))
        print("  started:  {}".format(existing.get('createdAt', 'unknown')))

        attempt = 0
        while True:
            if attempt > 0:
                print("Please enter 'y' or 'n'.")
            answer = input("Resume from where it left off? [y/n]: ").strip().lower()
            attempt += 1
            if answer in ('y', 'n'):
                return answer == 'y'

    @staticmethod
    def prepareForRun(resume, manifest):
        """Call once in the parent process before the account loop.

        resume is tri-state:
          True  - explicit --resume 1. Requires an exact scope match against
                  the checkpointed manifest; hard-fails with a field-level
                  diff otherwise, rather than silently starting fresh or
                  resuming the wrong scope.
          False - explicit --resume 0. Always wipes and starts fresh.
          None  - not specified. Auto-detect: if a leftover checkpoint exists
                  and its scope matches this request exactly, ask the user
                  whether to resume. If it exists but doesn't match, note it
                  and start fresh without asking (it's for a different scan).
        """
        existing = Checkpoint.loadManifest()

        if existing is None:
            if resume is True:
                print("--resume requested but no checkpoint manifest found at {}; "
                      "starting a fresh scan.".format(Checkpoint.MANIFEST_PATH))
            Checkpoint.resetAll()
            Checkpoint.writeManifest(manifest)
            return

        diffs = Checkpoint.diffManifest(existing, manifest)

        if resume is True:
            if diffs:
                print("--resume requested but this run's scope does not match the "
                      "checkpointed run's scope:")
                for key, oldVal, newVal in diffs:
                    print("  {}: checkpoint={} requested={}".format(key, oldVal, newVal))
                print("Refusing to resume a mismatched scope. Run without --resume "
                      "for a fresh scan, or match the original command.")
                exit(1)
            return  # exact match, keep existing checkpoint data as-is

        if resume is False:
            Checkpoint.resetAll()
            Checkpoint.writeManifest(manifest)
            return

        ## resume is None: auto-detect
        if diffs:
            print("Found leftover checkpoint data from a different scan (created {}); "
                  "starting fresh, ignoring it.".format(existing.get('createdAt', 'unknown')))
            Checkpoint.resetAll()
            Checkpoint.writeManifest(manifest)
            return

        if Checkpoint._promptResume(existing):
            return  # keep existing checkpoint data, resume

        Checkpoint.resetAll()
        Checkpoint.writeManifest(manifest)
