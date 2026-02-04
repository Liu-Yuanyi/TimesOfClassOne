from dataclasses import dataclass, field
from typing import Dict, Optional, List

class baseMode:

    def __init__(self, name: str):
        self.name = name

    def get_player_count(self) -> int:
        raise NotImplementedError

    def check_victory(self, game_state: Dict) -> Optional[str]:
        raise NotImplementedError