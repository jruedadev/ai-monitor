"""Clustering léxico de prompts (spec §3.3): trigramas de palabras + Jaccard
con índice invertido y union-find. Dos modos: candidatos para el LLM
(≥0,3, ≥2 sesiones, top 40) y solo léxico (≥0,5, umbrales finales, top 10)."""
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

CANDIDATE_THRESHOLD = 0.3
CANDIDATE_MIN_SESSIONS = 2
CANDIDATE_LIMIT = 40
LEXICAL_THRESHOLD = 0.5
FINAL_MIN_SESSIONS = 3
FINAL_MIN_DAYS = 2
FINAL_LIMIT = 10
SIGNATURE_SIZE = 50
SNIPPETS = 3
SNIPPET_CHARS = 200
PATTERN_CHARS = 120

STOPWORDS = frozenset("""
a al algo como con de del el ella en entre es esa ese eso esta este esto la las le les lo los mas me mi muy
no nos o para pero por que se si sin sobre su sus te tu un una uno unos y ya yo hay son fue ser esta estan
the a an and are as at be but by for from has have i in is it its me my of on or so that the this to was
we with you your do does can please
""".split())

SERVICES = ("jira", "github", "gitlab", "sentry", "slack", "notion", "linear", "confluence", "figma",
            "trello", "asana", "bitbucket", "jenkins", "datadog", "grafana", "vercel", "supabase", "stripe")

IMPERATIVE_VERBS = frozenset("""
revisa corrige arregla ejecuta corre crea agrega anade actualiza sube despliega genera escribe lee abre
compila prueba haz elimina borra busca documenta refactoriza migra instala configura valida verifica
analiza resume traduce commitea
review fix run create add update deploy generate write read open build test remove delete search find
document refactor migrate install configure validate verify check analyze summarize translate commit push
""".split())

_WORD = re.compile(r"[a-z0-9]+")
_PASTED = re.compile(
    r"Traceback \(most recent call last\)|^\s+at [\w.$<>]+\(|^\s*[{\[]\s*\"|\b(?:ERROR|WARN(?:ING)?|FATAL)\b"
    r"|^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}", re.MULTILINE)
PASTED_MIN_CHARS = 1500
PASTED_MIN_LINES = 15


def normalize(text):
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return [w for w in _WORD.findall(plain) if w not in STOPWORDS]


