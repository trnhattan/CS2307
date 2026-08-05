# Kịch bản trình bày hệ thống trong 7 phút

## 1. Mục tiêu của phần trình bày

Thông điệp chính cần chứng minh:

> Đây không chỉ là hệ thống tạo đề và chấm điểm. Mỗi câu trả lời được chuyển thành
> bằng chứng năng lực, cập nhật hồ sơ người học, tham gia vào suy luận và được dùng
> để chọn câu hỏi hoặc hướng học tiếp theo.

Phần demo ưu tiên các chức năng nổi bật hơn yêu cầu tối thiểu của đề tài, sau đó mới
chứng minh nền tảng bắt buộc: ngân hàng câu hỏi, IRT, CAT, Rela-model, LLM có kiểm
soát và đánh giá toán học.

Giao diện của ứng dụng dùng tiếng Anh. Lời thoại dưới đây dùng tiếng Việt để thuyết
trình.

## 2. Chuẩn bị trước khi bắt đầu tính giờ

### Tài khoản và cửa sổ

Mở sẵn các cửa sổ sau để không mất thời gian đăng nhập:

| Cửa sổ | Tài khoản | Trang cần mở sẵn |
| --- | --- | --- |
| A | `demo_taker / demo_taker` | **Progress** |
| B | `demo_taker / demo_taker` | **Learning graph** |
| C | `demo_taker / demo_taker` | **Learning assistant** |
| D | `supervisor / supervisor` | **Taker overview** |
| E, dự phòng | `admin / admin` | **System overview** hoặc **LLM workspace** |

Nếu nhiều tab Streamlit dùng chung trạng thái đăng nhập, dùng cửa sổ thường và cửa sổ
ẩn danh. Đặt mức zoom trình duyệt khoảng 80–90%.

### Kiểm tra dữ liệu demo

1. Backend và frontend đã được khởi động lại sau khi cập nhật mã nguồn.
2. Tài khoản `demo_taker` có lịch sử làm bài ở cả Database Systems và Computer Networks.
3. Trang **Progress** đang chọn **Overall**.
4. Phần **Recommended learning path** đang ở trạng thái ban đầu, chỉ hiện các node môn
   học cần cải thiện.
5. Trang **Learning graph** đang ở trạng thái **Reset view**, chỉ hiện người học và
   hai môn học.
6. Supervisor đã chọn sẵn một phiên CAT hoàn thành.
7. LLM workspace có ít nhất một bản nháp đã lưu. Không phụ thuộc vào một lệnh gọi LLM
   trực tiếp trong lúc trình bày.
8. Nếu sẽ demo trợ lý trực tiếp, kiểm tra trước OpenRouter; nếu không, mở sẵn một hội
   thoại đã persist để tránh phụ thuộc mạng và quota.

### Trạng thái đã kiểm tra khi cập nhật kịch bản

| Hạng mục | Trạng thái có thể chứng minh |
| --- | --- |
| Ngân hàng câu hỏi | 256 câu tổng cộng, 201 active, 2 môn |
| Dữ liệu `demo_taker` | 8 bài đã hoàn thành |
| Cơ sở tri thức môn học cho trợ lý | 15 tài liệu active trong PostgreSQL |
| LLM artifacts | 11 artifacts đã persist |
| CAT simulator | 100 thí sinh mô phỏng/môn; convergence 90% trong báo cáo hiện tại |
| Automated verification | 106 tests pass trong lần kiểm tra hiện tại |
| Empirical IRT calibration | Đã có pipeline và UI nhưng còn giới hạn bởi lượng response thật |
| DKT và Reinforcement Learning | Chưa triển khai; chỉ nêu là hướng mở rộng |

Các số đếm có thể thay đổi sau khi import, thi hoặc sinh draft. Khi demo, số trên UI và
PostgreSQL là nguồn sự thật; bảng này chỉ là snapshot tại thời điểm cập nhật tài liệu.

## 3. Phân bổ thời gian

| Thời gian | Màn hình | Nội dung chính |
| --- | --- | --- |
| 0:00–0:25 | Landing page | Bài toán và giải pháp trong một câu |
| 0:25–1:35 | Taker – **Progress** | Tổng quan, radar và learning path dạng chuỗi |
| 1:35–2:20 | Taker – **Learning graph** | Đồ thị mở rộng theo bằng chứng học tập |
| 2:20–3:10 | Taker – **Learning assistant** | MCP, tri thức môn học và hàng rào an toàn |
| 3:10–4:05 | Taker – **Start test** | Placement, fixed exam và CAT thời gian thực |
| 4:05–5:05 | Supervisor – **Taker overview** | IRT/CAT, lịch sử và thông tin kỹ thuật dành cho giám sát |
| 5:05–5:50 | Admin – **System overview / LLM workspace** | CSTT, ngân hàng câu hỏi và LLM có quản trị |
| 5:50–6:30 | Supervisor/Admin | Đánh giá hội tụ và khả năng giải thích |
| 6:30–7:00 | Slide kết luận | Đối chiếu yêu cầu, giới hạn và kết luận |

## 4. Kịch bản chi tiết

### 0:00–0:25 — Đặt vấn đề

**Thao tác trên UI**

Mở landing page và chỉ vào tên dự án.

