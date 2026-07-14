from datetime import datetime, timezone
from typing import Any, Dict


DEMO_DISCLAIMER = "全部为虚拟演示数据，仅用于方案展示，不代表真实设备检测结果。"


def demo_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "demo": True,
        "data_source": "mock",
        "not_real_device_data": True,
        "disclaimer": DEMO_DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    data.update(payload)
    return data
