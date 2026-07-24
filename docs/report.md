# Báo cáo hệ thống đánh giá năng lực thích ứng

## 1. Phạm vi và điều chỉnh yêu cầu

Hệ thống dùng FastAPI, PostgreSQL và Streamlit để sinh đề cố định, tổ chức CAT, chấm điểm IRT 3PL, cập nhật năng lực theo môn và đơn vị tri thức, suy diễn lộ trình học, quản trị ngân hàng câu hỏi và trực quan hóa Knowledge Graph.

Ngân hàng đang vận hành vẫn lấy số lượng thật từ PostgreSQL và không tự sao chép, diễn đạt lại hoặc chèn câu giả để đạt chỉ tiêu 200 câu. Dashboard readiness công khai phần thiếu so với yêu cầu học phần. Staff có thể yêu cầu LLM tạo đúng một bản nháp mỗi lần; thao tác này không chạy tự động, không kích hoạt câu và không làm thay đổi báo cáo 200 câu nếu chưa qua validation, review và activation của admin.

## 2. Quy trình thiết kế hệ CSTT

Slide quy trình mô tả hệ CSTT nhận bài toán theo ngôn ngữ quy ước, dịch sang biểu diễn nội bộ và dùng bộ suy diễn để tạo lời giải bằng suy diễn tiến, lùi hoặc bài toán mẫu [*2a. Các quy trình trong Thiết kế hệ CSTT*, tr. 4]. Bốn giai đoạn được nêu trực tiếp ở trang 6 và được triển khai như sau:

1. **Thu thập tri thức:** xác định miền đánh giá năng lực; thu thập câu hỏi, môn, chủ đề, kỹ năng, Bloom, IRT và phản hồi. Slide yêu cầu xác định miền, nguồn và phân lớp bài toán [*2a...*, tr. 8; *3. Các quy trình trong Thiết kế hệ CSTT*, tr. 5].
2. **Thiết kế CSTT:** lưu `C`, `R`, `Rules`, facts, câu hỏi và provenance trong PostgreSQL. Đây là bước mô hình hóa, tổ chức và thiết kế tác vụ CSTT [*2a...*, tr. 9; *3...*, tr. 6].
3. **Thiết kế bộ suy diễn:** phân loại các bài toán sinh đề, cập nhật năng lực, CAT và lộ trình; cài đặt hợp nhất, bao đóng, suy diễn tiến, định hướng mục tiêu và trace [*2a...*, tr. 10; *3...*, tr. 7].
4. **Thiết kế giao diện:** tách giao diện thí sinh, giám sát và kỹ sư tri thức/quản trị; trình bày kết quả phù hợp từng vai trò [*2a...*, tr. 11; *3...*, tr. 8].

## 3. Rela-model `K = (C, R, Rules)`

Tài liệu Rela-model xác định ba thành phần chính `(C, R, Rules)` và tổ chức khái niệm theo `C(0)` đến `C(3)` [*6b. Cấu trúc tri thức quan hệ*, tr. 2]. Hệ thống ánh xạ:

- `C(0)`: số, chuỗi, Boolean, xác suất, theta, thời gian.
- `C(1)`: `Subject`, `KnowledgeUnit`, `BloomLevel`, `Student`.
- `C(2)`: `Question`, `IRTItem`, `AbilityState`, `ResponseEvent`.
- `C(3)`: `ExamSession`, hồ sơ học thích ứng và Knowledge Graph sinh viên.

`R` gồm `belongs_to`, `measures`, `prerequisite_of`, `selected_option`, `has_ability`, `recommended_next` và các quan hệ nghiệp vụ khác. Metadata quan hệ điều khiển tính đối xứng và bắc cầu. `Rules` nằm trong `kb_rules`, có mã, giả thiết, kết luận, độ ưu tiên, trọng số, nguồn và mẫu giải thích; engine không chứa danh sách luật nghiệp vụ cố định.

Năm loại sự kiện được chuẩn hóa thành `type`, `determined_object`, `constant_assignment`, `equality` và `binary_relation`. Quy tắc hợp nhất theo loại, kể cả tính đối xứng của equality/quan hệ, dựa trên mô tả ở [*6b...*, tr. 4]. `fact_args` lưu danh sách đối số chuẩn hóa; các cột subject/object cũ vẫn được giữ để tương thích.

## 4. Bao đóng và chiến lược suy diễn