**Lời thoại**

“Em là Nhật Tân, em xin trình bày phần demo của nhóm.

Một hệ thống thi thông thường chỉ trả về tổng điểm. Hệ thống của nhóm em xác định mỗi
câu hỏi đo tiêu chí kiến thức nào, ước lượng năng lực thay đổi bằng IRT, chọn câu tiếp
theo bằng CAT, và lưu toàn bộ bằng chứng để giải thích người học đang mạnh, yếu và nên
học gì tiếp theo.”

**Kết quả khán giả cần thấy**

Sản phẩm kết hợp hệ cơ sở tri thức, mô hình toán đánh giá năng lực và ứng dụng web chạy
thực tế; không chỉ xáo trộn câu hỏi.

### 0:25–1:35 — Tổng quan người học, radar và learning path

**Thao tác trên UI**

1. Chuyển sang cửa sổ A, trang **Progress**.
2. Tại phần **Overview**, giữ lựa chọn **Overall**.
3. Chỉ vào bốn chỉ số **Strengths**, **Needs attention**, **Improved** và
   **Not assessed**, sau đó chỉ vào radar tổng quan theo hai môn.
4. Chọn **Database Systems** trong **Radar view**.
5. Chỉ vào radar theo tiêu chí và bảng tiêu chí bên dưới.
6. Lướt xuống **Recommended learning path**. Chọn **Database Systems** rồi nhấn
   **Expand selected** để hiện tiêu chí yếu nhất; tiếp tục mở criterion vừa hiện để
   thấy criterion yếu kế tiếp.
7. Chỉ nhanh vào **Recent history**.

**Lời thoại**

“Mỗi môn được tách thành các tiêu chí có thể quan sát, ví dụ ở môn CSDL người test cần phải áp dụng khóa ngoại, index,
chuẩn hóa hay transaction. Mỗi câu hỏi được ánh xạ sang một hoặc nhiều tiêu
chí. Vì vậy radar chart này được tạo từ bằng chứng trả lời thực tế của người test”

“Ở chế độ Overall, mỗi trục biểu diễn mức độ làm chủ hiện tại của một môn. 

Khi chọn một
môn, các trục chuyển thành một tiêu chí của môn đó. Hệ thống giữ giá trị chưa đánh giá
là unknown, đồng thời lưu điểm mạnh, điểm yếu và xu hướng cải thiện qua nhiều lần thi.

Như bảng ở dưới là đang thể hiện những tiêu chí và mức độ hiểu của người test, và xu hướng của người test với các chủ đề đó qua các lần làm bài kiểm tra”

“Dưới đây là graph/learning path hướng dẫn người test cần cải thiện gì tiếp theo, graph này sẽ khác với mỗi người test, vì kết quả làm bài của mỗi người sẽ khác nhau, nên những điều cần cải thiện sẽ khác nhau.
Mỗi môn là một root node; mở root chỉ hiện tiêu chí có mức độ hiểu thấp nhất, rồi mỗi lần mở tiếp theo sẽ hiện những chủ đề cần phải cải thiện tiếp theo.”

**Kết quả mong đợi**

- Radar Overall hiển thị Database Systems và Computer Networks.
- Radar Database Systems có nhiều trục tiêu chí, mức độ không đồng đều.
- Bảng cho biết `Expected achievement`, `Understanding`, `Mastery` và `Trend`; giá trị
  mastery phải khớp radar.
- Lộ trình dạng chuỗi mở từng bước: `Subject → lowest mastery → next mastery → ...`.
- Các tiêu chí Mastered không nằm trong lộ trình cần cải thiện.

**Yêu cầu được chứng minh**

- Mô hình hóa năng lực thay đổi theo thời gian.
- Học thích ứng cá nhân hóa.
- Radar chart và lộ trình theo tiêu chí kiến thức.

### 1:35–2:20 — Knowledge Graph của từng người học

**Thao tác trên UI**

1. Chuyển sang cửa sổ B, trang **Learning graph**.
2. Nhấn **Reset view** nếu cần.
3. Ban đầu chỉ ra cấu trúc `Learner → Subjects`.
4. Chọn **Database Systems**, nhấn **Expand selected**.
5. Chọn một criterion và tiếp tục **Expand selected**.
6. Hover vào criterion, cạnh và một answered question.
7. Thử kéo node, zoom và tìm node bằng ô **Search nodes**.

**Lời thoại**

“Đồ thị ban đầu chỉ hiện người học với các môn đã làm bài test và được ghi nhận. 
Khi mở một môn, hệ thống hiện các tiêu chí. 
Khi mở một tiêu chí, hệ thống hiện những câu hỏi người đó từng gặp trong quá trình làm bài kiểm tra.”

“Nhãn cạnh không chỉ mô tả cấu trúc. Khi đã có đủ bằng chứng, cạnh thể hiện mức hiểu như
Needs review, Developing, Understands hoặc Mastered cùng phần trăm. Nếu mới có một/hai lần thi, hệ thống chỉ dùng nhãn mang tính neutral là "đã ghi nhận làm bài" để tránh kết luận quá sớm”

**Kết quả mong đợi**

