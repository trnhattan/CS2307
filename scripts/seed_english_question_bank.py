import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from backend.admin.repository import AdminRepository
from backend.admin.service import AdminService
from backend.db.session import async_session_factory
from backend.generation.rubric import initial_irt


@dataclass(frozen=True, slots=True)
class Concept:
    code: str
    name: str
    topic_code: str
    topic_name: str
    context: str
    definition: str
    practical: str
    benefit: str


DATABASE_CONCEPTS = [
    Concept("PRIMARY_KEY", "primary key", "DB_EN_RELATIONAL", "Relational Design", "an online bookstore schema", "A column or minimal column set that uniquely identifies every row and cannot be NULL.", "assign a stable unique identifier to each book record", "each row can be referenced without ambiguity"),
    Concept("FOREIGN_KEY", "foreign key", "DB_EN_RELATIONAL", "Relational Design", "a hospital appointment migration", "A constraint whose values must reference an existing candidate key in a related table, unless NULL is permitted.", "prevent an appointment from referencing a patient that does not exist", "relationships retain referential integrity"),
    Concept("THIRD_NORMAL_FORM", "third normal form", "DB_EN_RELATIONAL", "Relational Design", "a university enrollment redesign", "A normalization condition that removes non-key attributes that depend transitively on a candidate key.", "separate department details from rows that store individual students", "update anomalies and redundant descriptive data are reduced"),
    Concept("JUNCTION_TABLE", "junction table", "DB_EN_RELATIONAL", "Relational Design", "a music playlist service", "A relation that represents a many-to-many association by storing foreign keys to both participating entities.", "store membership between playlists and songs as one row per association", "many-to-many membership can be constrained and queried directly"),
    Concept("WHERE", "WHERE clause", "DB_EN_SQL", "SQL Querying", "a retail order report", "A SQL clause that filters individual rows before grouping and aggregate calculation.", "exclude cancelled orders before computing regional totals", "only qualifying source rows participate in later query stages"),
    Concept("HAVING", "HAVING clause", "DB_EN_SQL", "SQL Querying", "a subscription analytics query", "A SQL clause that filters groups after GROUP BY and aggregate calculation.", "retain customer groups whose SUM(amount) exceeds a threshold", "aggregate conditions are applied to completed groups"),
    Concept("LEFT_JOIN", "LEFT JOIN", "DB_EN_SQL", "SQL Querying", "a customer engagement audit", "A join that keeps every row from the left input and fills unmatched right-side columns with NULL.", "list all customers including those who have never placed an order", "the result preserves unmatched entities from the required side"),
    Concept("WINDOW_FUNCTION", "window function", "DB_EN_SQL", "SQL Querying", "a salary ranking dashboard", "A calculation over a related row window that does not collapse the result into one row per group.", "rank employees within each department while retaining every employee row", "analytical values and row-level detail remain together"),
    Concept("ATOMICITY", "transaction atomicity", "DB_EN_TX", "Transactions and Concurrency", "a wallet transfer service", "The ACID property that makes all operations in a transaction succeed together or have no effect.", "debit one account and credit another inside one transaction", "a partial business operation cannot remain committed"),
    Concept("ISOLATION", "transaction isolation", "DB_EN_TX", "Transactions and Concurrency", "a ticket reservation platform", "The ACID property that controls how concurrent transactions observe and interfere with one another.", "select an isolation level that prevents two buyers from confirming the same seat", "concurrent execution behaves within a defined consistency boundary"),
    Concept("MVCC", "multi-version concurrency control", "DB_EN_TX", "Transactions and Concurrency", "a read-heavy inventory system", "A concurrency technique that keeps row versions so readers can use a consistent snapshot without blocking ordinary writers.", "serve a stable report snapshot while stock updates continue", "read and write contention is reduced while snapshot consistency is maintained"),
    Concept("DEADLOCK", "database deadlock", "DB_EN_TX", "Transactions and Concurrency", "a warehouse allocation workflow", "A wait cycle in which transactions each hold a resource required by another transaction in the cycle.", "detect and abort one transaction when two workers lock bins in opposite order", "the circular wait is broken and remaining work can continue"),
    Concept("BTREE", "B-tree index", "DB_EN_PERFORMANCE", "Indexing and Performance", "an account lookup service", "A balanced ordered index structure that supports equality, range, prefix, and ordered access patterns.", "index an email column used for exact lookup and alphabetical range scans", "the engine can avoid scanning every table row for ordered predicates"),
    Concept("COMPOSITE_INDEX", "composite index", "DB_EN_PERFORMANCE", "Indexing and Performance", "a large order history table", "An index whose search key is formed from two or more columns in a defined left-to-right order.", "index customer_id followed by created_at for customer-specific time ranges", "one ordered access path matches the query's combined predicates"),
    Concept("COVERING_INDEX", "covering index", "DB_EN_PERFORMANCE", "Indexing and Performance", "a high-volume status endpoint", "An index containing every column needed by a query so the engine may answer it without fetching base-table rows.", "include status and total in an index used by a frequent order lookup", "eligible queries can reduce random table-page access"),
    Concept("PARTITIONING", "table partitioning", "DB_EN_PERFORMANCE", "Indexing and Performance", "a multi-year event archive", "A physical organization that divides one logical table into separately managed pieces by a partition key.", "partition events by month when most queries and retention jobs use event_time", "partition pruning and lifecycle maintenance can touch less data"),
    Concept("WAL", "write-ahead logging", "DB_EN_OPERATIONS", "Database Operations", "a payment database recovery plan", "A durability mechanism that records change information in a log before the corresponding data pages are persisted.", "replay committed log records after an unexpected server restart", "committed changes can be recovered even when data pages were not flushed"),
    Concept("MATERIALIZED_VIEW", "materialized view", "DB_EN_OPERATIONS", "Database Operations", "a daily sales dashboard", "A stored query result that is refreshed according to policy rather than recomputed on every read.", "precompute daily revenue totals and refresh them after the reporting load", "expensive repeated aggregation is exchanged for controlled refresh cost"),
    Concept("LEAST_PRIVILEGE", "least-privilege database role", "DB_EN_OPERATIONS", "Database Operations", "a reporting application deployment", "An authorization design that grants only the operations and objects required for a role's responsibilities.", "allow the reporting service to SELECT approved views but not modify base tables", "a compromised account has a smaller capability and data-change surface"),
    Concept("REPLICATION", "database replication", "DB_EN_OPERATIONS", "Database Operations", "a geographically distributed service", "The controlled maintenance of database copies by transmitting changes from a source to one or more replicas.", "send committed changes to a read replica used for regional queries", "read capacity and recovery options improve while consistency lag remains explicit"),
]