Engine bắt đầu từ `KnownFacts`, hợp nhất sự kiện, áp dụng luật theo priority/weight đến điểm cố định, ngăn trùng lặp và giới hạn chu kỳ. Mỗi fact suy ra mang `rule_code`, facts bằng chứng, nguồn và trace. Cách lặp đến khi không còn sự kiện mới tương ứng thuật giải `Obj.Closure(F)` [*6b...*, tr. 5–7].

Suy diễn tiến của hệ luật bắt đầu từ `Known = GT`, chọn luật có giả thiết nằm trong Known và thêm kết luận đến khi đạt mục tiêu hoặc hết luật [*4a. Các chiến lược suy diễn*, tr. 3]. Chế độ backward thực hiện phân tích phụ thuộc từ predicate mục tiêu để giới hạn tập luật rồi chứng minh bằng các facts; hybrid chạy bao đóng và duyệt ngược trace để giữ các bước cần cho mục tiêu, phù hợp ý tưởng kết hợp tiến/lùi [*4a...*, tr. 5].

Bài toán tổng quát được mô hình hóa `(O, F) → G`; tài liệu định nghĩa tính giải được bằng một dãy luật và so sánh lời giải theo số bước [*6b...*, tr. 8]. Các heuristic giới hạn tập luật, sắp xếp luật và ưu tiên xác định đối tượng/thuộc tính được nêu ở [*6b...*, tr. 9]. Trong hệ thống, priority/weight quyết định thứ tự luật; CAT dùng một hàm điểm minh bạch để chọn câu.

Khái niệm `Closure(A)` trên mạng suy diễn và điều kiện bài toán giải được khi mục tiêu thuộc bao đóng được trình bày ở [*4b. Các chiến lược suy diễn (tt.)*, tr. 3]. Mạng tính toán `(M,F)` và luật `u(f) → v(f)` nằm ở [*5a. Mạng tính toán*, tr. 4]; mạng có trọng số `(A,D,w)` và chi phí luật nằm ở trang 5. IRT/CAT được xem là module tính toán có trọng số, phát facts và provenance trở lại CSTT.

## 5. IRT, CAT và học cá nhân hóa

Xác suất đúng dùng IRT 3PL:

```text
P_i(theta) = c_i + (1-c_i) / (1 + exp(-1.7*a_i*(theta-b_i)))
```

EAP cập nhật theta và sai số chuẩn từ toàn bộ lịch sử phản hồi. Trọng số liên kết câu hỏi–đơn vị tri thức điều chỉnh mức ảnh hưởng khi cập nhật năng lực chủ đề/kỹ năng. Response events không bị ghi đè; `student_abilities` chỉ là trạng thái hiện tại được tái tính từ ledger.

CAT một môn lọc câu `active`, pool hợp lệ và chưa hỏi. Điểm chọn gồm Fisher information, mức yếu của đơn vị tri thức, thiếu hụt phân bố nội dung và phạt phơi nhiễm. Mọi trọng số nằm trong `sys_props`; tie-break theo mã câu để tái hiện được. CAT dừng sau số câu tối thiểu khi đạt ngưỡng sai số, theta ổn định trong cửa sổ cấu hình, đạt tối đa hoặc hết pool. Đồng hồ chỉ là thời gian ước lượng, không tự nộp hay khóa bài.

Facts `unit_accuracy(student, unit, value)` được đưa vào engine. Các luật trong `kb_rules` suy ra `weak_unit`, `has_mastery` và `recommended_next`; hai ngưỡng được quản lý tập trung trong `sys_props` và đồng bộ vào luật. Thí sinh chỉ xem điểm, mức hiểu, tiến độ và lộ trình; supervisor/admin xem theta, SE, Fisher, selection reason và trace.

## 6. Knowledge Graph và giải thích

Tài liệu e-learning yêu cầu CSTT tổ chức miền học, truy xuất đúng nghĩa và đề xuất tri thức liên quan [*6d. Ứng dụng - Hệ thống tra cứu kiến thức*, tr. 11, 15]. Mô hình ontology tích hợp gồm concepts, relations, operators, rules, problems và methods [*6d...*, tr. 21]. Ví dụ Legal-Onto cũng kết hợp Rela-model và Knowledge Graph, với concepts, relations và rules [*6a. Ứng dụng - Hệ truy vấn kiến thức luật*, tr. 3, 8].

