import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "context-usage-chart" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import context_usage as cu  # noqa: E402


def assistant(mid, inp, cread, ccreate, out=10, ts="2026-01-01T00:00:00Z", sidechain=False):
    o = {"type": "assistant", "timestamp": ts, "uuid": "u-" + mid,
         "message": {"id": mid, "usage": {"input_tokens": inp, "cache_read_input_tokens": cread,
                                          "cache_creation_input_tokens": ccreate, "output_tokens": out}}}
    if sidechain:
        o["isSidechain"] = True
    return o


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write((r if isinstance(r, str) else json.dumps(r)) + "\n")


SAMPLE_ROWS = [
    {"type": "user", "message": {"content": "hello"}},
    assistant("m1", 10, 0, 20000, ts="2026-01-01T00:00:00Z"),
    assistant("m1", 10, 0, 20000, out=50, ts="2026-01-01T00:00:01Z"),   # duplicate id, same size
    assistant("m2", 5, 20000, 30000, ts="2026-01-01T00:01:00Z"),        # 50,005
    assistant("m2", 5, 20000, 35000, ts="2026-01-01T00:01:01Z"),        # duplicate id, larger -> 55,005
    assistant("m3", 5, 55000, 45000, ts="2026-01-01T00:02:00Z"),        # 100,005
    assistant("side", 1, 900000, 0, sidechain=True),                    # subagent: ignored
    "this is not json but mentions \"usage\"",                          # broken line: skipped
    assistant("m4", 5, 0, 20000, ts="2026-01-01T00:03:00Z"),            # compaction: 100,005 -> 20,005
    assistant("m5", 5, 20000, 5000, ts="2026-01-01T00:04:00Z"),         # 25,005
]


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "sample.jsonl")
        write_jsonl(self.path, SAMPLE_ROWS)

    def test_dedup_and_sum(self):
        pts = cu.extract(self.path)
        self.assertEqual([p["context"] for p in pts], [20010, 55005, 100005, 20005, 25005])

    def test_sidechain_excluded(self):
        self.assertNotIn(900000 + 1, [p["context"] for p in cu.extract(self.path)])

    def test_collect_summary(self):
        d = cu.collect(self.path)
        self.assertEqual(d["session_id"], "sample")
        self.assertEqual(d["turns"], 5)
        self.assertEqual(d["last"], 25005)
        self.assertEqual(d["max"], 100005)

    def test_compaction_detected(self):
        d = cu.collect(self.path)
        self.assertEqual(len(d["compactions"]), 1)
        c = d["compactions"][0]
        self.assertEqual((c["from"], c["to"]), (100005, 20005))

    def test_small_drop_is_not_compaction(self):
        rows = [assistant("a", 1, 0, 50000), assistant("b", 1, 0, 45000)]
        p = os.path.join(self.tmp.name, "small.jsonl")
        write_jsonl(p, rows)
        self.assertEqual(cu.collect(p)["compactions"], [])

    def test_downsample_keeps_key_points(self):
        rows = [assistant("m%d" % i, 1, 0, 1000 + i) for i in range(1000)]
        p = os.path.join(self.tmp.name, "big.jsonl")
        write_jsonl(p, rows)
        d = cu.collect(p, max_points=50)
        self.assertLess(len(d["points"]), 200)
        idx = [q["i"] for q in d["points"]]
        self.assertIn(0, idx)
        self.assertIn(999, idx)
        self.assertEqual(d["turns"], 1000)


