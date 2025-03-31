from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlretrieve


def download_file_from_google_drive(id, destination):
    import requests

    URL = "https://docs.google.com/uc"

    session = requests.Session()
    response = session.get(
        URL,
        params={
            "id": id,
            "confirm": "t",
            "export": "download",
        },
        stream=True,
    )
    token = get_confirm_token(response)

    if token:
        params = {"id": id, "confirm": token}
        response = session.get(URL, params=params, stream=True)

    save_response_content(response, destination)


def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value

    return None


def save_response_content(response, destination):
    CHUNK_SIZE = 32768

    with Path(destination).open("wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)


class AbstractRemoteFile:
    """
    AbstractRemoteFile provide infrastructure for RemoteFile where
    only the method fetch() needs to be defined for a concreate implementation.
    """

    def __init__(self, local_path=None, local_base=None):
        # setup base path
        self._base = Path.cwd().resolve()
        if local_base is not None:
            local_base = Path(local_base).resolve()
            self._base = local_base
            if local_base.exists() and local_base.is_file():
                self._base = local_base.parent

        # setup local path
        self._file_path = Path(local_path)
        if not self._file_path.is_absolute():
            self._file_path = self._base / local_path

        # Make sure target directory exists
        parent_dir = self._file_path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)

    @property
    def local(self):
        """Return true if the file is available locally on the File System"""
        return self._file_path.exists()

    def fetch(self):
        """Perform the action needed to fetch the content and store it locally"""

    @property
    def path(self):
        """Return the actual local file path"""
        if not self.local:
            self.fetch()

        return str(self._file_path)


class GoogleDriveFile(AbstractRemoteFile):
    """
    Helper file to manage caching and retrieving of file available on Google Drive
    """

    def __init__(
        self,
        local_path=None,
        google_id=None,
        local_base=None,
    ):
        """
        Provide the information regarding where the file should be located
        and where to fetch it if missing.

        :param local_path: relative or absolute path
        :param google_id: Resource ID from google
        :param local_base: Absolute path when local_path is relative
        """
        super().__init__(local_path, local_base)
        self._gid = google_id

    def fetch(self):
        try:
            print(f"Downloading:\n - {self._gid}\n - to {self._file_path}")  # noqa: T201
            download_file_from_google_drive(self._gid, self._file_path)
        except HTTPError as e:
            print(RuntimeError(f"Failed to download {self._gid}. {e.reason}"))  # noqa: T201


class HttpFile(AbstractRemoteFile):
    """
    Helper file to manage caching and retrieving of file available on HTTP servers
    """

    def __init__(
        self,
        local_path=None,
        remote_url=None,
        local_base=None,
    ):
        """
        Provide the information regarding where the file should be located
        and where to fetch it if missing.

        :param local_path: relative or absolute path
        :param remote_url: http(s):// url to fetch the file from
        :param local_base: Absolute path when local_path is relative
        """
        super().__init__(local_path, local_base)
        self._url = remote_url

    def fetch(self):
        try:
            print(f"Downloading:\n - {self._url}\n - to {self._file_path}")  # noqa: T201
            urlretrieve(self._url, str(self._file_path))
        except HTTPError as e:
            print(RuntimeError(f"Failed to download {self._url}. {e.reason}"))  # noqa: T201


__all__ = [
    "AbstractRemoteFile",
    "GoogleDriveFile",
    "HttpFile",
]