Graph của dự án được dựng trực tiếp từ PostgreSQL, không cần graph database. Node gồm sinh viên, môn, topic/skill, câu đã trả lời và evidence; edge gồm `belongs_to_subject`, `measures`, `produced_evidence`, `supports_ability`, `has_ability`, `prerequisite_of`, `recommended_next`. Recommendation được đọc từ facts do luật suy ra, không tính lại bằng ngưỡng cứng trong graph service. Graph staff có thông số kỹ thuật và provenance; graph thí sinh dùng nhãn hiểu bài đã làm mờ thông số nội bộ.

Backend tạo explanation context xác định từ điểm, thay đổi năng lực, evidence theo đơn vị tri thức và trace. LLM chỉ chuyển context này thành văn bản tự nhiên, không được sửa điểm, theta, luật áp dụng hoặc trạng thái activation. Context thí sinh loại bỏ theta, Bloom, Fisher, SE và mã trace trước khi gọi provider; context staff giữ số liệu kỹ thuật. Mỗi kết quả được lưu trong `llm_artifacts` và được cache theo phiên/vai trò để tránh gọi lặp tốn token.

## 7. Validation và đánh giá hội tụ

Question governance kiểm tra pool phương án, đúng một best answer, phương án trùng, topic và primary skill, Bloom/difficulty, `difficulty_norm`, IRT range, explanation, source, provenance và stem trùng/gần trùng. Import và LLM đều chỉ đưa câu vào `draft`; chỉ admin có thể review và kích hoạt khi không còn blocking issue.

`POST /generation/questions` nhận môn, topic, skill, Bloom, độ khó, mục tiêu và đoạn nguồn; mỗi lần chỉ tạo một câu. Provider trả stem, phương án, đáp án, giải thích và Bloom rationale. IRT ban đầu không do LLM quyết định mà được rubric `deterministic-initial-irt-v1` ánh xạ từ Bloom, độ khó và kích thước pool. Prompt/input, model, thời gian, người gọi, usage, output và lỗi được audit; khóa API chỉ đọc từ biến môi trường. `sys_props` quản lý kill switch, model, giới hạn token, temperature và giới hạn đoạn nguồn.

Simulator dùng chính selector và stopping rule của production, tạo phản hồi từ xác suất IRT theo true theta trong `[-3,3]`. Báo cáo gồm RMSE, MAE, bias, tỷ lệ hội tụ, số câu trung bình, SE theo bước, item fit, khả năng phân biệt, phân bố `b`, Bloom/difficulty và thời gian theo độ khó. Mọi hạn chế do ngân hàng hiện tại nhỏ hơn yêu cầu đều được ghi rõ.

## 8. Ma trận yêu cầu

| Yêu cầu | Trạng thái | Bằng chứng |
| --- | --- | --- |
| FastAPI/PostgreSQL/Streamlit, role navigation | Implemented and verified | API routers, role dependencies, modular pages, automated tests |
| Rela-model `K=(C,R,Rules)`, `C(0)-C(3)` | Implemented and verified | `kb_definitions`, `kb_rules`, canonical facts |
| Năm loại sự kiện, hợp nhất, bao đóng | Implemented and verified | Inference unit tests |
| Suy diễn tiến, lùi/hybrid, trace thu gọn | Implemented and verified | `/kb/closure`, trace endpoints and tests |
| Sinh đề cố định theo constraints | Implemented and verified | Subject/count/difficulty/topic/skill/Bloom/time validation |
| IRT theo môn và topic/skill | Implemented and verified | Weighted EAP and response-history refresh |
| CAT realtime | Implemented but limited by current question bank | Active-only selector; pool exhaustion is an explicit stop reason |
| Knowledge Graph | Implemented and verified | Staff and privacy-safe taker endpoints/UI |
| Question review/activation/readiness | Implemented and verified | Deterministic governance endpoints and admin UI |
| Báo cáo hiệu chỉnh/hội tụ | Implemented but limited by current question bank | `python -m scripts.evaluate_cat` |
| 200 active questions từ hai môn | Pending additional externally authored question content | Readiness dashboard reports exact gap; no automatic generation |
| LLM question generation và prose XAI | Implemented and verified | OpenAI-compatible client, one-draft endpoint/UI, deterministic validator/IRT, role-safe cached explanations, audit artifacts |

## 9. Chạy và kiểm chứng

Chạy toàn hệ thống bằng một lệnh:

```bash
docker compose -f docker/docker-compose.yaml up --build
```

Hoặc dùng Conda `CS2307` theo README. Chạy test bằng `conda run -n CS2307 pytest -q`; chạy đánh giá bằng `conda run -n CS2307 python -m scripts.evaluate_cat` sau khi admin đã review và kích hoạt các câu hiện có.
