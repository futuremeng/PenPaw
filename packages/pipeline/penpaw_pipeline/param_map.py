"""滑块 → 流水线参数映射（PRD 附录 A 唯一入口）。

M2a：在 PRD 附录 A 的 4 个参数基础上，增加规则式生成器所需的
contour_epsilon（DP 简化容差）与 bezier_tension（贝塞尔平滑强度）。
M2 调参定稿后需同步更新 PRD 附录 A、TDD §5 与单元测试。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MappedParams:
    # Stage 1：方向场高斯平滑核（像素）
    flow_sigma_px: float
    # Stage 2：最大命令数上限
    n_max: int
    # Stage 3：曲率惩罚 / 控制点惩罚（PRD 附录 A）
    lambda_c: float
    lambda_p: float
    # M2a 规则式：Douglas-Peucker 简化容差（周长占比）
    contour_epsilon: float
    # M2a 规则式：贝塞尔平滑强度 0..1（越大越圆滑）
    bezier_tension: float

    def to_dict(self) -> dict:
        return asdict(self)


def _clamp01(v: int) -> float:
    return min(max(v, 0), 100) / 100


def map_sliders(smoothness: int, detail: int) -> MappedParams:
    """意图滑块 → 流水线参数。

    单调性（由单元测试断言）：
    - smoothness↑ → flow_sigma_px↑, lambda_c↑, contour_epsilon↑, bezier_tension↑
    - detail↑ → n_max↑, lambda_p↓
    """
    s = _clamp01(smoothness)
    d = _clamp01(detail)
    return MappedParams(
        flow_sigma_px=1.0 + s * 5.0,
        n_max=int(200 + d * 800),
        lambda_c=0.01 * (s * 2) ** 2,
        lambda_p=0.005 * (1 - d) + 0.001,
        contour_epsilon=0.002 + s * 0.02,
        bezier_tension=0.3 + s * 0.7,
    )
