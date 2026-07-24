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
        nodes: dict[str, GraphNode] = {
            student_node: GraphNode(
                id=student_node,
                label=student["display_name"],
                type="student",
            )
        }
        edges: dict[tuple[str, str, str], GraphEdge] = {}
        for ability in abilities:
            subject_node = f"subject:{ability['subject_code']}"
            nodes.setdefault(
                subject_node,
                GraphNode(
                    id=subject_node,
                    label=ability["subject_name"],
                    type="subject",
                ),
            )
            target = subject_node
            if ability["unit_code"]:
                target = f"unit:{ability['subject_code']}:{ability['unit_code']}"
                attributes = {
                    "unit_type": ability["unit_type"],
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
                    label=ability["unit_name"],
                    type=ability["unit_type"],
                    attributes=attributes,
                )
                self._edge(
                    edges,
                    target,
                    subject_node,
                    "belongs_to_subject",
                    {"source": "knowledge_units"},
                )
                if ability["parent_code"]:
                    parent = f"unit:{ability['subject_code']}:{ability['parent_code']}"
                    nodes.setdefault(
                        parent,
                        GraphNode(
                            id=parent,
                            label=ability["parent_name"] or ability["parent_code"],
                            type=ability["parent_type"] or "topic",
                        ),
                    )
                    self._edge(
                        edges,
                        parent,
                        target,
                        "prerequisite_of",
                        {"source": "knowledge_units.parent_unit_id"},
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
            attributes = {"answered": True, "correct": bool(attempt["is_correct"])}
            if technical:
                attributes["stem"] = attempt["stem"]
            nodes.setdefault(
                question_node,
                GraphNode(
                    id=question_node,
                    label=attempt["question_code"],
                    type="question",
                    attributes=attributes,
                ),
            )
            evidence_attributes = {"correct": bool(attempt["is_correct"])}
            if technical:
                evidence_attributes.update(
                    {
                        "exam_item_id": attempt["exam_item_id"],
                        "answered_at": attempt["answered_at"].isoformat(),
                    }
                )
            nodes[evidence_node] = GraphNode(
                id=evidence_node,
                label="Bằng chứng trả lời",
                type="evidence",
                attributes=evidence_attributes,
            )
            self._edge(
                edges,
                student_node,
                evidence_node,
                "produced_evidence",
                {"source": "exam_items"},
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
                        {"source": "question_knowledge_units"},
                    )
                    self._edge(
                        edges,
                        evidence_node,
                        unit_node,
                        "supports_ability",
                        {"source": "exam_items"},
                    )

        unit_nodes = {
            node.id.rsplit(":", 1)[-1]: node.id
            for node in nodes.values()
            if node.type in {"topic", "skill"}
        }
        action_labels = {
            "remediate": "Ôn lại kiến thức nền",
            "reinforce": "Luyện tập củng cố",
            "advance": "Chuyển sang vận dụng nâng cao",
            "initial_assessment": "Hoàn thành bài đánh giá đầu tiên",
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
                        "trace_id": recommendation["inference_trace_id"],
                        "rule_code": recommendation["derived_by_rule_code"],
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
            return "Chưa đủ bằng chứng"
        probability = float(value)
        if probability < 0.5:
            return "Cần ôn tập"
        if probability < 0.75:
            return "Đang củng cố"
        return "Đã nắm vững"

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