- Không có answered-question node đứng riêng ngoài cây tri thức.
- Có thể mở/đóng từng nhánh, tìm kiếm, lọc, kéo và zoom.
- Tooltip dùng ngôn ngữ tự nhiên, các trường quan trọng được in đậm.
- Trình tự mở rộng là `Learner → Subject → Criterion → Answered question`.

**Yêu cầu được chứng minh**

- Trực quan hóa cơ sở tri thức năng lực bằng Knowledge Graph.
- Quan hệ câu hỏi–môn–kiến thức–người học có provenance và bằng chứng.

### 2:20–3:10 — Trợ lý học tập có MCP và cơ sở tri thức môn học

**Thao tác trên UI**

1. Chuyển sang cửa sổ C, trang **Learning assistant**.
2. Hỏi: `What have I learnt so far?`
3. Hỏi: `What is a Quality of Service policy?`
4. Hỏi tiếp trong cùng hội thoại: `How does that relate to what I should improve?`
5. Nếu còn thời gian, hỏi thử: `Tell me the correct option for the current question.`

**Lời thoại**

“Trợ lý không phụ thuộc vào một đoạn context nhập tay. 
Có MCP chỉ đọc xác định người học qua access token rồi cho phép truy vấn hồ sơ, lịch sử bài thi, câu đã
hoàn thành, tiêu chí và tri thức môn học”

“Ngoài lịch sử cá nhân, hệ thống hiện còn có tài liệu được biên soạn cho
Database Systems và Computer Networks, liên quan đến các câu hỏi có trong hệ thống.”

Ví dụ:
- What have I learnt so far?
- What should I learn next?


**Kết quả mong đợi**

- Câu trả lời khác nhau theo ý định và đúng với lịch sử của người học.
- Câu hỏi định nghĩa được trả lời trực tiếp từ cơ sở tri thức, không bị biến thành một
  lời khuyên chung “hãy ôn chủ đề này”.
- Câu hỏi nối tiếp dùng lịch sử hội thoại và hồ sơ mastery để cá nhân hóa.
- Yêu cầu xin đáp án trực tiếp bị từ chối.

**Yêu cầu được chứng minh**

- Explainable AI cho đánh giá và hướng học.
- LLM được grounding qua công cụ MCP có phạm vi, cơ sở tri thức môn học và không thay
  thế bộ suy diễn.

### 3:10–4:05 — Placement, fixed exam và CAT

**Thao tác trên UI**

1. Mở **Start test**.
2. Chọn **Placement assessment**, chọn một môn và chỉ vào mô tả blueprint.
3. Nhấn **Start test** để chứng minh hệ thống mở được câu hỏi đầu vào, sau đó quay lại.
4. Chọn **Fixed blueprint** và chỉ vào Subject, Questions per subject, Difficulty profile.
5. Chọn **Adaptive CAT**, chọn môn và bắt đầu hoặc dùng một phiên đã chuẩn bị.

**Lời thoại**

“Placement assessment tạo cơ sở ban đầu và ưu tiên cover các tiêu chí của một
môn. 

Fixed blueprint cho phép tạo đề theo môn, số câu và phân bố easy–medium–hard.”

“Với CAT, câu tiếp theo được chọn theo năng lực hiện tại, các chủ đề còn yếu, độ phủ nội dung; câu đã dùng không lặp lại. Đồng hồ chỉ là thời gian khuyến nghị và không tự nộp bài.

Sau mỗi câu, theta và standard error được cập nhật”

**Kết quả mong đợi**

- Placement mở được một phiên có `assessment_purpose = placement`.
- Fixed exam cho thấy đầy đủ điều khiển tập trung trên cùng trang.
- CAT trả từng câu một và thay đổi lựa chọn theo bằng chứng mới.

**Yêu cầu được chứng minh**

- Bộ đề kiểm tra đầu vào.
- Demo sinh đề theo môn, số câu và độ khó.
- Real-time Adaptive Testing Engine.

### 4:05–5:05 — Góc nhìn supervisor và IRT/CAT

**Thao tác trên UI**

1. Chuyển sang cửa sổ D, tài khoản supervisor.
2. Mở **Taker overview**.
3. Chọn `demo_taker` và một phiên CAT hoàn thành.
4. Chỉ vào score, theta, standard error, số câu, lý do dừng và CAT trajectory.
5. Chỉ vào bảng năng lực hoặc lịch sử các lần thi.

**Lời thoại**

“Người thi chỉ thấy điểm, mức hiểu và hướng học. Supervisor mới thấy các thông số của người test. Đây là tách quyền theo vai trò và cũng tránh đưa thông tin kỹ thuật gây nhiễu vào giao diện người học.”

“Điểm thô trả lời câu hỏi người học đúng bao nhiêu; IRT trả lời bằng chứng đó nói gì về
năng lực khi xét cả độ khó, độ phân biệt và xác suất đoán đúng. 

Hai giá trị không được đồng nhất.”

**Kết quả mong đợi**

- Supervisor xem được nhiều người học và nhiều phiên thi.
- CAT trajectory thể hiện theta thay đổi sau từng câu.
- Lý do chọn câu và lý do dừng có thể truy vết.

### 5:05–5:50 — Cơ sở tri thức, ngân hàng câu hỏi và LLM có quản trị

**Thao tác trên UI**