NETWORK_CONCEPTS = [
    Concept("IP_LAYER", "OSI network layer", "NET_EN_FOUNDATIONS", "Network Foundations", "a packet-forwarding trace", "The layer responsible for logical addressing and forwarding packets across interconnected networks.", "route an IPv4 packet through multiple routers toward a remote subnet", "communication can cross Layer 2 broadcast boundaries"),
    Concept("ETHERNET_MAC", "Ethernet MAC addressing", "NET_EN_FOUNDATIONS", "Network Foundations", "a switched office LAN", "Layer 2 addressing used by Ethernet switches to deliver frames within a local broadcast domain.", "forward a frame toward the switch port learned for a destination MAC", "local frame delivery uses link-layer identities"),
    Concept("ARP", "Address Resolution Protocol", "NET_EN_FOUNDATIONS", "Network Foundations", "a workstation sending to a local server", "An IPv4 protocol that resolves a local next-hop IP address to a link-layer MAC address.", "discover the MAC address associated with the server's IPv4 address", "the sender can build an Ethernet frame for the local next hop"),
    Concept("ICMP", "Internet Control Message Protocol", "NET_EN_FOUNDATIONS", "Network Foundations", "a path diagnostic session", "A network-layer control protocol used for error reports and diagnostic messages such as echo replies.", "return an unreachable message when a router cannot forward a packet", "hosts receive structured feedback about delivery and path conditions"),
    Concept("CIDR", "CIDR prefix", "NET_EN_ADDRESSING", "IP Addressing and Routing", "an enterprise address plan", "A notation that identifies an IP network by an address and the number of leading network bits.", "allocate 10.20.8.0/22 to a site that needs contiguous address space", "network size and route aggregation are expressed without classful boundaries"),
    Concept("SUBNET_MASK", "IPv4 subnet mask", "NET_EN_ADDRESSING", "IP Addressing and Routing", "a branch-office host configuration", "A 32-bit mask that separates the network prefix from host bits in an IPv4 address.", "determine whether 192.168.10.20 and 192.168.10.90 are local under /25", "a host can distinguish local delivery from gateway forwarding"),
    Concept("DEFAULT_GATEWAY", "default gateway", "NET_EN_ADDRESSING", "IP Addressing and Routing", "a newly configured workstation", "The local router next hop used when a host has no more specific route to a destination.", "send Internet-bound traffic to the router interface on the local subnet", "off-subnet packets have a reachable first hop"),
    Concept("LONGEST_PREFIX", "longest-prefix matching", "NET_EN_ADDRESSING", "IP Addressing and Routing", "a router with overlapping routes", "The forwarding rule that selects the matching route with the greatest number of prefix bits.", "choose a /24 route instead of matching /16 and default routes", "the most specific available destination route wins"),
    Concept("TCP_HANDSHAKE", "TCP three-way handshake", "NET_EN_TRANSPORT", "Transport Protocols", "a client opening an HTTPS connection", "The SYN, SYN-ACK, ACK exchange that establishes TCP sequence state before data transfer.", "synchronize client and server sequence numbers before sending application bytes", "both endpoints confirm reachability and initialize connection state"),
    Concept("FLOW_CONTROL", "TCP flow control", "NET_EN_TRANSPORT", "Transport Protocols", "a fast sender and slow receiver", "A receiver-protection mechanism that advertises how much unacknowledged data the receiving buffer can accept.", "reduce the sender's outstanding data when the advertised receive window shrinks", "the sender avoids overrunning the receiver's buffer"),
    Concept("CONGESTION_CONTROL", "TCP congestion control", "NET_EN_TRANSPORT", "Transport Protocols", "a busy wide-area path", "A sender-side mechanism that adjusts traffic according to inferred capacity and packet-loss signals in the network.", "reduce the congestion window after loss and cautiously increase it after acknowledgements", "shared network capacity is probed without sustained overload"),
    Concept("UDP", "User Datagram Protocol", "NET_EN_TRANSPORT", "Transport Protocols", "an interactive voice application", "A connectionless transport protocol with datagram boundaries and no built-in retransmission, ordering, or congestion recovery guarantee.", "send latency-sensitive audio where late retransmissions have little value", "applications can prioritize timeliness and implement only the recovery they need"),
    Concept("DNS", "Domain Name System", "NET_EN_SERVICES", "Network Services", "a browser resolving a service name", "A distributed hierarchical service that maps domain names to records such as addresses and mail exchangers.", "resolve api.example.org to its current IP address", "applications can use stable names while service addresses change"),
    Concept("DHCP", "Dynamic Host Configuration Protocol", "NET_EN_SERVICES", "Network Services", "a campus wireless network", "A client-server protocol that leases IP configuration such as address, prefix, gateway, and DNS servers.", "automatically provide valid network settings when a laptop joins", "large client populations receive consistent configuration without manual entry"),
    Concept("TLS", "TLS for HTTPS", "NET_EN_SERVICES", "Network Services", "an online banking session", "A security protocol that authenticates peers and protects application data with integrity and encryption in transit.", "validate the service certificate and encrypt HTTP messages", "network observers cannot silently read or alter protected application traffic"),
    Concept("NAT_PAT", "NAT with port address translation", "NET_EN_SERVICES", "Network Services", "a home Internet router", "A translation method that maps many private endpoint flows to one public address by tracking transport ports.", "give several private hosts concurrent Internet access through one public IPv4 address", "scarce public addressing is shared while return flows remain distinguishable"),
    Concept("VLAN", "virtual LAN", "NET_EN_DESIGN", "Network Design and Security", "an office access-switch deployment", "A logical Layer 2 broadcast domain identified independently of the physical switch layout.", "separate guest and employee devices into different broadcast domains", "segmentation policy can follow organizational groups on shared hardware"),
    Concept("STP", "Spanning Tree Protocol", "NET_EN_DESIGN", "Network Design and Security", "a redundant switched topology", "A Layer 2 control protocol that blocks selected links to create a loop-free forwarding tree while retaining redundancy.", "prevent broadcast loops when access switches have redundant physical paths", "the LAN avoids indefinite frame circulation and can reconverge after failure"),
    Concept("QOS", "quality of service policy", "NET_EN_DESIGN", "Network Design and Security", "a congested WAN carrying voice and backups", "A classification, queueing, and scheduling policy that gives defined treatment to traffic classes under contention.", "prioritize delay-sensitive voice packets while shaping bulk backup traffic", "critical applications receive predictable service when bandwidth is scarce"),
    Concept("VPN", "virtual private network", "NET_EN_DESIGN", "Network Design and Security", "a remote administrator connection", "An authenticated encrypted tunnel that carries private traffic across an untrusted network.", "require administrators to enter the private network through a managed VPN gateway", "remote traffic gains confidentiality, integrity, and controlled network entry"),
]


