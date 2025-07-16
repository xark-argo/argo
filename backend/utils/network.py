import requests


def is_china_network():
    try:
        response = requests.get("http://ipinfo.io")
        country = response.json().get("country")
        return country == "CN"
    except Exception:
        return False
