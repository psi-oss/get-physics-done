"""Tests for the research verification kernel."""

from __future__ import annotations

from datetime import UTC, datetime

from gpd.core.kernel import (
    KERNEL_VERSION,
    Fail,
    Pass,
    RegistryBase,
    Result,
    run,
)

# -- Result type --


class TestResult:
    def test_pass_is_truthy(self):
        assert bool(Pass("ok")) is True

    def test_fail_is_falsy(self):
        assert bool(Fail("bad")) is False

    def test_result_fields(self):
        r = Result(passed=True, reason="test")
        assert r.passed is True
        assert r.reason == "test"


# -- RegistryBase --


class TestRegistryBase:
    def test_empty_registry_hashes(self):
        r = RegistryBase(raw_bytes=b"")
        h = r.content_hash()
        assert h.startswith("sha256:")
        assert len(h) > 10

    def test_different_bytes_different_hash(self):
        r1 = RegistryBase(raw_bytes=b"hello")
        r2 = RegistryBase(raw_bytes=b"world")
        assert r1.content_hash() != r2.content_hash()

    def test_same_bytes_same_hash(self):
        r1 = RegistryBase(raw_bytes=b"hello")
        r2 = RegistryBase(raw_bytes=b"hello")
        assert r1.content_hash() == r2.content_hash()

    def test_default_stats_empty(self):
        r = RegistryBase()
        assert r.stats() == {}

    def test_load_records_missing_dir(self, tmp_path):
        records = RegistryBase.load_records(
            tmp_path / "nonexistent", lambda d: d
        )
        assert records == []

    def test_load_records_single_object(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        (d / "a.json").write_text('{"id": "test-1"}')
        records = RegistryBase.load_records(d, lambda x: x)
        assert len(records) == 1
        assert records[0]["id"] == "test-1"

    def test_load_records_array(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        (d / "a.json").write_text('[{"id": "a"}, {"id": "b"}]')
        records = RegistryBase.load_records(d, lambda x: x)
        assert len(records) == 2

    def test_load_records_skips_dotfiles(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        (d / ".hidden.json").write_text('{"id": "hidden"}')
        (d / "visible.json").write_text('{"id": "visible"}')
        records = RegistryBase.load_records(d, lambda x: x)
        assert len(records) == 1
        assert records[0]["id"] == "visible"

    def test_collect_raw_bytes(self, tmp_path):
        d = tmp_path / "sub"
        d.mkdir()
        (d / "a.json").write_text('{"x": 1}')
        raw = RegistryBase.collect_raw_bytes(tmp_path, ["sub"])
        assert raw == b'{"x": 1}'

    def test_collect_raw_bytes_sorted(self, tmp_path):
        d = tmp_path / "sub"
        d.mkdir()
        (d / "b.json").write_text("B")
        (d / "a.json").write_text("A")
        raw = RegistryBase.collect_raw_bytes(tmp_path, ["sub"])
        assert raw == b"AB"


# -- Kernel runner --


class TestKernelRun:
    def _make_registry(self, raw: bytes = b"test") -> RegistryBase:
        return RegistryBase(raw_bytes=raw)

    def test_empty_predicates(self):
        verdict = run(self._make_registry(), {})
        assert verdict["overall"] == "PASS"
        assert verdict["total"] == 0

    def test_single_pass(self):
        preds = {"check_a": lambda _: Pass("ok")}
        verdict = run(self._make_registry(), preds)
        assert verdict["overall"] == "PASS"
        assert verdict["passed"] == 1
        assert verdict["total"] == 1

    def test_single_fail(self):
        preds = {"check_a": lambda _: Fail("bad")}
        verdict = run(self._make_registry(), preds)
        assert verdict["overall"] == "FAIL"
        assert verdict["failed"] == 1

    def test_mixed_results(self):
        preds = {
            "good": lambda _: Pass("ok"),
            "bad": lambda _: Fail("nope"),
        }
        verdict = run(self._make_registry(), preds)
        assert verdict["overall"] == "FAIL"
        assert verdict["passed"] == 1
        assert verdict["failed"] == 1

    def test_verdict_has_required_keys(self):
        verdict = run(self._make_registry(), {"a": lambda _: Pass()})
        required = {
            "kernel_version", "timestamp", "registry_hash",
            "predicates_hash", "registry_stats", "results",
            "passed", "failed", "total", "overall", "verdict_hash",
        }
        assert required <= set(verdict.keys())

    def test_verdict_version(self):
        verdict = run(self._make_registry(), {})
        assert verdict["kernel_version"] == KERNEL_VERSION

    def test_verdict_hash_is_content_addressed(self):
        reg = self._make_registry(b"stable")
        preds = {"a": lambda _: Pass("fixed")}
        v1 = run(reg, preds, generated_at=datetime(2026, 3, 18, 12, 0, tzinfo=UTC))
        v2 = run(reg, preds, generated_at=datetime(2026, 3, 18, 12, 5, tzinfo=UTC))
        assert v1["verdict_hash"] == v2["verdict_hash"]
        assert v1["registry_hash"] == v2["registry_hash"]
        assert v1["timestamp"] != v2["timestamp"]

    def test_verdict_registry_stats(self):
        class MyReg(RegistryBase):
            def stats(self):
                return {"items": 42}

        verdict = run(MyReg(), {})
        assert verdict["registry_stats"] == {"items": 42}

    def test_predicates_source_hash(self, tmp_path):
        src = tmp_path / "preds.py"
        src.write_text("# predicates")
        verdict = run(
            self._make_registry(), {"a": lambda _: Pass()},
            predicates_source=src,
        )
        assert verdict["predicates_hash"].startswith("sha256:")
        assert len(verdict["predicates_hash"]) > 10

    def test_no_predicates_source(self):
        verdict = run(self._make_registry(), {"a": lambda _: Pass()})
        assert verdict["predicates_hash"] == ""

    def test_deterministic_results(self):
        reg = self._make_registry(b"fixed")
        preds = {
            "a": lambda _: Pass("ok"),
            "b": lambda _: Fail("no"),
        }
        v1 = run(reg, preds)
        v2 = run(reg, preds)
        assert v1["results"] == v2["results"]
        assert v1["overall"] == v2["overall"]
        assert v1["registry_hash"] == v2["registry_hash"]


# -- Integration: subclass pattern --


class TestSubclassPattern:
    """Test that the intended usage pattern works: subclass RegistryBase,
    write domain predicates, pass to run()."""

    def test_domain_subclass(self, tmp_path):
        # Create a minimal domain registry
        d = tmp_path / "evidence"
        d.mkdir()
        (d / "data.json").write_text(
            '[{"id": "ev-1", "value": 10}, {"id": "ev-2", "value": -1}]'
        )

        class MyRecord:
            def __init__(self, d):
                self.id = d["id"]
                self.value = d["value"]

        class MyRegistry(RegistryBase):
            def __init__(self, records, raw_bytes):
                super().__init__(raw_bytes)
                self._records = records

            @classmethod
            def load(cls, path):
                records = cls.load_records(path / "evidence", lambda d: MyRecord(d))
                raw = cls.collect_raw_bytes(path, ["evidence"])
                return cls(records, raw)

            def records(self):
                return list(self._records)

            def stats(self):
                return {"records": len(self._records)}

        def check_positive(reg):
            for r in reg.records():
                if r.value < 0:
                    return Fail(f"{r.id} has negative value {r.value}")
            return Pass("all values positive")

        reg = MyRegistry.load(tmp_path)
        verdict = run(reg, {"positive_values": check_positive})

        assert verdict["overall"] == "FAIL"
        assert "ev-2" in verdict["results"]["positive_values"]["reason"]
        assert verdict["registry_stats"] == {"records": 2}
        assert verdict["registry_hash"].startswith("sha256:")
