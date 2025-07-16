import json
import os

from utils.path import app_path


class Translation:
    def __init__(self, language_path: str):
        self.language_path = language_path
        self.language = "en"
        self.language_data = self.load()

    def set_locale(self, language: str):
        self.language = language

    def load(self):
        language_data = {}
        for language_file in os.listdir(self.language_path):
            if ".json" not in language_file:
                continue
            language = language_file.split(".")[0]
            with open(os.path.join(self.language_path, language_file), encoding="utf-8") as fp:
                json_file = json.load(fp)
            language_data[language] = json_file
        return language_data

    def t(self, key: str, **kwargs):
        origin_value = self.language_data[self.language]
        key_list = key.split(".")
        for each_key in key_list:
            origin_value = origin_value[each_key]
        origin_value = origin_value.format(**kwargs)
        return origin_value

    def generate_log(self):
        change_log = self.language_data[self.language]["changelog"]
        final = []
        for version, change_list in change_log.items():
            final.append(f"#### {version}")
            for index, change in enumerate(change_list):
                final.append(f"{index + 1}. {change}")
        return "\n\n".join(final)


translation: Translation


def init():
    global translation
    translation_path = app_path("configs", "locales")
    translation = Translation(language_path=translation_path)
