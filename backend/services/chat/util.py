def get_file_docs(files: list[dict]) -> list[str]:
    docs = []
    for file in files:
        if not isinstance(file, dict):
            raise ValueError("Invalid file format, must be dict")
        if file.get("type", "") != "document":
            continue
        if file.get("id", "") == "":
            continue

        docs.append(file.get("id"))

    return list({doc for doc in docs if doc is not None})
