import requests

from core.file.file_obj import FileTransferMethod, FileType, FileVar


class MessageFileParser:
    def __init__(self, workspace_id: str, bot_id: str) -> None:
        self.workspace_id = workspace_id
        self.bot_id = bot_id

    def validate_and_transform_files_arg(self, files: list[dict]) -> list[FileVar]:
        """
        validate and transform files arg

        :param files:
        :return:
        """
        for file in files:
            if not isinstance(file, dict):
                raise ValueError("Invalid file format, must be dict")
            if not file.get("type"):
                raise ValueError("Missing file type")
            FileType.value_of(file.get("type"))
            if not file.get("transfer_method"):
                file["transfer_method"] = FileTransferMethod.LOCAL_FILE.value
            FileTransferMethod.value_of(file.get("transfer_method"))
            if file.get("transfer_method") == FileTransferMethod.REMOTE_URL.value:
                if not file.get("url"):
                    raise ValueError("Missing file url")
                if not file.get("url", "").startswith("http"):
                    raise ValueError("Invalid file url")
            if file.get("transfer_method") == FileTransferMethod.LOCAL_FILE.value and not file.get("id"):
                raise ValueError("Missing file upload_file_id")

        # transform files to file objs
        type_file_objs = self._to_file_objs(files)

        # validate files
        new_files = []
        for file_type, file_objs in type_file_objs.items():
            for file_obj in file_objs:
                if file_obj.transfer_method == FileTransferMethod.REMOTE_URL:
                    # check remote url valid and is image
                    result, error = self._check_image_remote_url(file_obj.url)
                    if result is False:
                        raise ValueError(error)
                elif file_obj.transfer_method == FileTransferMethod.LOCAL_FILE:
                    if not file_obj.related_id:
                        raise ValueError("Invalid upload file")

                new_files.append(file_obj)

        # return all file objs
        return new_files

    def transform_message_files(self, files: list[dict]) -> list[FileVar]:
        """
        transform message files

        :param files:
        :return:
        """
        # transform files to file objs
        type_file_objs = self._to_file_objs(files)

        # return all file objs
        return [file_obj for file_objs in type_file_objs.values() for file_obj in file_objs]

    def _to_file_objs(self, files: list[dict]) -> dict[FileType, list[FileVar]]:
        """
        transform files to file objs

        :param files:
        :return:
        """
        type_file_objs: dict[FileType, list[FileVar]] = {
            # Currently only support image
            FileType.IMAGE: [],
            FileType.DOCUMENT: [],
        }

        if not files:
            return type_file_objs

        # group by file type and convert file args or message files to FileObj
        for file in files:
            file_obj = self._to_file_obj(file)
            if file_obj.type not in type_file_objs:
                continue

            type_file_objs[file_obj.type].append(file_obj)

        return type_file_objs

    def _to_file_obj(self, file: dict) -> FileVar:
        """
        transform file to file obj

        :param file:
        :return:
        """
        transfer_method = FileTransferMethod.value_of(file.get("transfer_method"))
        return FileVar(
            workspace_id=self.workspace_id,
            type=FileType.value_of(file.get("type")),
            transfer_method=transfer_method,
            url=(file.get("url") if transfer_method == FileTransferMethod.REMOTE_URL else None),
            related_id=(file.get("id") if transfer_method == FileTransferMethod.LOCAL_FILE else None),
        )

    def _check_image_remote_url(self, url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) \
                Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.head(url, headers=headers, allow_redirects=True)
            if response.status_code == 200:
                return True, ""
            else:
                return False, "URL does not exist."
        except requests.RequestException as e:
            return False, f"Error checking URL: {e}"
