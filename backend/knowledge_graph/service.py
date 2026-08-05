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
            subjects = await self.repository.subjects(session, student_id)
            criteria = await self.repository.criteria(session, student_id)
            attempts = await self.repository.attempts(session, student_id)
            config = await self.repository.config(session)

        minimum_tests = int(config.get("PROFILE_GRAPH_MIN_TESTS", 3))
        needs_review = float(config.get("PROFILE_NEEDS_REVIEW_THRESHOLD", 0.45))
        developing = float(config.get("PROFILE_DEVELOPING_THRESHOLD", 0.60))
        mastered = float(config.get("PROFILE_MASTERY_THRESHOLD", 0.75))

        student_node = f"student:{student['student_code']}"
        nodes: dict[str, GraphNode] = {
            student_node: GraphNode(
                id=student_node,
                label=self._english_label(
                    student["display_name"],
                    self._humanize_identifier(student["student_code"], "Exam taker"),
                ),
                type="student",
            )
        }
        edges: dict[tuple[str, str, str], GraphEdge] = {}
        subject_by_code = {subject["subject_code"]: subject for subject in subjects}

        for subject in subjects:
            subject_node = f"subject:{subject['subject_code']}"
            completed_tests = int(subject.get("completed_tests") or 0)
            subject_mastery = (
                float(subject["mastery_probability"])
                if subject.get("mastery_probability") is not None else None
            )
            relationship, display_label = self._mastery_relation(
                subject_mastery,
                evidence_count=int(subject.get("evidence_count") or 0),
                completed_tests=completed_tests,
                minimum_tests=minimum_tests,
                needs_review=needs_review,
                developing=developing,
                mastered=mastered,
                subject=True,
            )
            nodes[subject_node] = GraphNode(
                id=subject_node,
                label=self._subject_label(
                    subject["subject_code"], subject["subject_name"]
                ),
                type="subject",
                attributes={
                    "understanding": self._mastery_label(
                        subject_mastery,
                        int(subject.get("evidence_count") or 0),
                        reliable=completed_tests >= minimum_tests,
                        needs_review=needs_review,
                        developing=developing,
                        mastered=mastered,
                    ),
                    "completed_tests": completed_tests,
                    "mastery_percent": (
                        round(100 * subject_mastery, 1)
                        if subject_mastery is not None else None
                    ),
                },
            )
            self._edge(
                edges,
                student_node,
                subject_node,
                relationship,
                {
                    "relationship": "Learner subject understanding",
                    "completed_tests": completed_tests,
                    "mastery_percent": (
                        round(100 * subject_mastery, 1)
                        if subject_mastery is not None else None
                    ),
                },
                display_label=display_label,
            )

        for criterion in criteria:
            subject_node = f"subject:{criterion['subject_code']}"
            criterion_node = (
                f"criterion:{criterion['subject_code']}:{criterion['criterion_code']}"
            )
            mastery = (
                float(criterion["mastery_probability"])
                if criterion["mastery_probability"] is not None
                else None
            )
            evidence_count = int(criterion["evidence_count"] or 0)
            subject = subject_by_code[criterion["subject_code"]]
            completed_tests = int(subject.get("completed_tests") or 0)
            reliable = completed_tests >= minimum_tests and evidence_count >= minimum_tests
            understanding = self._mastery_label(
                mastery,
                evidence_count,
                reliable=reliable,
                needs_review=needs_review,
                developing=developing,
                mastered=mastered,
            )
            relationship, display_label = self._mastery_relation(
                mastery,
                evidence_count=evidence_count,
                completed_tests=completed_tests,
                minimum_tests=minimum_tests,
                needs_review=needs_review,
                developing=developing,
                mastered=mastered,
                subject=False,
            )
            attributes = {
                "learning_objective": criterion["learning_objective"],
                "success_statement": criterion["success_statement"],
                "understanding": understanding,
                "evidence_count": evidence_count,
                "accuracy_percent": (
                    float(criterion["accuracy_percent"])
                    if criterion["accuracy_percent"] is not None
                    else None
                ),
            }
            if technical:
                attributes.update(
                    {
                        "theta": (
                            float(criterion["theta"])
                            if criterion["theta"] is not None
                            else None
                        ),
                        "standard_error": (
                            float(criterion["standard_error"])
                            if criterion["standard_error"] is not None
                            else None
                        ),
                        "mastery_probability": mastery,
                    }
                )
            nodes[criterion_node] = GraphNode(
                id=criterion_node,
                label=self._english_label(
                    criterion["criterion_name"],
                    self._humanize_identifier(
                        criterion["criterion_code"], "Assessment criterion"
                    ),
                ),
                type="criterion",
                attributes=attributes,
            )
            self._edge(
                edges,
                subject_node,
                criterion_node,
                relationship,
                {
                    "understanding": understanding,
                    "evidence_count": evidence_count,
                    "mastery_percent": (
                        round(100 * mastery, 1) if mastery is not None else None
                    ),
                },
                display_label=display_label,
            )

        for attempt in attempts:
            criterion_nodes = [
                f"criterion:{attempt['subject_code']}:{criterion_code}"
                for criterion_code in attempt["criterion_codes"]
                if f"criterion:{attempt['subject_code']}:{criterion_code}" in nodes
            ]
            if not criterion_nodes:
                continue
            question_node = f"question:{attempt['exam_item_id']}"
            result_label = "Correct" if attempt["is_correct"] else "Incorrect"
            question_text = self._english_label(
                attempt["stem"],
                f"Answered question {attempt['question_code']}",
            )
            question_attributes = {
                "question_text": question_text,
                "question_code": attempt["question_code"],
                "result": result_label,
                "difficulty": str(attempt["difficulty_label"]).title(),
                "answered_at": attempt["answered_at"].isoformat(),
            }
            if technical:
                question_attributes["bloom_level"] = str(
                    attempt["bloom_level"]
                ).title()
            nodes[question_node] = GraphNode(
                id=question_node,
                label=question_text,
                type="question",
                attributes=question_attributes,
            )
            for criterion_node in criterion_nodes:
                self._edge(
                    edges,
                    criterion_node,
                    question_node,
                    "answered_question",
                    {
                        "answer_result": result_label,
                        "difficulty": str(attempt["difficulty_label"]).title(),
                    },
                )

        return KnowledgeGraphResponse(
            student_id=student_id,
            student_code=student["student_code"],
            nodes=list(nodes.values()),
            edges=list(edges.values()),
        )

    @staticmethod
    def _mastery_label(
        value: float | None,
        evidence_count: int,
        *,
        reliable: bool = True,
        needs_review: float = 0.45,
        developing: float = 0.60,
        mastered: float = 0.75,
    ) -> str:
        if value is None or evidence_count == 0:
            return "Not assessed"
        if not reliable:
            return "Initial evidence"
        if value < needs_review:
            return "Needs review"
        if value < developing:
            return "Developing"
        if value < mastered:
            return "Understands"
        return "Mastered"

    @classmethod
    def _mastery_relation(
        cls,
        value: float | None,
        *,
        evidence_count: int,
        completed_tests: int,
        minimum_tests: int,
        needs_review: float,
        developing: float,
        mastered: float,
        subject: bool,
    ) -> tuple[str, str]:
        if completed_tests < minimum_tests or evidence_count < minimum_tests or value is None:
            return (
                ("has_subject", "Has learning profile for")
                if subject else ("has_criterion", "Requires understanding of")
            )
        percent = round(100 * value)
        prefix = "subject" if subject else "criterion"
        if value < needs_review:
            return f"{prefix}_needs_review", f"Needs review · {percent}%"
        if value < developing:
            return f"{prefix}_developing", f"Developing · {percent}%"
        if value < mastered:
            return f"{prefix}_understands", f"Understands · {percent}%"
        label = "Proficient" if subject else "Mastered"
        return f"{prefix}_mastered", f"{label} · {percent}%"

    @staticmethod
    def _subject_label(subject_code: str, value: str | None) -> str:
        known = {
            "DATABASE": "Database Systems",
            "NETWORK": "Computer Networks",
        }
        return known.get(
            subject_code,
            KnowledgeGraphService._english_label(
                value,
                KnowledgeGraphService._humanize_identifier(subject_code, "Subject"),
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
        while tokens and tokens[0].upper() in {
            "DB", "DATABASE", "NET", "NETWORK", "DBEN", "NETEN", "EN", "SK", "R"
        }:
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
    def _edge(
        edges: dict[tuple[str, str, str], GraphEdge],
        source: str,
        target: str,
        relation: str,
        provenance: dict,
        display_label: str | None = None,
    ) -> None:
        edges[(source, target, relation)] = GraphEdge(
            source=source,
            target=target,
            relation=relation,
            display_label=display_label,
            provenance=provenance,
        )