FORM_CONFIG = [
    ("remember", "easy", 0),
    ("understand", "easy", 1),
    ("apply", "medium", 2),
    ("analyze", "medium", 3),
    ("evaluate", "hard", 4),
]


def build_bank() -> list[dict[str, Any]]:
    questions = []
    for subject_code, prefix, concepts in (
        ("DATABASE", "DBEN", DATABASE_CONCEPTS),
        ("NETWORK", "NETEN", NETWORK_CONCEPTS),
    ):
        for concept_index, concept in enumerate(concepts):
            for form_index, (bloom, difficulty, _) in enumerate(FORM_CONFIG):
                peers = [
                    concepts[(concept_index + offset) % len(concepts)]
                    for offset in range(1, 10)
                ]
                stem, correct, distractors, explanation = _form(
                    concept, peers, form_index
                )
                option_count = {"remember": 4, "understand": 5, "apply": 6, "analyze": 8, "evaluate": 10}[bloom]
                raw_options = [(correct, True, None)] + [
                    (text, False, diagnosis)
                    for text, diagnosis in distractors[: option_count - 1]
                ]
                rotation = (concept_index * 5 + form_index) % option_count
                options = raw_options[rotation:] + raw_options[:rotation]
                number = concept_index * 5 + form_index + 1
                questions.append(
                    {
                        "question_code": f"{prefix}-{number:03d}",
                        "subject_code": subject_code,
                        "topic_code": concept.topic_code,
                        "topic_name": concept.topic_name,
                        "skill_code": f"{prefix}_SK_{concept.code}",
                        "skill_name": f"Apply {concept.name}",
                        "stem": stem,
                        "options": options,
                        "explanation": explanation,
                        "bloom_level": bloom,
                        "difficulty_label": difficulty,
                    }
                )
    return questions