1. Chuyển sang admin **System overview**.
2. Chỉ vào số subject, active questions, knowledge units, facts và active rules.
3. Mở **Question bank** để chỉ vào trạng thái review/activation và tham số IRT.
4. Mở **LLM workspace** và hiển thị một artifact đã lưu.

**Lời thoại**

“Tại thời điểm chuẩn bị demo, PostgreSQL có 256 câu hỏi, trong đó 201 câu đã được duyệt và đưa vào sử dụng ở
hai môn. Con số trên System overview là nguồn sự thật khi trình bày. Mỗi câu có Bloom,
độ khó, thời gian trung bình, tham số IRT và ánh xạ kiến thức. Cơ sở tri thức dùng
Rela-model `K = (C, R, Rules)`: concepts biểu diễn người học, môn, tiêu chí, câu hỏi và
phiên thi; relations biểu diễn ánh xạ; rules suy ra điểm yếu và hướng học.”

“LLM tạo bản nháp hoặc diễn đạt giải thích. 

Câu hỏi mới phải qua kiểm tra cấu trúc, đáp án, trùng lặp, Bloom, độ khó, provenance và review của admin trước khi
được activate.”

**Kết quả mong đợi**

- Dashboard hiện 256 câu tổng cộng và 201 câu active trên hai môn; nếu dữ liệu thay đổi,
  đọc đúng số đang hiển thị thay vì thuộc lòng con số này.
- Admin xem và chỉnh cấu hình từ `sys_props`.
- Artifact LLM có trạng thái và provenance; không tự động trở thành câu thi.

### 5:50–6:30 — Suy luận, hội tụ và calibration thực nghiệm

**Thao tác trên UI**

1. Mở **IRT calibration**.
2. Chỉ vào `Real responses`, `Evaluated items`, ngưỡng sample và cột `Reliability`.
3. Không nhấn áp dụng tham số nếu chưa đủ ngưỡng production.
4. Nếu có slide phụ, chỉ vào bảng kết quả simulator trong
   `docs/evaluation_report.md`.

**Lời thoại**

IRT calibration sử dụng một lượng đủ lớn dữ liệu trả lời thực tế để kiểm tra và ước lượng lại các tham số a, b, c của từng câu hỏi

Phần này dùng response thật để so sánh xác suất dự đoán với độ chính xác quan sát qua các lần làm bài test,
point-biserial, fit RMSE và đề xuất tham số b (độ khó) mới. Dữ liệu hiện còn thưa nên hệ thống đánh
dấu reliability thấp và không tự ghi đè tham số production khi chưa đạt ngưỡng.”

**Kết quả mong đợi**

- Calibration UI hiển thị số response thật, độ tin cậy và giới hạn dữ liệu.
- Báo cáo simulator có RMSE `0.3499`, MAE `0.2796`, bias `0.0511`, trung bình `20.79`
  câu và convergence `90%` cho mỗi môn trong lần chạy hiện tại.
- Không đồng nhất simulation với empirical calibration.

### 6:30–7:00 — Kết luận

**Lời thoại đề xuất**

“Nhóm em đã đáp ứng lõi của đề tài: 201 câu active ở hai môn, IRT 3PL, CAT thời
gian thực, đề cố định, placement, hồ sơ năng lực thay đổi, Rela-model có bộ suy diễn và
trace, Knowledge Graph, radar, lộ trình cá nhân hóa, LLM sinh nháp và giải thích có kiểm
soát, cùng đánh giá hội tụ.”

“Điểm vượt yêu cầu là hệ thống không dừng ở một theta theo môn. Nó liên kết từng câu trả
lời tới tiêu chí, bảo toàn lịch sử, trực quan hóa mức hiểu, và dùng cùng bằng chứng cho
CAT, graph, radar, lộ trình dạng chuỗi và trợ lý học tập có công cụ MCP. DKT và
Reinforcement Learning vẫn là hướng mở rộng có chủ đích; hiện tại CAT/IRT và bộ suy
diễn quyết định hành vi chính để đảm bảo tính xác định và giải thích được.”

## 5. Bảng giải nghĩa thuật ngữ kỹ thuật

Bảng này dùng để trả lời nhanh khi giảng viên hỏi “chỉ số đó là gì và ảnh hưởng như
thế nào?”. Các chỉ số kỹ thuật chỉ hiển thị cho supervisor/admin; người thi chỉ thấy
điểm, mức hiểu và hướng học.