class ProjectNameTests(unittest.TestCase):
    def test_mac_linux_windows(self):
        self.assertEqual(cu.project_dir_name("/Users/name/proj"), "-Users-name-proj")
        self.assertEqual(cu.project_dir_name("/home/u/my.proj"), "-home-u-my-proj")
        self.assertEqual(cu.project_dir_name("C:\\dev\\x"), "C--dev-x")


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / "projects"
        self.pdir = self.base / cu.project_dir_name(os.getcwd())
        self.pdir.mkdir(parents=True)
        now = time.time()
        for i, name in enumerate(["old", "env", "arg", "newest"]):
            f = self.pdir / (name + ".jsonl")
            write_jsonl(f, [assistant(name, 1, 0, 1000)])
            os.utime(f, (now + i, now + i))  # "newest" has the latest mtime
        self.explicit = Path(self.tmp.name) / "explicit.jsonl"
        write_jsonl(self.explicit, [assistant("x", 1, 0, 1000)])
        self._env = os.environ.get("CLAUDE_CODE_SESSION_ID")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._env is None:
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        else:
            os.environ["CLAUDE_CODE_SESSION_ID"] = self._env

    def args(self, **kw):
        d = dict(path=None, session_id=None, projects_dir=str(self.base))
        d.update(kw)
        return argparse.Namespace(**d)

    def name(self, args):
        return Path(cu.find_jsonl(args)).stem

    def test_path_beats_everything(self):
        os.environ["CLAUDE_CODE_SESSION_ID"] = "env"
        a = self.args(path=str(self.explicit), session_id="arg")
        self.assertEqual(self.name(a), "explicit")

    def test_session_id_beats_env(self):
        os.environ["CLAUDE_CODE_SESSION_ID"] = "env"
        self.assertEqual(self.name(self.args(session_id="arg")), "arg")

    def test_env_beats_newest(self):
        os.environ["CLAUDE_CODE_SESSION_ID"] = "env"
        self.assertEqual(self.name(self.args()), "env")

    def test_fallback_to_newest_with_warning(self):
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        import io
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(self.name(self.args()), "newest")
        self.assertIn("warning", err.getvalue())

    def test_env_id_found_in_other_project_folder(self):
        other = self.base / "some-other-project"
        other.mkdir()
        write_jsonl(other / "elsewhere.jsonl", [assistant("e", 1, 0, 1000)])
        os.environ["CLAUDE_CODE_SESSION_ID"] = "elsewhere"
        self.assertEqual(self.name(self.args()), "elsewhere")

    def test_claude_config_dir(self):
        old = os.environ.get("CLAUDE_CONFIG_DIR")
        self.addCleanup(lambda: os.environ.__setitem__("CLAUDE_CONFIG_DIR", old) if old is not None
                        else os.environ.pop("CLAUDE_CONFIG_DIR", None))
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp.name
        self.assertEqual(cu.config_dir(), Path(self.tmp.name))


class MakeChartTests(unittest.TestCase):
    def test_html_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "sample.jsonl")
            write_jsonl(log, SAMPLE_ROWS)
            out = os.path.join(tmp, "sub", "chart.html")
            usage = {"tokensUsed": 25005, "contextWindow": 1000000, "percentUsed": 3,
                     "autoCompactsAtPercent": 97,
                     "categories": [{"name": "Messages", "tokens": 20000, "percent": 2},
                                    {"name": "System tools", "tokens": 5005, "percent": 1}]}
            uf = os.path.join(tmp, "usage.json")
            with open(uf, "w", encoding="utf-8") as f:
                json.dump({"context": usage}, f)
            r = subprocess.run([sys.executable, str(SCRIPTS / "make_chart.py"), "--path", log,
                                "--usage-file", uf, "--out", out],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                               encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            html = Path(out).read_text(encoding="utf-8")
            self.assertTrue(html.startswith("<!doctype html>"))
            self.assertIn("<svg", html)
            self.assertNotIn("hello", html)  # conversation text never reaches the output

    def test_assumed_usage_without_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "sample.jsonl")
            write_jsonl(log, SAMPLE_ROWS)
            out = os.path.join(tmp, "chart.html")
            r = subprocess.run([sys.executable, str(SCRIPTS / "make_chart.py"), "--path", log, "--out", out],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                               encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.isfile(out))


if __name__ == "__main__":
    unittest.main()
