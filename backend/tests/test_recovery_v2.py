
import json
from app.forensics.recovery.engine import RecoveryCandidate
from app.forensics.recovery.engine import RecoveryEngine

def test_1_three_compatible_dahua():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20}),
        RecoveryCandidate(candidate_id="C3", offset_bytes=200, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 21, "last_sequence": 30}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 1
    assert res["paths"][0]["candidate_ids"] == ["C1", "C2", "C3"]

def test_2_non_adjacent_physical_offset():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"channel": 1, "first_timestamp": 1000, "last_timestamp": 1050}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=500, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"channel": 1, "first_timestamp": 1055, "last_timestamp": 1100}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 1
    assert res["paths"][0]["candidate_ids"] == ["C1", "C2"]

def test_3_different_channels_reject():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"channel": 1}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"channel": 2}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 2

def test_4_codec_mismatch_reject():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"codec": "H264"}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"codec": "H265"}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 2

def test_5_missing_channel_metadata_does_not_reject():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"channel": 1, "first_sequence": 0, "last_sequence": 10}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 1
    assert res["paths"][0]["candidate_ids"] == ["C1", "C2"]

def test_6_small_sequence_gap():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 15, "last_sequence": 20}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 1
    assert res["paths"][0]["unresolved_gaps"] == 1
    assert len(res["paths"][0]["discontinuities"]) == 1

def test_7_impossible_sequence_regression():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 500, "last_sequence": 510}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 100, "last_sequence": 110}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 2

def test_8_timestamp_regression_rejects():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 10, "last_sequence": 20, "first_timestamp": 5000, "last_timestamp": 5100}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 100, "last_sequence": 110, "first_timestamp": 1000, "last_timestamp": 1100}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 2

def test_9_16bit_sequence_wrap():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 65530, "last_sequence": 65535}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 1
    assert res["paths"][0]["candidate_ids"] == ["C1", "C2"]

def test_10_adjacent_but_incompatible():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"channel": 1}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"channel": 2}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 2

def test_11_multiple_possibilities_deterministic():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10, "channel": 1}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 16, "last_sequence": 20, "channel": 1}),
        RecoveryCandidate(candidate_id="C3", offset_bytes=200, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20, "channel": 1}),
    ]
    res = engine.reconstruct_fragments(cands)
    paths = res["paths"]
    path_c1 = next(p for p in paths if p["candidate_ids"][0] == "C1")
    assert path_c1["candidate_ids"] == ["C1", "C3"]

def test_12_deterministic_serialization():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20}),
    ]
    res1 = engine.reconstruct_fragments(cands)
    res2 = engine.reconstruct_fragments(cands)
    assert json.dumps(res1, sort_keys=True) == json.dumps(res2, sort_keys=True)

def test_13_vendor_format_mismatch():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Hikvision", format_name="HIKV", confidence=1.0, signature_matched=True),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 2
    for e in res["edges"]:
        assert e["rejected"] is True

def test_14_no_duplicates_in_path():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 1
    path_cands = res["paths"][0]["candidate_ids"]
    assert len(path_cands) == len(set(path_cands))

def test_15_no_fabricated_metadata():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True),
    ]
    res = engine.reconstruct_fragments(cands)
    node = res["nodes"][0]
    assert node["channel"] is None
    assert node["sequence_start"] is None
    assert node["first_timestamp"] is None

def test_16_frame_score_contributes():
    engine = RecoveryEngine()
    cands1 = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20}),
    ]
    res1 = engine.reconstruct_fragments(cands1)

    cands2 = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10, "gop_sequence_end": 5}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20, "gop_sequence_start": 6}),
    ]
    res2 = engine.reconstruct_fragments(cands2)

    score1 = res1["paths"][0]["total_score"]
    score2 = res2["paths"][0]["total_score"]
    assert score2 > score1

def test_17_incompatible_gop_rejects():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10, "gop_sequence_end": 5}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20, "gop_sequence_start": 8}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 2

def test_18_missing_gop_metadata_neutral():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10, "gop_sequence_end": 5}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20}),
    ]
    res = engine.reconstruct_fragments(cands)
    assert len(res["paths"]) == 1

def test_19_graph_explicitly_acyclic():
    engine = RecoveryEngine()
    # If a graph were cyclic, C1 -> C2 and C2 -> C1 would both be valid if they had equal timestamps and adjacent physically in a loop
    # We test that even without timestamps, backward physical offset is rejected, preventing cycle
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 11, "last_sequence": 20}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=0, length_bytes=50, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_sequence": 0, "last_sequence": 10}),
    ]
    res = engine.reconstruct_fragments(cands)
    # C2 offset 0 < C1 offset 100. So C2 -> C1 is allowed physically. C1 -> C2 is rejected.
    path_c2 = next(p for p in res["paths"] if p["candidate_ids"][0] == "C2")
    assert path_c2["candidate_ids"] == ["C2", "C1"]

def test_20_reverse_ordering_cannot_create_cycle():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_timestamp": 1000}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=200, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_timestamp": 1000}),
    ]
    res = engine.reconstruct_fragments(cands)
    # Both have timestamp 1000. C1 offset < C2 offset, so C1 -> C2 is allowed. C2 -> C1 must be rejected.
    assert len(res["paths"]) == 1
    assert res["paths"][0]["candidate_ids"] == ["C1", "C2"]

def test_21_tie_breaking():
    engine = RecoveryEngine()
    # C1 can go to C2 or C3 with exact same score
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_timestamp": 1000, "last_timestamp": 1010}),
        RecoveryCandidate(candidate_id="C3", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_timestamp": 1011, "last_timestamp": 1020}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_timestamp": 1011, "last_timestamp": 1020}),
    ]
    res = engine.reconstruct_fragments(cands)
    # Tie broken lexicographically -> C2 < C3
    assert res["paths"][0]["candidate_ids"] == ["C1", "C2"]

def test_22_identical_output_regardless_of_order():
    engine = RecoveryEngine()
    cands = [
        RecoveryCandidate(candidate_id="C1", offset_bytes=0, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_timestamp": 1000, "last_timestamp": 1010}),
        RecoveryCandidate(candidate_id="C2", offset_bytes=100, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_timestamp": 1011, "last_timestamp": 1020}),
        RecoveryCandidate(candidate_id="C3", offset_bytes=200, length_bytes=100, detected_vendor="Dahua", format_name="DHAV", confidence=1.0, signature_matched=True, metadata={"first_timestamp": 1021, "last_timestamp": 1030}),
    ]

    import itertools
    results = []
    for p in itertools.permutations(cands):
        res = engine.reconstruct_fragments(list(p))
        # Zero out nodes list since that retains original order, we care about paths and edges
        res["nodes"] = []
        res["edges"] = sorted(res["edges"], key=lambda e: (e["from_candidate_id"], e["to_candidate_id"]))
        results.append(json.dumps(res, sort_keys=True))

    assert all(r == results[0] for r in results)