| Thuật ngữ | Nghĩa ngắn gọn | Ví dụ ảnh hưởng trong hệ thống |
| --- | --- | --- |
| **IRT** | Item Response Theory – mô hình xác suất liên hệ năng lực người học với đặc tính của từng câu hỏi. | Hai người cùng đúng một câu chưa chắc nhận cùng một kết luận năng lực nếu các câu trước có độ khó khác nhau. |
| **IRT 3PL** | Mô hình 3 tham số gồm discrimination `a`, difficulty `b` và guessing `c`. | Hệ thống tính xác suất trả lời đúng thay vì chỉ đếm số câu đúng. |
| **IRT `a` – discrimination** | Độ phân biệt; cho biết câu hỏi phân biệt người có năng lực gần nhau tốt đến mức nào. `a` cao làm đường xác suất dốc hơn. | Một câu có `a` cao và phù hợp với theta hiện tại thường cung cấp nhiều thông tin hơn. |
| **IRT `b` – difficulty** | Vị trí độ khó trên thang năng lực; `b` càng cao thì câu càng khó. | CAT có thể chọn câu quanh theta hiện tại, thay vì luôn đưa câu dễ hoặc khó cố định. |
| **IRT `c` – guessing** | Xác suất trả lời đúng do đoán; là giới hạn dưới của xác suất 3PL. | Với câu nhiều lựa chọn, một câu đúng do đoán không được xem như bằng chứng mạnh về năng lực. |
| **`theta`** | Năng lực tiềm ẩn của người học trên thang IRT, thường bắt đầu gần 0. | Sau mỗi câu, theta được cập nhật; theta tăng không có nghĩa là điểm phần trăm tăng cùng tỷ lệ. |
| **Standard error (SE)** | Độ không chắc chắn của ước lượng theta; càng thấp thì ước lượng càng ổn định. | CAT có thể dừng khi SE đạt ngưỡng cấu hình sau minimum số câu. |
| **Fisher information** | Lượng thông tin một câu cung cấp tại theta hiện tại. | CAT ưu tiên câu có information cao, nhưng vẫn xét tiêu chí yếu, cân bằng nội dung và exposure. |
| **EAP** | Expected A Posteriori – cách ước lượng theta bằng phân phối hậu nghiệm trên một lưới theta và prior. | Backend dùng chuỗi response để tính theta sau mỗi câu, rồi lưu theta trước/sau và SE. |
| **CAT** | Computerized Adaptive Testing – bài thi chọn câu tiếp theo dựa trên năng lực hiện tại. | Hai người có lịch sử khác nhau có thể nhận các câu tiếp theo khác nhau. |
| **Mastery probability** | Xác suất chuyển đổi từ theta sang mức làm chủ, dùng để hiển thị radar và phân loại tiêu chí. | Một tiêu chí dưới ngưỡng được đưa vào learning path; tiêu chí đạt ngưỡng Mastered bị loại khỏi lộ trình cần cải thiện. |
| **Bloom level** | Mức độ nhận thức của câu hỏi: Remember, Understand, Apply, Analyze, Evaluate, Create. | Admin/supervisor dùng để kiểm tra độ phủ nhận thức; CAT có thể lọc Bloom theo cấu hình. |
| **Difficulty label / `difficulty_norm`** | Nhãn dễ/trung bình/khó và giá trị chuẩn hóa của độ khó trong question bank. | Fixed blueprint dùng nhãn để phân bổ câu; CAT dùng thêm `b` và Fisher information. |
| **Assessment criterion** | Tiêu chí kiến thức cụ thể, ví dụ “Apply B-tree index” hoặc “Apply TCP congestion control”. | Câu hỏi được ánh xạ vào criterion; mastery của criterion tạo radar, graph và learning path. |
| **Evidence** | Response đã chấm từ bài đã hoàn thành, gắn với câu hỏi và criterion. | Evidence tăng qua nhiều bài giúp phân biệt tín hiệu ban đầu với kết luận ổn định. |
| **Rela-model `K=(C,R,Rules)`** | Mô hình cơ sở tri thức gồm concepts, relations và rules. | Fact response tạo bằng chứng; rule suy ra điểm yếu hoặc `recommended_next`; trace lưu provenance. |
| **LLM** | Large Language Model – mô hình ngôn ngữ dùng để diễn đạt, giải thích hoặc tạo draft. | LLM không tự quyết định theta, không được tự activate câu hỏi và không thay thế validation/rule engine. |
| **MCP** | Model Context Protocol – lớp công cụ có schema và quyền truy cập để model truy vấn dữ liệu hệ thống. | Learner assistant chỉ nhận dữ liệu của người đang đăng nhập, bài đã hoàn thành và tri thức môn học được phép đọc. |
| **Placement assessment** | Bài kiểm tra đầu vào để tạo baseline criterion-level trước khi học/thi thích ứng. | Kết quả placement khởi tạo hồ sơ năng lực và giúp các bài sau chọn câu phù hợp hơn. |
| **Fixed blueprint** | Đề cố định theo subject, số câu và difficulty distribution. | Mọi người trong cùng blueprint có cùng tập ràng buộc; hệ thống báo lỗi nếu question bank không đủ. |
| **Exposure penalty** | Điểm phạt câu đã được dùng nhiều trong các session. | CAT giảm việc lặp một item phổ biến, giúp bảo vệ question bank và tăng độ phủ. |
| **IRT calibration** | Ước lượng lại tham số câu hỏi từ response thật để xem `b` hiện tại có phù hợp không. | Không cập nhật ngay chỉ vì một vài người làm bài; hệ thống chỉ cho áp dụng khi đủ sample. |

### Mô hình cơ sở tri thức đang dùng: `K = (C, R, Rules)`

Trong implementation, mô hình được lưu và kiểm soát bằng các bảng `kb_definitions`,
`kb_facts`, `kb_rules` và `kb_inference_traces`. LLM không thay thế các bảng này; nó chỉ
đọc dữ liệu được phân quyền hoặc diễn đạt kết quả đã có provenance.

