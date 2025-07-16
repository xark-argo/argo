import re


def truncate_image_base64(text):
    def replacer(match):
        prefix, base64_data = match.groups()
        length = len(base64_data)

        if length < 10:
            return f"{prefix}{base64_data}"

        return f"{prefix}{base64_data[:10]}...[TRUNCATED]...{base64_data[-10:]}"

    return re.sub(r"(data:image\/[a-zA-Z]+;base64,)([A-Za-z0-9+/=]+)", replacer, text)
