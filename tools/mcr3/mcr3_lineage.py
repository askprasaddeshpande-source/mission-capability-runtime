"""Append-only evidence store with lineage and supersession (in memory; a durable store must keep the same rules).

Rules: an event id may be re-added only if the content is byte-identical (idempotent retry); the same id with different
content is a conflict and is refused. An event may supersede exactly one earlier event of the same mission and type; an
event can be superseded once (no forks); a chain cannot loop. A superseded event stays readable as history and is never
returned as current. causation_id, when set, must name an event already stored for the same mission. Nothing is deleted.
"""
import evc1


class LineageError(ValueError):
    pass


class EventStore:
    def __init__(self):
        self._events = {}              # id -> event
        self._order = []
        self._superseded_by = {}       # id -> id

    def add(self, event):
        known, _unrec = evc1.parse(event)
        eid = known["id"]
        if eid in self._events:
            if evc1.canonical_bytes(self._events[eid]) == evc1.canonical_bytes(event):
                return False                    # idempotent retry
            raise LineageError("event id %s already stored with different content" % eid)
        mission = known["correlation"]["mission_id"]
        cause = known["correlation"]["causation_id"]
        if cause is not None:
            c = self._events.get(cause)
            if c is None:
                raise LineageError("causation_id %s is not a stored event" % cause)
            if c["correlation"]["mission_id"] != mission:
                raise LineageError("causation_id belongs to another mission")
        sup = known["lineage"]["supersedes"]
        if sup is not None:
            old = self._events.get(sup)
            if old is None:
                raise LineageError("supersedes names an event that is not stored")
            if old["correlation"]["mission_id"] != mission or old["type"] != known["type"]:
                raise LineageError("an event may supersede only an event of the same mission and type")
            if sup in self._superseded_by:
                raise LineageError("event %s is already superseded (no forks)" % sup)
            if sup == eid:
                raise LineageError("an event cannot supersede itself")
        self._events[eid] = event
        self._order.append(eid)
        if sup is not None:
            self._superseded_by[sup] = eid
        return True

    def get(self, eid):
        return self._events[eid]

    def history(self, mission_id):
        return [self._events[i] for i in self._order if self._events[i]["correlation"]["mission_id"] == mission_id]

    def current(self, mission_id):
        return [e for e in self.history(mission_id) if e["id"] not in self._superseded_by]

    def superseded(self, eid):
        return eid in self._superseded_by

    def chain_of(self, eid):
        """The supersession chain ending at eid, oldest first."""
        out, cur = [eid], eid
        for _ in range(len(self._events) + 1):
            prev = self._events[cur]["lineage"]["supersedes"]
            if prev is None:
                return list(reversed(out))
            out.append(prev)
            cur = prev
        raise LineageError("supersession loop")

    def __len__(self):
        return len(self._order)
