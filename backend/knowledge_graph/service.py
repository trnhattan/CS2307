import re
import unicodedata

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.knowledge_graph.repository import KnowledgeGraphRepository
from backend.knowledge_graph.schemas import GraphEdge, GraphNode, KnowledgeGraphResponse


class KnowledgeGraphService:
    def __init__(
        self,
        repository: KnowledgeGraphRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.repository = repository
        self.session_factory = session_factory

    async def graph(
        self, student_id: int, *, technical: bool
    ) -> KnowledgeGraphResponse | None:
        async with self.session_factory() as session:
            student = await self.repository.student(session, student_id)
            if student is None:
                return None
            abilities = await self.repository.abilities(session, student_id)
            attempts = await self.repository.attempts(session, student_id)
            recommendations = await self.repository.recommendations(
                session, student["student_code"]
            )

        student_node = f"student:{student['student_code']}"
        student_label = self._english_label(
            student["display_name"],
            self._humanize_identifier(student["student_code"], "Exam taker"),
        )
        nodes: dict[str, GraphNode] = {
            student_node: GraphNode(
                id=student_node,
                label=student_label,
                type="student",
            )
        }
        edges: dict[tuple[str, str, str], GraphEdge] = {}
        unit_labels: dict[str, str] = {}
        for ability in abilities:
            subject_node = f"subject:{ability['subject_code']}"
            subject_label = self._subject_label(
                ability["subject_code"], ability["subject_name"]
            )
            nodes.setdefault(
                subject_node,
                GraphNode(
                    id=subject_node,
                    label=subject_label,
                    type="subject",
                ),
            )
            target = subject_node
            if ability["unit_code"]:
                target = f"unit:{ability['subject_code']}:{ability['unit_code']}"
                unit_label = self._english_label(
                    ability["unit_name"],
                    self._humanize_identifier(ability["unit_code"], "Knowledge area"),
                )
                unit_labels[ability["unit_code"]] = unit_label
                attributes = {
                    "knowledge_type": str(ability["unit_type"]).title(),
                    "understanding": self._mastery_label(ability["mastery_probability"]),
                    "evidence_count": ability["evidence_count"],
                }
                if technical:
                    attributes.update(
                        {
                            "theta": float(ability["theta"]),
                            "standard_error": float(ability["standard_error"]),
                            "mastery_probability": (
                                float(ability["mastery_probability"])
                                if ability["mastery_probability"] is not None
                                else None
                            ),
                        }
                    )
                nodes[target] = GraphNode(
                    id=target,
                    label=unit_label,
                    type=ability["unit_type"],
                    attributes=attributes,
                )
                self._edge(
                    edges,
                    target,
                    subject_node,
                    "belongs_to_subject",
                    {"source": "Course knowledge structure"},
                )
                if ability["parent_code"]:
                    parent = f"unit:{ability['subject_code']}:{ability['parent_code']}"
                    parent_label = self._english_label(
                        ability["parent_name"],
                        self._humanize_identifier(
                            ability["parent_code"], "Knowledge area"
                        ),
                    )
                    unit_labels[ability["parent_code"]] = parent_label
                    nodes.setdefault(
                        parent,
                        GraphNode(
                            id=parent,
                            label=parent_label,
                            type=ability["parent_type"] or "topic",
                        ),
                    )
                    self._edge(
                        edges,
                        parent,
                        target,
                        "prerequisite_of",
                        {"source": "Course prerequisite structure"},
                    )
            attributes = {
                "understanding": self._mastery_label(ability["mastery_probability"]),
                "evidence_count": ability["evidence_count"],
            }
            if technical:
                attributes.update(
                    {
                        "theta": float(ability["theta"]),
                        "standard_error": float(ability["standard_error"]),
                        "mastery_probability": (
                            float(ability["mastery_probability"])
                            if ability["mastery_probability"] is not None
                            else None
                        ),
                    }
                )
            self._edge(edges, student_node, target, "has_ability", attributes)

        for attempt in attempts:
            question_node = f"question:{attempt['question_code']}"
            evidence_node = f"evidence:{attempt['exam_item_id']}"
            result_label = "Correct" if attempt["is_correct"] else "Incorrect"
            subject_label = self._subject_label(
                attempt["subject_code"], attempt["subject_code"]
            )
            unit_label = next(
                (
                    unit_labels[unit_code]
                    for unit_code in attempt["unit_codes"]
                    if unit_code in unit_labels
                ),
                subject_label,
            )
            technical_question_label = self._english_label(
                attempt["stem"], f"Archived question about {unit_label}"
            )
            question_label = (
                technical_question_label
                if technical
                else f"Answered question about {unit_label}"
            )
            attributes = {"result": result_label}
            if technical and not technical_question_label.startswith("Archived question about "):
                attributes["question_text"] = technical_question_label
            nodes.setdefault(
                question_node,
                GraphNode(
                    id=question_node,
                    label=question_label,
                    type="question",
                    attributes=attributes,
                ),
            )
            evidence_attributes = {"result": result_label}
            if technical:
                evidence_attributes.update(
                    {
                        "answered_at": attempt["answered_at"].isoformat(),
                    }
                )
            nodes[evidence_node] = GraphNode(
                id=evidence_node,
                label=f"{result_label} response",
                type="evidence",
                attributes=evidence_attributes,
            )
            self._edge(
                edges,
                student_node,
                evidence_node,
                "produced_evidence",
                {"source": "Completed test response"},
            )
            self._edge(
                edges,
                evidence_node,
                question_node,
                "answers",
                {"correct": bool(attempt["is_correct"])},
            )
            for unit_code in attempt["unit_codes"]:
                unit_node = f"unit:{attempt['subject_code']}:{unit_code}"
                if unit_node in nodes:
                    self._edge(
                        edges,
                        question_node,
                        unit_node,
                        "measures",
                        {"source": "Question knowledge mapping"},
                    )
                    self._edge(
                        edges,
                        evidence_node,
                        unit_node,
                        "supports_ability",
                        {"source": "Completed test response"},
                    )

        unit_nodes = {
            node.id.rsplit(":", 1)[-1]: node.id
            for node in nodes.values()
            if node.type in {"topic", "skill"}
        }
        action_labels = {
            "remediate": "Review foundational knowledge",
            "reinforce": "Complete reinforcement practice",
            "advance": "Continue to advanced application",
            "initial_assessment": "Complete the first assessment",
        }
        for recommendation in recommendations:
            target = unit_nodes.get(recommendation["unit_code"])
            if target is None:
                continue
            provenance = {
                "recommendation": action_labels.get(
                    recommendation["action"], recommendation["action"]
                )
            }
            if technical:
                provenance.update(
                    {
                        "reasoning_trace": recommendation["inference_trace_id"],
                        "reasoning_rule": self._rule_label(
                            recommendation["derived_by_rule_code"]
                        ),
                    }
                )
            self._edge(edges, student_node, target, "recommended_next", provenance)

        return KnowledgeGraphResponse(
            student_id=student_id,
            student_code=student["student_code"],
            nodes=list(nodes.values()),
            edges=list(edges.values()),
        )

    @staticmethod
    def _mastery_label(value) -> str:
        if value is None:
            return "Insufficient evidence"
        probability = float(value)
        if probability < 0.5:
            return "Needs review"
        if probability < 0.75:
            return "Reinforcing"
        return "Mastered"

    @staticmethod
    def _subject_label(subject_code: str, value: str | None) -> str:
        known = {
            "DATABASE": "Database Systems",
            "NETWORK": "Computer Networks",
        }
        return known.get(
            subject_code,
            KnowledgeGraphService._english_label(
                value, KnowledgeGraphService._humanize_identifier(subject_code, "Subject")
            ),
        )

    @staticmethod
    def _english_label(value: str | None, fallback: str) -> str:
        text = " ".join(str(value or "").split()).strip()
        known = {
            "Sinh viên 1": "Student 1",
            "Sinh viên 2": "Student 2",
            "Cơ sở dữ liệu": "Database Systems",
            "Mạng máy tính": "Computer Networks",
        }
        if text in known:
            return known[text]
        normalized = unicodedata.normalize("NFKC", text)
        corrupted = bool(re.search(r"(?:\\?u00[0-9a-f]{2}|�)", normalized, re.IGNORECASE))
        vietnamese = bool(re.search(r"[À-ỹĐđ]", normalized))
        if not normalized or corrupted or vietnamese:
            return fallback
        ascii_text = (
            normalized.replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"')
            .replace("–", "-")
            .replace("—", "-")
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        return ascii_text or fallback

    @staticmethod
    def _humanize_identifier(value: str | None, fallback: str) -> str:
        tokens = [token for token in re.split(r"[_\-]+", str(value or "")) if token]
        while tokens and tokens[0].upper() in {"DB", "DATABASE", "NET", "NETWORK", "DBEN", "NETEN", "EN", "SK", "R"}:
            tokens.pop(0)
        acronyms = {
            "ACID", "ARP", "CIDR", "DDL", "DHCP", "DNS", "HTTPS", "ICMP",
            "IP", "IPV4", "JOIN", "MAC", "MTU", "MVCC", "NAT", "PAT",
            "PMTUD", "QOS", "RTP", "SQL", "STP", "TCP", "TLS", "TTL",
            "UDP", "VLAN", "VPN", "WAL",
        }
        words = [
            token.upper() if token.upper() in acronyms else token.lower()
            for token in tokens
        ]
        if not words:
            return fallback
        result = " ".join(words)
        return result[0].upper() + result[1:]

    @staticmethod
    def _rule_label(rule_code: str | None) -> str:
        labels = {
            "R_LEARNING_START_SUBJECT": "Start with an initial subject assessment",
            "R_LEARNING_REMEDIATE": "Review weak foundational knowledge",
            "R_LEARNING_REINFORCE": "Reinforce developing knowledge",
            "R_LEARNING_ADVANCE": "Advance mastered knowledge",
        }
        return labels.get(
            str(rule_code or ""),
            KnowledgeGraphService._humanize_identifier(
                rule_code, "Learning recommendation rule"
            ),
        )

    @staticmethod
    def _edge(
        edges: dict[tuple[str, str, str], GraphEdge],
        source: str,
        target: str,
        relation: str,
        provenance: dict,
    ) -> None:
        edges[(source, target, relation)] = GraphEdge(
            source=source,
            target=target,
            relation=relation,
            provenance=provenance,
        )
