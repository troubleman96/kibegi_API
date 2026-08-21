from app.extract import chunk_text, should_process


def test_supported_types_match_file_gate():
    assert should_process("report.pdf", "other")
    assert should_process("notes.bin", "document")
    assert should_process("slides.pptx", "presentation")
    assert not should_process("photo.png", "image")


def test_chunking_preserves_overlap_and_content():
    source = "A" * 700 + "\n\n" + "B" * 700
    chunks = chunk_text(source, chunk_size=800, overlap=100)
    assert len(chunks) >= 2
    assert "A" in chunks[0]
    assert "B" in chunks[-1]
    assert all(chunk.strip() for chunk in chunks)
