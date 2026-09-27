from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class FragmentDescriptor:
    candidate_id: str
    source_offset: int
    length_bytes: int
    vendor: str
    format_name: str
    channel: Optional[int] = None
    sequence_start: Optional[int] = None
    sequence_end: Optional[int] = None
    first_timestamp: Optional[int] = None
    last_timestamp: Optional[int] = None
    codec: Optional[str] = None
    frame_count: Optional[int] = None
    keyframe_count: Optional[int] = None
    gop_sequence_start: Optional[int] = None
    gop_sequence_end: Optional[int] = None

@dataclass
class FragmentEdge:
    from_candidate_id: str
    to_candidate_id: str
    score: float = 0.0
    sequence_score: float = 0.0
    timestamp_score: float = 0.0
    channel_score: float = 0.0
    codec_score: float = 0.0
    frame_score: float = 0.0
    offset_score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    rejected: bool = False
    rejection_reason: Optional[str] = None

@dataclass
class ReconstructedPath:
    path_id: str
    candidate_ids: List[str]
    total_score: float
    average_edge_score: float
    confidence: float
    unresolved_gaps: int
    discontinuities: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class GraphReconstructor:
    def __init__(self):
        self.weights = {
            "sequence": 0.30,
            "timestamp": 0.25,
            "channel": 0.20,
            "codec": 0.10,
            "frame": 0.10,
            "offset": 0.05
        }

    def evaluate_edge(self, c1: FragmentDescriptor, c2: FragmentDescriptor) -> FragmentEdge:
        edge = FragmentEdge(from_candidate_id=c1.candidate_id, to_candidate_id=c2.candidate_id)

        # 1. DAG directionality rule
        if c1.first_timestamp is not None and c2.first_timestamp is not None:
            if c2.first_timestamp < c1.first_timestamp:
                edge.rejected = True
                edge.rejection_reason = "Timestamp regression prevents forward edge"
                return edge
            elif c2.first_timestamp == c1.first_timestamp:
                if c2.source_offset <= c1.source_offset:
                    edge.rejected = True
                    edge.rejection_reason = "Equal timestamp but non-forward physical offset"
                    return edge
        else:
            if c2.source_offset <= c1.source_offset:
                edge.rejected = True
                edge.rejection_reason = "Non-forward physical offset without timestamp progression"
                return edge

        if c1.vendor != c2.vendor or c1.format_name != c2.format_name:
            edge.rejected = True
            edge.rejection_reason = "Vendor or format mismatch"
            return edge

        if c1.codec is not None and c2.codec is not None:
            if c1.codec != c2.codec:
                edge.rejected = True
                edge.rejection_reason = "Explicit codec mismatch"
                return edge
            edge.codec_score = self.weights["codec"]
            edge.reasons.append("Codec match")

        if c1.channel is not None and c2.channel is not None:
            if c1.channel != c2.channel:
                edge.rejected = True
                edge.rejection_reason = "Explicit channel mismatch"
                return edge
            edge.channel_score = self.weights["channel"]
            edge.reasons.append("Channel match")

        if c1.sequence_end is not None and c2.sequence_start is not None:
            expected_seq = (c1.sequence_end + 1) % 65536
            diff = (c2.sequence_start - expected_seq) % 65536

            if diff == 0:
                edge.sequence_score = self.weights["sequence"]
                edge.reasons.append("Exact sequence continuation")
            elif diff < 100:
                edge.sequence_score = self.weights["sequence"] * 0.5
                edge.reasons.append(f"Small sequence gap ({diff})")
            else:
                edge.rejected = True
                edge.rejection_reason = "Impossible or large backward sequence transition"
                return edge

        if c1.last_timestamp is not None and c2.first_timestamp is not None:
            t_diff = c2.first_timestamp - c1.last_timestamp
            if t_diff < 0:
                edge.rejected = True
                edge.rejection_reason = "Impossible reverse-time transition"
                return edge
            elif t_diff < 10:
                edge.timestamp_score = self.weights["timestamp"]
                edge.reasons.append("Plausible temporal continuity")
            elif t_diff < 3600:
                edge.timestamp_score = self.weights["timestamp"] * 0.5
                edge.reasons.append(f"Unexplained time gap ({t_diff} ticks)")
            else:
                edge.timestamp_score = self.weights["timestamp"] * 0.1
                edge.reasons.append(f"Large unexplained time gap ({t_diff} ticks)")

        if c1.gop_sequence_end is not None and c2.gop_sequence_start is not None:
            if c1.gop_sequence_end + 1 == c2.gop_sequence_start:
                edge.frame_score = self.weights["frame"]
                edge.reasons.append("GOP continuity matched")
            else:
                edge.rejected = True
                edge.rejection_reason = "Explicit GOP discontinuity"
                return edge

        offset_diff = c2.source_offset - (c1.source_offset + c1.length_bytes)
        if offset_diff == 0:
            edge.offset_score = self.weights["offset"]
            edge.reasons.append("Perfect physical adjacency")
        elif offset_diff > 0:
            edge.offset_score = self.weights["offset"] * 0.5
            edge.reasons.append(f"Positive physical offset ({offset_diff} bytes)")
        else:
            edge.offset_score = 0.0
            edge.reasons.append(f"Negative physical offset ({offset_diff} bytes)")

        edge.score = (
            edge.sequence_score +
            edge.timestamp_score +
            edge.channel_score +
            edge.codec_score +
            edge.frame_score +
            edge.offset_score
        )

        if edge.score == 0.0:
            edge.score = 0.01
            edge.reasons.append("Weak structural fallback")

        return edge

    def reconstruct(self, candidates: List[FragmentDescriptor]) -> Dict[str, Any]:
        edges = []
        adj = {c.candidate_id: [] for c in candidates}

        for c1 in candidates:
            for c2 in candidates:
                if c1.candidate_id == c2.candidate_id: continue
                edge = self.evaluate_edge(c1, c2)
                if not edge.rejected and edge.score > 0:
                    edges.append(edge)
                    adj[c1.candidate_id].append(edge)

        paths = []
        used_cands = set()

        while True:
            rem = {c.candidate_id for c in candidates if c.candidate_id not in used_cands}
            if not rem: break

            memo = {}
            def dp(node):
                if node in memo: return memo[node]

                best_score = 0.0
                best_avg = 0.0
                best_path = [node]
                best_edges = []

                # outgoing edges constrained to remaining nodes
                outgoing = [e for e in adj[node] if e.to_candidate_id in rem]

                for edge in outgoing:
                    nxt = edge.to_candidate_id
                    sub_score, sub_avg, sub_path, sub_edges = dp(nxt)

                    cand_score = edge.score + sub_score
                    cand_edges = [edge] + sub_edges
                    cand_avg = cand_score / len(cand_edges) if cand_edges else 0.0
                    cand_path = [node] + sub_path

                    # Tie-breaking logic
                    is_better = False
                    if cand_score > best_score:
                        is_better = True
                    elif cand_score == best_score and best_score > 0:
                        if cand_avg > best_avg:
                            is_better = True
                        elif cand_avg == best_avg:
                            # Lexicographically smaller sequence of IDs
                            if cand_path < best_path:
                                is_better = True
                    elif best_score == 0.0 and cand_score == 0.0:
                        if cand_path < best_path:
                            is_better = True

                    if is_better:
                        best_score = cand_score
                        best_avg = cand_avg
                        best_path = cand_path
                        best_edges = cand_edges

                memo[node] = (best_score, best_avg, best_path, best_edges)
                return memo[node]

            overall_best_score = -1.0
            overall_best_avg = -1.0
            overall_best_path = []
            overall_best_edges = []

            for start_node in list(rem):
                score, avg, path, edges_list = dp(start_node)

                is_better = False
                if score > overall_best_score:
                    is_better = True
                elif score == overall_best_score:
                    if avg > overall_best_avg:
                        is_better = True
                    elif avg == overall_best_avg:
                        if not overall_best_path or path < overall_best_path:
                            is_better = True

                if is_better:
                    overall_best_score = score
                    overall_best_avg = avg
                    overall_best_path = path
                    overall_best_edges = edges_list

            if not overall_best_path:
                break

            if len(overall_best_path) == 1:
                node = overall_best_path[0]
                paths.append(ReconstructedPath(
                    path_id=f"PATH-{node}",
                    candidate_ids=[node],
                    total_score=0.0,
                    average_edge_score=0.0,
                    confidence=0.5,
                    unresolved_gaps=0,
                    discontinuities=[],
                    metadata={"status": "PROBABLE_RECONSTRUCTION"}
                ))
                used_cands.add(node)
                continue

            discontinuities = []
            for e in overall_best_edges:
                has_gap = any("gap" in r.lower() for r in e.reasons)
                if has_gap:
                    discontinuities.append({
                        "from": e.from_candidate_id,
                        "to": e.to_candidate_id,
                        "reasons": e.reasons
                    })

            conf = min(0.99, 0.5 + (overall_best_avg * 0.5))

            paths.append(ReconstructedPath(
                path_id=f"PATH-{overall_best_path[0]}",
                candidate_ids=overall_best_path,
                total_score=overall_best_score,
                average_edge_score=overall_best_avg,
                confidence=conf,
                unresolved_gaps=len(discontinuities),
                discontinuities=discontinuities,
                metadata={"status": "PROBABLE_RECONSTRUCTION"}
            ))

            for n in overall_best_path:
                used_cands.add(n)

        # Final deterministic sort of paths just in case
        paths.sort(key=lambda p: (-p.total_score, -p.average_edge_score, p.candidate_ids))

        return {
            "method": "FRAGMENT_GRAPH_RECONSTRUCTION_V1",
            "nodes": [c.__dict__ for c in candidates],
            "edges": [e.__dict__ for e in edges],
            "paths": [p.__dict__ for p in paths]
        }
