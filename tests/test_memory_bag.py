from app.services import memory_bag, rag

PAGE = "<html><body><p>" + " ".join(["Syarat lesen gerai pasar malam hendaklah dipatuhi oleh setiap penjaja berdaftar."] * 6) + "</p></body></html>"


def test_add_update_delete_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_bag, "DB", tmp_path / "bag.db")
    monkeypatch.setattr(memory_bag, "CORPUS", tmp_path)
    monkeypatch.setattr(rag, "CORPUS", tmp_path)
    meta = {"title_en": "Night market rules", "dept": "local_gov", "kind": "guideline", "doc_id": "night_market"}

    r = memory_bag.add_manual(meta, "night_market.html", PAGE.encode())
    assert r["op"] == "add" and r["chunks"] >= 1
    assert any(h["doc_id"] == "night_market" for h in rag.search("lesen gerai pasar malam", dept="local_gov"))

    assert memory_bag.add_manual(meta, "night_market.html", PAGE.encode())["op"] == "unchanged"  # no re-scan
    assert memory_bag.add_manual(meta, "night_market.html", PAGE.replace("malam", "pagi").encode())["op"] == "update"

    memory_bag.delete_doc("night_market")
    assert not any(h["doc_id"] == "night_market" for h in rag.search("lesen gerai pasar", dept="local_gov"))
    memory_bag.restore_doc("night_market")
    assert any(h["doc_id"] == "night_market" for h in rag.search("lesen gerai pasar", dept="local_gov"))

    ops = [e["op"] for e in memory_bag.status()["recent_changes"]][::-1]
    assert ops == ["add", "update", "delete", "add"]
    rag.invalidate()