#### 1. Concepts — tập khai niệm `C`

| Cấp | Concepts đang dùng | Vai trò |
| --- | --- | --- |
| `C(0)` | `NUMBER`, `TEXT`, `BOOLEAN` | Giá trị nguyên thủy cho theta, IRT parameters, score, mã và cờ đúng/sai. |
| `C(1)` | `SUBJECT`, `KNOWLEDGE_UNIT`, `BLOOM_LEVEL`, `STUDENT` | Các đối tượng nền: Database Systems, topic/skill, cấp nhận thức và người thi. |
| `C(2)` | `QUESTION`, `ANSWER_OPTION`, `ABILITY_STATE` | Câu hỏi có stem, Bloom và `a/b/c`; phương án trả lời; trạng thái theta/SE/mastery của người học. |
| `C(3)` | `EXAM_SESSION` | Đối tượng tổng hợp liên kết student, question, response, score và ability movement trong một phiên. |
| Mở rộng learner model | `AssessmentCriterion`, `AbilitySnapshot`, `LearnerConversation` | Criterion có mục tiêu và mastery threshold; snapshot lưu bằng chứng theo session; conversation lưu hội thoại đã grounding. |

Ví dụ: `QUESTION` thuộc một `SUBJECT`, có thể đo nhiều `KNOWLEDGE_UNIT`, có một
`BLOOM_LEVEL`, chứa phương án và mang ba tham số IRT. `ABILITY_STATE` không phải điểm
thi; nó là ước lượng năng lực thay đổi theo response.

#### 2. Relations — các quan hệ `R`

| Relation | Dạng fact ví dụ | Ý nghĩa trong hệ thống |
| --- | --- | --- |
| `is_a` | `q001 is_a QUESTION` | Fact kiểu đối tượng theo Rela-model. |
| `belongs_to` | `indexing belongs_to DATABASE` | Knowledge unit thuộc subject. |
| `measures` | `q001 measures DB_INDEX` | Câu hỏi đo topic/skill/criterion nào. |
| `prerequisite_of` | `primary_key prerequisite_of indexing` | Quan hệ tiên quyết; được khai báo transitive. |
| `has_bloom_level` | `q001 has_bloom_level APPLY` | Cấp nhận thức của câu hỏi. |
| `selected_option` | `selected_option(student,q001,opt_b)` | Người thi đã chọn phương án nào. |
| `unit_accuracy` | `unit_accuracy(student,DB_INDEX,0.42)` | Bằng chứng độ chính xác theo knowledge unit. |
| `criterion_mastery` | `criterion_mastery(student,DB_INDEX,0.42)` | Mastery IRT-derived của một criterion. |
| `has_irt_parameters` | `has_irt_parameters(q001,1.2,0.5,0.25)` | Tuple `a`, `b`, `c` của item. |
| `has_binary_response` | `has_binary_response(student,q001,false)` | Response đúng/sai được đưa vào IRT. |
| `computed_theta` / `updated_theta` | `computed_theta(student,0.31)` → `updated_theta(student,0.31)` | Trace trước/sau của cập nhật năng lực. |
| `weak_unit` / `has_mastery` | `weak_unit(student,DB_INDEX)` | Đánh dấu unit yếu hoặc đã đạt mastery. |
| `recommended_next` | `recommended_next(student,DB_INDEX,remediate)` | Khuyến nghị học tiếp do rule suy ra. |
| `question_ready`, `best_option`, `displayed_options_include` | `question_ready(q001)` | Kiểm tra câu hợp lệ và phương án đúng có được hiển thị. |
| `valid_question_pool`, `student_theta`, `difficulty_blueprint` | Facts đầu vào của generator/CAT | Xác nhận pool, năng lực hiện tại và yêu cầu blueprint. |
| `exam_generated_with_constraints` | `exam_generated_with_constraints(student,DATABASE)` | Goal chứng minh đề thỏa ràng buộc. |

Các relation cấu trúc như `belongs_to`, `measures`, `prerequisite_of` tạo graph tri thức;
các relation vận hành như `criterion_mastery`, `updated_theta` và `recommended_next`
được tạo từ response, IRT và inference trace.

#### 3. Rules — các luật suy diễn đang dùng

