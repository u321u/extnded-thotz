from extnded_thotz.history import History


def test_append_and_read_back(tmp_path):
    h = History(tmp_path / "h.jsonl")
    h.append("first", 1.2, "local")
    h.append("second", 0.8, "local")
    entries = h.last()
    assert [e["text"] for e in entries] == ["first", "second"]
    assert entries[0]["backend"] == "local"
    assert "ts" in entries[0]


def test_last_n_limits(tmp_path):
    h = History(tmp_path / "h.jsonl")
    for i in range(30):
        h.append(f"t{i}")
    assert len(h.last(5)) == 5
    assert h.last(5)[-1]["text"] == "t29"


def test_corrupt_lines_skipped(tmp_path):
    p = tmp_path / "h.jsonl"
    h = History(p)
    h.append("good")
    with open(p, "a", encoding="utf-8") as f:
        f.write("{broken\n")
    h.append("also good")
    assert [e["text"] for e in h.last()] == ["good", "also good"]


def test_empty_history(tmp_path):
    assert History(tmp_path / "none.jsonl").last() == []
