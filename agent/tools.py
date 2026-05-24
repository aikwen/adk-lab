import datetime
from zoneinfo import ZoneInfo


def get_weather(city: str) -> dict:
    """查询指定城市的当前天气。

    Args:
        city: 城市名称，例如「福州」「台北」「New York」。

    Returns:
        包含工具执行状态和天气结果的字典。
    """
    normalized_city = city.lower()

    if normalized_city == "new york":
        return {
            "status": "success",
            "report": "New York 当前天气晴朗，气温约 25 摄氏度。",
        }

    if normalized_city in {"taipei", "台北"}:
        return {
            "status": "success",
            "report": "台北当前多云，气温约 28 摄氏度。",
        }

    if normalized_city in {"fuzhou", "福州"}:
        return {
            "status": "success",
            "report": "福州当前晴朗，气温约 30 摄氏度。",
        }

    return {
        "status": "error",
        "error_message": f"暂时没有「{city}」的天气信息。",
    }


def get_current_time(city: str) -> dict:
    """查询指定城市的当前时间。

    Args:
        city: 城市名称，例如「福州」「台北」「New York」。

    Returns:
        包含工具执行状态和当前时间结果的字典。
    """
    timezone_map = {
        "new york": "America/New_York",
        "taipei": "Asia/Taipei",
        "台北": "Asia/Taipei",
        "fuzhou": "Asia/Shanghai",
        "福州": "Asia/Shanghai",
    }

    normalized_city = city.lower()
    tz_identifier = timezone_map.get(normalized_city)

    if tz_identifier is None:
        return {
            "status": "error",
            "error_message": f"暂时没有「{city}」的时区信息。",
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = f"{city} 当前时间是 {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}。"

    return {
        "status": "success",
        "report": report,
    }