| Rule | Điều kiện chính | Fact/goal sinh ra | Tác động nhìn thấy |
| --- | --- | --- | --- |
| `R_GEN_INCLUDE_BEST` | Question ready và có best option | Displayed options phải chứa best option | Không tạo đề thiếu đáp án được chấm đúng. |
| `R_SCORE_SELECTED_OPTION` | Student chọn option và option có weight | `awarded_score` | Tạo score từ phương án đã chọn. |
| `R_UPDATE_ABILITY_3PL` | Có binary response, IRT `a/b/c`, theta mới | `updated_theta` | Lưu thay đổi theta/SE sau response. |
| `R_GEN_IRT_BALANCED` | Pool hợp lệ, student theta, difficulty blueprint | `exam_generated_with_constraints` | Fixed exam/CAT giữ difficulty và content constraints. |
| `R_LEARNING_START_SUBJECT` | Subject chưa có evidence | `recommended_next(...,initial_assessment)` | Đề xuất placement/assessment đầu tiên. |
| `R_LEARNING_REMEDIATE` | Unit accuracy `< 0.50` | `weak_unit` và `recommended_next(...,remediate)` | Learning path ưu tiên ôn nền tảng. |
| `R_LEARNING_REINFORCE` | Accuracy từ `0.50` đến `< 0.75` | `recommended_next(...,reinforce)` | Đề xuất luyện tập củng cố. |
| `R_LEARNING_ADVANCE` | Accuracy `≥ 0.75` | `has_mastery` và `recommended_next(...,advance)` | Unit được xem là đạt và không còn là bước remediation. |
| `R_CRITERION_REMEDIATE` | Criterion mastery `< 0.45` | `recommended_next(...,remediate)` | Criterion cần xem lại prerequisite. |
| `R_CRITERION_DEVELOP` | Mastery `0.45–<0.60` | `recommended_next(...,develop)` | Criterion cần guided practice. |
| `R_CRITERION_REINFORCE` | Mastery `0.60–<0.75` | `recommended_next(...,reinforce)` | Criterion đã hiểu nhưng cần củng cố trước Mastered. |
| `R_DIFFICULTY_HARD` | `difficulty_norm ≥ 0.80` | `classified_as(...,hard)` | Phân loại difficulty phục vụ governance và blueprint. |
| `R_LOW_TOPIC_INCREASE_FREQUENCY` | Unit là `weak_unit` | `topic_weight(...,increased)` | CAT tăng ưu tiên nội dung còn yếu. |

Các luật được lưu ngoài code, có priority, weight, explanation template và source. Bộ
suy diễn hỗ trợ unification, comparison, forward closure, backward goal search và trace
rút gọn. CAT vẫn có một lớp tính toán riêng để tính Fisher information và selection
score; kết quả của lớp này được lưu cùng fact/trace để supervisor có thể kiểm tra.

#### 4. Ví dụ một chuỗi suy luận hoàn chỉnh

```text
Response(student, q001, incorrect)
  + q001 measures DB_INDEX
  + q001 has IRT parameters (a, b, c)
        ↓ R_UPDATE_ABILITY_3PL
updated_theta(student, theta_new)
        ↓ aggregate response evidence
criterion_mastery(student, DB_INDEX, 0.42)
        ↓ R_CRITERION_REMEDIATE
weak_unit(student, DB_INDEX)
recommended_next(student, DB_INDEX, remediate)
        ↓ learner model / UI
Radar thấp → graph criterion → learning path → grounded assistant advice
```

Đây là cách câu trả lời trở thành evidence, evidence cập nhật ability, rule suy ra
recommendation, rồi cùng một fact được sử dụng ở radar, graph, CAT và Learning assistant.

### Cách đọc một ví dụ IRT

Trong implementation, xác suất đúng của một item được tính theo 3PL:

```text
P(correct | theta) = c + (1 - c) / (1 + exp(-1.7 * a * (theta - b)))
```

`1.7` là scale constant đang được lưu trong cấu hình IRT. Công thức này là xác suất mô
hình, không phải điểm phần trăm hiển thị cho người thi.

Với câu hỏi có `a = 1.2`, `b = 0.5`, `c = 0.25`, người có `theta` gần `0.5` nằm ở vùng
câu hỏi phân biệt tốt. Nếu người học trả lời đúng, theta thường tăng; nếu trả lời sai,
theta thường giảm hoặc tăng ít. Tuy nhiên hệ thống còn xem các câu khác, prior EAP và
độ tin cậy của toàn bộ chuỗi response, nên không có quy tắc “đúng một câu = cộng cố định
một điểm”.

## 6. CAT trong hệ thống được thực hiện như thế nào?

CAT của project là một vòng lặp xác định, chỉ dùng câu hỏi active, validated và chưa
dùng trong cùng session:

1. **Khởi tạo:** người thi chọn một subject. Backend lấy theta và SE gần nhất của
   subject đó; nếu chưa có lịch sử thì dùng theta khởi tạo và SE mặc định.
2. **Tạo pool:** lọc câu đúng subject, trạng thái active, topic/skill/Bloom theo config,
   đồng thời loại câu đã xuất hiện trong session.
3. **Chấm điểm ứng viên:** với mỗi câu, hệ thống tính Fisher information tại theta hiện
   tại, weak-unit score từ các criterion mastery thấp, content-balance score, criterion
   coverage score và exposure penalty.
4. **Chọn câu:** điểm tổng quát có dạng:

   ```text
   selection score = information
                   + weak-unit priority
                   + content balance
                   + criterion coverage
                   - exposure penalty
   ```

   Các trọng số nằm trong `sys_props`, vì vậy supervisor/admin có thể điều chỉnh chính
   sách mà không sửa code.
5. **Trả lời và cập nhật:** backend kiểm tra ownership, session state, option được hiển
   thị và duplicate answer. Sau đó dùng IRT 3PL EAP để tính theta/SE mới, lưu response,
   ability snapshot, fact và trace.
6. **Lặp lại hoặc dừng:** hệ thống chọn câu tiếp theo nếu chưa đạt điều kiện dừng. CAT
   dừng khi đạt maximum, hết pool, SE đủ thấp, hoặc theta ổn định trong stability
   window; không dừng trước minimum số câu.
