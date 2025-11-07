
from dataclasses import dataclass

@dataclass
class EndpointAppeared:
    path: str

@dataclass
class EndpointVanished:
    pass

@dataclass
class ConnectedToKiCad:
    project_info: dict

@dataclass
class DisconnectedFromKiCad:
    pass

@dataclass
class RemoteUpdatesFound:
    repo: str
    repo_status: "RepoStatus"  # forward ref

@dataclass
class LocalChangesFound:
    repo: str
    details: dict

@dataclass
class NewLibraryDiscovered:
    folder: str

@dataclass
class FreezeToggled:
    is_frozen: bool