def _form(
    concept: Concept, peers: list[Concept], form_index: int
) -> tuple[str, str, list[tuple[str, str]], str]:
    if form_index == 0:
        stem = f"During {concept.context}, which statement accurately defines {concept.name}?"
        correct = concept.definition
        field = "definition"
        explanation = f"{concept.name.title()} is correctly defined as follows: {concept.definition}"
    elif form_index == 1:
        stem = f"An engineer working on {concept.context} gives this description: {concept.definition} Which term matches it?"
        correct = concept.name.title()
        field = "name"
        explanation = f"The description identifies {concept.name}, not a neighboring mechanism."
    elif form_index == 2:
        stem = f"For {concept.context}, the team must {concept.practical}. Which concept should guide the implementation first?"
        correct = concept.name.title()
        field = "name"
        explanation = f"The requirement is a direct application of {concept.name}: it is used to {concept.practical}."
    elif form_index == 3:
        stem = f"A design for {concept.context} applies {concept.name}. Which outcome best explains why that decision fits the stated mechanism?"
        correct = concept.benefit
        field = "benefit"
        explanation = f"Applying {concept.name} fits because {concept.benefit}."
    else:
        stem = f"A review of {concept.context} wants this outcome: {concept.benefit}. Which proposed action is the strongest use of {concept.name}?"
        correct = concept.practical
        field = "practical"
        explanation = f"The strongest action is to {concept.practical}; that is the intended operational use of {concept.name}."
    distractors = []
    for peer in peers:
        value = getattr(peer, field)
        distractors.append(
            (
                value.title() if field == "name" else value,
                f"This choice describes {peer.name}, not {concept.name}.",
            )
        )
    return stem, correct, distractors, explanation