7. **Thời gian:** estimated time chỉ là countdown hướng dẫn. Hết thời gian không tự
   khóa hoặc nộp bài.

Điểm quan trọng: CAT không sinh câu hỏi mới trong lúc thi. Nó chọn trong question bank
hiện có; LLM generation là một workspace quản trị riêng và câu mới phải qua review trước
khi active.

## 7. IRT calibration là gì?

IRT calibration khác với việc cập nhật theta cho một người thi:

- **Theta update:** diễn ra sau từng response để ước lượng năng lực của một người.
- **Calibration:** diễn ra trên nhiều response của nhiều người để kiểm tra đặc tính của
  một item, đặc biệt là độ khó `b`.

Quy trình hiện tại:

1. Lấy response thật từ các bài đã hoàn thành, cùng `theta_before`, kết quả đúng/sai và
   tham số item hiện tại.
2. Tính observed accuracy, predicted accuracy theo IRT 3PL, mean response time,
   point-biserial và binned fit RMSE.
3. Tìm `suggested_b` bằng conditional maximum likelihood trên lưới độ khó; hiện tại
   giữ `a` và `c` cố định để tránh tuyên bố full 3PL calibration khi dữ liệu chưa đủ.
4. Gắn reliability: `insufficient` nếu dưới 30 response, `provisional` nếu đã đủ để
   đánh giá nhưng chưa đủ 100 response để ghi production, và `eligible` khi đạt ngưỡng
   áp dụng.
5. Admin có thể chọn apply eligible estimates. Nếu chưa đủ 100 response, hệ thống lưu
   kết quả mô tả và không ghi đè tham số production.

Ví dụ: nếu một câu đang có `b = 0.2`, dữ liệu thật cho thấy câu khó hơn và conditional
MLE đề xuất `b = 0.8`, hệ thống chỉ hiển thị đề xuất cùng reliability và sample size.
Nó chưa thay đổi question bank nếu chưa đạt ngưỡng. Điều này bảo vệ CAT khỏi một tham
số mới được suy ra từ vài response ngẫu nhiên.

Calibration cũng khác với báo cáo simulator: simulator dùng learner giả lập để đánh giá
RMSE/MAE/bias/convergence của thuật toán CAT; calibration dùng response thật để đánh giá
item. Cả hai đều cần được trình bày riêng.

## 8. Đối chiếu nhanh với yêu cầu đề tài

| Yêu cầu | Bằng chứng nên chỉ trên UI |
| --- | --- |
| Tối thiểu 200 câu, từ hai môn | Admin – System overview và Question bank |
| Tham số IRT và thời gian trung bình | Question detail / supervisor metrics |
| Sinh đề theo môn, số câu, độ khó | Start test – Fixed blueprint |
| Cập nhật năng lực sau mỗi bài/câu | CAT trajectory và Progress history |
| CAT chọn câu tối ưu tiếp theo | Supervisor – lý do chọn, Fisher information, theta/SE |
| Rela-model, facts, relations, rules | System overview, graph và inference trace |
| Cá nhân hóa và lộ trình học | Progress – radar và chuỗi `Subject → criterion yếu nhất → bước kế tiếp` |
| Knowledge Graph từng sinh viên | Learning graph mở theo từng nhánh |
| LLM theo Bloom và XAI | LLM workspace, Learning assistant và công cụ MCP chỉ đọc |
| Đánh giá hội tụ năng lực | `docs/evaluation_report.md`; tách biệt với IRT calibration |
| Placement assessment | Start test – Placement assessment |

## 9. Phương án dự phòng khi demo

| Sự cố | Cách xử lý trong lúc trình bày |
| --- | --- |
| OpenRouter chậm hoặc hết quota | Mở artifact đã persist; không chờ gọi LLM trực tiếp |
| Radar chưa có dữ liệu ở tài khoản mới | Chuyển sang `demo_taker`; dữ liệu unknown không phải lỗi |
| Learning path có quá nhiều node | **Reset view**, mở subject rồi mở từng criterion theo chuỗi; không nhấn **Show all** |
| Knowledge Graph có quá nhiều node | **Reset view**, sau đó chỉ mở một subject và một criterion |
| Không đủ thời gian làm bài | Chỉ mở câu đầu của Placement/CAT rồi chuyển sang phiên hoàn thành ở supervisor |
| Phiên CAT live thay đổi khó dự đoán | Dùng CAT trajectory đã chuẩn bị để giải thích |
| Backend vừa cập nhật nhưng UI còn cũ | Khởi động lại backend trước giờ demo và refresh Streamlit |

## 10. Những điều không nên làm trong 7 phút

- Không nhập đủ một bài 20 câu trực tiếp.
- Không chờ LLM sinh nội dung live.
- Không mở toàn bộ graph cùng lúc.
- Không giải thích chi tiết source code, endpoint hoặc Docker.
- Không đồng nhất điểm phần trăm với theta hay mastery probability.
- Không gọi kết quả simulator là calibration từ người học thật.
- Không nói LLM có thể đọc toàn bộ database; nó chỉ dùng các công cụ MCP đã phân quyền.
- Không tuyên bố DKT/RL đã hoàn thiện; nêu rõ đây là hướng mở rộng sau CAT/IRT.
