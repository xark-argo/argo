import time


def is_in_china():
    # system_lang = locale.getlocale()[0]
    # is_chinese_lang = (system_lang == "zh_CN")
    current_timezone = time.tzname[0]
    is_china_timezone = "China" in current_timezone or "CST" in current_timezone or "中国标准时间" in current_timezone

    return is_china_timezone


if __name__ == "__main__":
    if is_in_china():
        print("in china")
    else:
        print("not in china")