async def seed(*, activate: bool, retire_legacy: bool) -> dict[str, Any]:
    bank = build_bank()
    _validate_source_bank(bank)
    inserted = 0
    existing = 0
    async with async_session_factory() as session:
        for code, name, description in (
            (
                "DATABASE",
                "Database Systems",
                "Relational modeling, SQL, transactions, indexing, and database operations.",
            ),
            (
                "NETWORK",
                "Computer Networks",
                "Network models, addressing, routing, transport, services, security, and troubleshooting.",
            ),
        ):
            await session.execute(
                text(
                    """
                    INSERT INTO subjects (
                        subject_code, subject_name, description, is_active
                    ) VALUES (:code, :name, :description, TRUE)
                    ON CONFLICT (subject_code) DO UPDATE
                    SET subject_name = EXCLUDED.subject_name,
                        description = EXCLUDED.description,
                        is_active = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {"code": code, "name": name, "description": description},
            )
        subject_ids = {
            row.subject_code: row.subject_id
            for row in await session.execute(
                text("SELECT subject_id, subject_code FROM subjects")
            )
        }
        for question in bank:
            subject_id = int(subject_ids[question["subject_code"]])
            topic_id = await _ensure_unit(
                session,
                subject_id,
                question["topic_code"],
                question["topic_name"],
                "topic",
            )
            skill_id = await _ensure_unit(
                session,
                subject_id,
                question["skill_code"],
                question["skill_name"],
                "skill",
                parent_unit_id=topic_id,
            )
            present = await session.scalar(
                text("SELECT question_id FROM questions WHERE question_code = :code"),
                {"code": question["question_code"]},
            )
            if present:
                existing += 1
                continue
            irt = initial_irt(
                question["bloom_level"],
                question["difficulty_label"],
                len(question["options"]),
            )
            result = await session.execute(
                text(
                    """
                    INSERT INTO questions (
                        question_code, subject_id, stem, bloom_level,
                        difficulty_label, difficulty_norm, avg_time_sec,
                        explanation, display_option_count, must_include_best,
                        randomize_options, irt_a, irt_b, irt_c, irt_status,
                        status, source, created_by, provenance
                    ) VALUES (
                        :code, :subject_id, :stem, :bloom, :difficulty,
                        :difficulty_norm, :avg_time, :explanation, 4, TRUE, TRUE,
                        :irt_a, :irt_b, :irt_c, 'estimated', 'draft',
                        'curated_english_bank_v1', 'knowledge_engineer',
                        CAST(:provenance AS JSONB)
                    ) RETURNING question_id
                    """
                ),
                {
                    "code": question["question_code"],
                    "subject_id": subject_id,
                    "stem": question["stem"],
                    "bloom": question["bloom_level"],
                    "difficulty": question["difficulty_label"],
                    "difficulty_norm": irt.difficulty_norm,
                    "avg_time": irt.avg_time_sec,
                    "explanation": question["explanation"],
                    "irt_a": irt.a,
                    "irt_b": irt.b,
                    "irt_c": irt.c,
                    "provenance": json.dumps(
                        {
                            "language": "en",
                            "authoring_method": "deterministic_domain_item_family_v1",
                            "irt_rubric": irt.rubric_version,
                            "content_review_required": True,
                            "source_catalog": "CS2307 English operational bank",
                        },
                        separators=(",", ":"),
                    ),
                },
            )
            question_id = int(result.scalar_one())
            for option_index, (option_text, is_best, diagnosis) in enumerate(
                question["options"]
            ):
                option_code = f"O{option_index + 1:02d}"
                await session.execute(
                    text(
                        """
                        INSERT INTO answer_options (
                            question_id, option_code, option_text, score_weight,
                            is_best_answer, distractor_type, diagnosis,
                            explanation, source, provenance
                        ) VALUES (
                            :question_id, :option_code, :option_text, :score_weight,
                            :is_best, :distractor_type, :diagnosis, :explanation,
                            'curated_english_bank_v1', CAST(:provenance AS JSONB)
                        )
                        """
                    ),
                    {
                        "question_id": question_id,
                        "option_code": option_code,
                        "option_text": option_text,
                        "score_weight": 1 if is_best else 0,
                        "is_best": is_best,
                        "distractor_type": "best" if is_best else "misconception",
                        "diagnosis": diagnosis,
                        "explanation": question["explanation"] if is_best else diagnosis,
                        "provenance": json.dumps(
                            {"question_code": question["question_code"], "language": "en"},
                            separators=(",", ":"),
                        ),
                    },
                )
            await session.execute(
                text(
                    """
                    INSERT INTO question_knowledge_units (
                        question_id, unit_id, unit_role, measurement_weight
                    ) VALUES
                        (:question_id, :topic_id, 'topic', 1),
                        (:question_id, :skill_id, 'primary_skill', 1)
                    """
                ),
                {
                    "question_id": question_id,
                    "topic_id": topic_id,
                    "skill_id": skill_id,
                },
            )
            inserted += 1
        await session.commit()

    result: dict[str, Any] = {
        "bank_size": len(bank),
        "inserted": inserted,
        "already_present": existing,
        "activated": 0,
        "rejected": {},
        "retired_legacy": 0,
    }
    if activate:
        codes = [question["question_code"] for question in bank]
        activation = await AdminService(
            AdminRepository(), async_session_factory
        ).bulk_activate_questions(codes, "seed_english_question_bank")
        result["activated"] = len(activation.activated)
        result["rejected"] = {
            code: [issue.model_dump() for issue in issues]
            for code, issues in activation.rejected.items()
        }
    if retire_legacy and result["activated"] == len(bank):
        async with async_session_factory() as session:
            retired = await session.execute(
                text(
                    """
                    UPDATE questions
                    SET status = 'retired', irt_status = 'retired',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE question_code NOT LIKE 'DBEN-%'
                      AND question_code NOT LIKE 'NETEN-%'
                      AND status <> 'retired'
                    """
                )
            )
            result["retired_legacy"] = retired.rowcount
            await session.commit()
    return result


async def _ensure_unit(
    session,
    subject_id: int,
    code: str,
    name: str,
    unit_type: str,
    parent_unit_id: int | None = None,
) -> int:
    result = await session.execute(
        text(
            """
            INSERT INTO knowledge_units (
                subject_id, parent_unit_id, unit_code, unit_name,
                unit_type, description, is_active
            ) VALUES (
                :subject_id, :parent_unit_id, :code, :name, :unit_type,
                :description, TRUE
            )
            ON CONFLICT (subject_id, unit_code) DO UPDATE
            SET unit_name = EXCLUDED.unit_name,
                unit_type = EXCLUDED.unit_type,
                parent_unit_id = EXCLUDED.parent_unit_id,
                description = EXCLUDED.description,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            RETURNING unit_id
            """
        ),
        {
            "subject_id": subject_id,
            "parent_unit_id": parent_unit_id,
            "code": code,
            "name": name,
            "unit_type": unit_type,
            "description": f"English operational-bank {unit_type}: {name}.",
        },
    )
    return int(result.scalar_one())


def _validate_source_bank(bank: list[dict[str, Any]]) -> None:
    if len(bank) != 200:
        raise ValueError(f"Expected 200 questions, found {len(bank)}")
    codes = [question["question_code"] for question in bank]
    if len(codes) != len(set(codes)):
        raise ValueError("Question codes must be unique")
    if {question["subject_code"] for question in bank} != {"DATABASE", "NETWORK"}:
        raise ValueError("The bank must contain Database Systems and Computer Networks")
    for question in bank:
        if len(question["stem"].split()) < 8 or len(question["explanation"].split()) < 8:
            raise ValueError(f"Incomplete content in {question['question_code']}")
        option_texts = [value[0].casefold() for value in question["options"]]
        if len(option_texts) != len(set(option_texts)):
            raise ValueError(f"Duplicate options in {question['question_code']}")
        if sum(value[1] for value in question["options"]) != 1:
            raise ValueError(f"Expected one best answer in {question['question_code']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--retire-legacy", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(
        seed(activate=args.activate, retire_legacy=args.retire_legacy)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
