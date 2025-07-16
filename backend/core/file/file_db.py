from core.tracking.client import FileTrackingPayload, argo_tracking
from database.db import session_scope
from models.file import File


class FileDB:
    @staticmethod
    def create_new_file(user_id: str, file_id: str, file_name: str, file_size: int = 0):
        with session_scope() as session:
            file = File(
                user_id=user_id,
                file_id=file_id,
                file_name=file_name,
                file_size=file_size,
            )
            session.add(file)

            argo_tracking(FileTrackingPayload())

    @staticmethod
    def get_file_list():
        with session_scope() as session:
            files = session.query(File).all()
            return files

    @staticmethod
    def get_file_by_id(file_id: str):
        with session_scope() as session:
            file = session.query(File).filter(File.file_id == file_id).one_or_none()
            return file

    @staticmethod
    def delete_file(file_id: str):
        with session_scope() as session:
            file = session.query(File).filter(File.file_id == file_id).one_or_none()
            if file:
                session.delete(file)

    @staticmethod
    def update_file_name(user_id: str, file_id: str, file_name: str, file_size: int = 0):
        with session_scope() as session:
            file = session.query(File).filter_by(user_id=user_id, file_id=file_id).one_or_none()
            if file:
                file.file_name = file_name
                if file_size:
                    file.file_size = file_size