def trigrams(words):
    if not words:
        return set()
    if len(words) < 3:
        return {" ".join(words)}
    return {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _union_find_groups(sets, threshold):
    parent = list(range(len(sets)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    index = defaultdict(list)
    for i, grams in enumerate(sets):
        for gram in grams:
            index[gram].append(i)
    for i, grams in enumerate(sets):
        neighbours = {j for gram in grams for j in index[gram] if j > i}
        for j in neighbours:
            if find(i) != find(j) and jaccard(grams, sets[j]) >= threshold:
                parent[find(j)] = find(i)

    groups = defaultdict(list)
    for i in range(len(sets)):
        groups[find(i)].append(i)
    return list(groups.values())


def _verb_sequence(text):
    seq = []
    for word in normalize(text):
        if word in IMPERATIVE_VERBS and (not seq or seq[-1] != word):
            seq.append(word)
    return seq


def _step_pairs(text):
    seq = _verb_sequence(text)
    return {(seq[i], seq[i + 1]) for i in range(len(seq) - 1)}


def _features(members):
    pasted = any(_PASTED.search(m.text) or len(m.text) >= PASTED_MIN_CHARS
                 or m.text.count("\n") >= PASTED_MIN_LINES for m in members)
    words = set()
    for m in members:
        words.update(normalize(m.text))
    services = [s for s in SERVICES if s in words]
    pair_counts = Counter(pair for m in members for pair in _step_pairs(m.text))
    same_steps = any(count >= 2 for count in pair_counts.values())
    return {"pega_datos": bool(pasted), "menciona_servicio": services, "mismos_pasos": same_steps}


def _signature(members):
    counts = Counter(gram for m in members for gram in trigrams(normalize(m.text)))
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return {gram for gram, _ in ranked[:SIGNATURE_SIZE]}


@dataclass
class Cluster:
    cluster_id: str
    members: list
    signature: set
    session_tokens: dict = field(repr=False)
    features: dict

    @property
    def sessions(self):
        return {(m.source, m.session_id) for m in self.members}

    @property
    def days(self):
        return {m.day_utc for m in self.members}

    @property
    def projects(self):
        return sorted({m.project for m in self.members})

    @property
    def sources(self):
        return sorted({m.source for m in self.members})

    @property
    def tokens(self):
        estimated = Counter()
        for m in self.members:
            estimated[(m.source, m.session_id)] += len(m.text) // 4
        return sum(self.session_tokens.get(key, estimated[key]) for key in self.sessions)

    @property
    def tool(self):
        sources = self.sources
        return sources[0] if len(sources) == 1 else "varias"

    @property
    def score(self):
        return len(self.sessions) * self.tokens

    @property
    def pattern(self):
        shortest = min(self.members, key=lambda m: (len(m.text), m.text))
        return shortest.text.strip().splitlines()[0][:PATTERN_CHARS]

    def snippets(self):
        out, seen_sessions = [], set()
        for m in sorted(self.members, key=lambda m: (m.day_utc, m.session_id)):
            key = (m.source, m.session_id)
            snippet = m.text.strip()[:SNIPPET_CHARS]
            if key in seen_sessions or snippet in out:
                continue
            seen_sessions.add(key)
            out.append(snippet)
            if len(out) == SNIPPETS:
                break
        return out

    def common_steps(self):
        sequences = [tuple(_verb_sequence(m.text)) for m in self.members]
        counts = Counter(seq for seq in sequences if len(seq) >= 2)
        if not counts:
            return []
        seq, _ = max(counts.items(), key=lambda kv: (kv[1], len(kv[0]), kv[0]))
        return list(seq)

    def evidence(self):
        return {"sessions": len(self.sessions), "days": len(self.days), "tokens": self.tokens,
                "projects": self.projects, "sources": self.sources, "snippets": self.snippets()}


def _build(cluster_id, members, session_tokens):
    return Cluster(cluster_id, list(members), _signature(members), session_tokens, _features(members))


def _groups(prompts, threshold):
    usable = [(p, trigrams(normalize(p.text))) for p in prompts]
    usable = [(p, grams) for p, grams in usable if grams]
    indices = _union_find_groups([grams for _, grams in usable], threshold)
    return [[usable[i][0] for i in group] for group in indices]


def _renumber(clusters):
    for i, c in enumerate(clusters, start=1):
        c.cluster_id = f"c{i}"
    return clusters


def candidates(prompts, session_tokens, limit=CANDIDATE_LIMIT):
    built = [_build("", members, session_tokens) for members in _groups(prompts, CANDIDATE_THRESHOLD)]
    built = [c for c in built if len(c.sessions) >= CANDIDATE_MIN_SESSIONS]
    built.sort(key=lambda c: (-c.tokens, c.pattern))
    return _renumber(built[:limit])


def passes_final(c):
    return len(c.sessions) >= FINAL_MIN_SESSIONS and len(c.days) >= FINAL_MIN_DAYS


def rank_final(clusters, limit=FINAL_LIMIT):
    kept = [c for c in clusters if passes_final(c)]
    kept.sort(key=lambda c: (-c.score, c.pattern))
    return kept[:limit]


def lexical_clusters(prompts, session_tokens, limit=FINAL_LIMIT):
    built = [_build("", members, session_tokens) for members in _groups(prompts, LEXICAL_THRESHOLD)]
    return _renumber(rank_final(built, limit))


def merge(clusters, group_id):
    members = [m for c in clusters for m in c.members]
    features = {
        "pega_datos": any(c.features["pega_datos"] for c in clusters),
        "menciona_servicio": [s for s in SERVICES if any(s in c.features["menciona_servicio"] for c in clusters)],
        "mismos_pasos": any(c.features["mismos_pasos"] for c in clusters),
    }
    signature = set().union(*(c.signature for c in clusters)) if clusters else set()
    session_tokens = clusters[0].session_tokens if clusters else {}
    return Cluster(group_id, members, signature, session_tokens, features)
