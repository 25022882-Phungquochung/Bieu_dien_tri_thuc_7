"""Agent 2048 dùng heuristic và tìm kiếm Expectimax nông."""

from __future__ import annotations

import time

import numpy as np

# Observation là dữ liệu trạng thái engine đưa cho agent (định nghĩa trong observation.py).
from game2048.observation import Observation
# move_board mô phỏng một nước, trả về (bàn mới, điểm gộp, bàn có thay đổi hay không).
from game2048.rules import move_board
# Move là enum 4 hướng được engine dùng (định nghĩa trong types.py).
from game2048.types import Move


class _SearchTimeout(Exception):
    """Dừng một tầng tìm kiếm chưa hoàn tất khi sắp hết ngân sách."""
    # Hiện tại choose_move chưa dùng ngoại lệ này để dừng tìm kiếm.


class Agent:
    # Đổi tên này thành tên đội; nó sẽ xuất hiện trong UI và file kết quả.
    name = "nhom_7"

    def reset(agent7, seed: int | None = None) -> None:
        """Đặt lại thống kê giữa các ván.

        seed được truyền theo API AgentProtocol trong interfaces.py và từ benchmark.py.
        Agent không có RNG riêng: engine (engine.py/rng.py) dùng seed để sinh ô.
        """
        # Giữ tham số seed để đúng API chung; agent hiện không cần dùng nó.
        _ = seed
    @staticmethod
    def evaluate(board: np.ndarray, merge_score: int) -> float:
        # Heuristic tự viết trong class Agent, không lấy từ module heuristic.py.
        # board là bàn sau mô phỏng; merge_score là điểm nước vừa gộp (từ move_board).
        HS_O_TRONG = 30  # thưởng ô trống
        HS_DON_DIEU = 22    # phạt đơn điệu
        HS_DO_MUOT = 1.2  # phạt độ mượt

        # Đổi giá trị ô thành số mũ: 2 -> 1, 4 -> 2, 8 -> 3; ô trống giữ 0.
        log2_board = np.zeros(board.shape)
        log2_board[board > 0] = np.log2(board[board > 0])

        # Chênh lệch giữa các ô kề nhau theo chiều ngang (axis=1) và dọc (axis=0).
        d_row = np.diff(log2_board, axis=1)
        d_col = np.diff(log2_board, axis=0)

        # Chênh lệch lớn giữa ô kề nhau bị phạt.
        do_muot = np.abs(d_row).sum() + np.abs(d_col).sum()

        # Đo mức các hàng/cột đổi chiều tăng-giảm; đổi chiều ít thì bàn dễ xếp gọn hơn.
        don_dieu = 0.0
        for d, axis in ((d_row, 1), (d_col, 0)):
            up = np.maximum(d, 0).sum(axis=axis)
            down = np.maximum(-d, 0).sum(axis=axis)
            don_dieu += np.minimum(up, down).sum()

        # Càng nhiều ô trống thì càng có chỗ cho các nước đi tiếp.
        o_trong = np.count_nonzero(board == 0)

        # Điểm heuristic cao hơn được xem là trạng thái tốt hơn.
        return HS_O_TRONG * o_trong - HS_DON_DIEU * don_dieu - HS_DO_MUOT * do_muot + merge_score

    def choose_move(agent7, obs: Observation, time_limit_ms: float) -> Move:
        # Không thể chọn nước đi nếu trạng thái hiện tại không còn nước hợp lệ.
        if not obs.legal_moves:
            raise ValueError("choose_move được gọi ở trạng thái kết thúc")

        # Chỉ dùng tối đa 80% thời gian được cấp và giới hạn mỗi lượt tìm kiếm ở 50 ms.
        move_budget_ms = min(50.0, max(0.0, time_limit_ms) * 0.8)
        # Đổi ngân sách từ mili giây sang giây để so sánh với đồng hồ hiệu năng.
        deadline = time.perf_counter() + move_budget_ms / 1000.0

        def player_value(board, depth):
            # Đến độ sâu giới hạn thì ước lượng giá trị bàn cờ thay vì tìm tiếp.
            if depth <= 0:
                return agent7.evaluate(board, 0)

            # Lượt của người chơi: thử mọi hướng và giữ giá trị tốt nhất.
            best = float("-inf")

            for move in Move:
                after, score, changed = move_board(board, move)

                # Chỉ xét các hướng thực sự làm thay đổi bàn cờ.
                if changed:
                    best = max(best, chance_value(after, depth, score))

            # Nếu không hướng nào hợp lệ, xem đây là trạng thái bất lợi.
            return best if best != float("-inf") else agent7.evaluate(board, 0) - 1000.0

        def chance_value(after, depth, score):

            # Dừng tìm kiếm khi hết ngân sách thời gian.
            if time.perf_counter() >= deadline:
                raise _SearchTimeout

            # Liệt kê các ô trống, nơi ô mới có thể xuất hiện ngẫu nhiên.
            o_trong = np.argwhere(after == 0)

            # Nếu không còn ô trống, không thể sinh ô mới; tiếp tục lượt kế tiếp.
            if len(o_trong) == 0:
                return score + player_value(after, depth - 1)

            # Tính giá trị kỳ vọng trên mọi vị trí và loại ô có thể được sinh.
            total = 0.0

            for r, c in o_trong:
                # Ô 2 xuất hiện với xác suất 90%, ô 4 với xác suất 10%.
                for tile, prob in ((2, 0.9), (4, 0.1)):
                    spawned = after.copy()
                    spawned[r, c] = tile
                    total += prob * player_value(spawned, depth - 1)

            # Các vị trí trống có khả năng như nhau nên lấy trung bình theo số ô.
            return score + total / len(o_trong)

        # Mặc định chọn nước hợp lệ đầu tiên để luôn có phương án trả về.
        best_move = obs.legal_moves[0]

        # Tìm kiếm tăng dần độ sâu; nếu hết giờ thì giữ kết quả từ độ sâu trước.
        for depth in (1, 2):
            try:
                best_value = float("-inf")
                candidate = best_move

                # Đánh giá từng nước hợp lệ và lưu nước có giá trị cao nhất.
                for move in obs.legal_moves:
                    after, score, _ = move_board(obs.board, move)
                    value = chance_value(after, depth, score)

                    if value > best_value:
                        candidate, best_value = move, value
                        
            except _SearchTimeout:
                break
            best_move = candidate
            
        # Trả về nước tốt nhất tìm được trong giới hạn thời gian.
        return best_move
