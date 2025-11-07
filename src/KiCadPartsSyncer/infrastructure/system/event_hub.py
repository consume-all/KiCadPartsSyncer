
from collections import defaultdict
from typing import Callable, Type, Dict, List, Any

class EventHub:
    def __init__(self):
        self._subs: Dict[Type, List[Callable]] = defaultdict(list)

    def publish(self, evt: Any) -> None:
        for handler in list(self._subs[type(evt)]):
            handler(evt)

    def subscribe(self, evt_type: Type, handler: Callable):
        self._subs[evt_type].append(handler)
        return lambda: self._subs[evt_type].remove(handler)
