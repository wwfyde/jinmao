from datetime import datetime


def generate_version_string(date: datetime | None = None) -> str:
    """
    根据日期生成版本号
    """
    if date is None:
        date = datetime.now()
    year = date.year
    month = date.month

    # 确定季度
    if 1 <= month <= 3:
        quarter = 1
    elif 4 <= month <= 6:
        quarter = 2
    elif 7 <= month <= 9:
        quarter = 3
    elif 10 <= month <= 12:
        quarter = 4
    else:
        raise ValueError("Invalid month value")

    return f"{year}Q{quarter}"


if __name__ == '__main__':
    date = datetime.now()
    print(generate_version_string(date))
