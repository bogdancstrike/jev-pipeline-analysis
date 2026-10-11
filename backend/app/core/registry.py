"""Which modules exist, in what order they can run, and which ones a job needs."""
from collections.abc import Iterable

from .errors import InvalidInput
from .modules import Module


class ModuleRegistry:
    def __init__(self, modules: Iterable[Module]):
        self._by_name: dict[str, Module] = {}
        for m in modules:
            if m.name in self._by_name:
                raise ValueError(f"duplicate module name {m.name!r}")
            self._by_name[m.name] = m
        for m in self._by_name.values():
            missing = [r for r in m.requires if r not in self._by_name]
            if missing:
                raise ValueError(f"module {m.name!r} requires {missing}, which are not enabled")
        self.order = self._toposort()

    def _toposort(self) -> list[Module]:
        out: list[Module] = []
        state: dict[str, int] = {}  # 1 = visiting, 2 = done

        def visit(name: str, path: tuple[str, ...]) -> None:
            if state.get(name) == 2:
                return
            if state.get(name) == 1:
                raise ValueError(f"module dependency cycle: {' -> '.join(path + (name,))}")
            state[name] = 1
            for dep in self._by_name[name].requires:
                visit(dep, path + (name,))
            state[name] = 2
            out.append(self._by_name[name])

        for name in self._by_name:  # registration order, so the UI order is stable
            visit(name, ())
        return out

    def __iter__(self):
        return iter(self.order)

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def get(self, name: str) -> Module:
        return self._by_name[name]

    def defaults(self) -> list[str]:
        return [m.name for m in self.order if m.describe()["default_on"]]

    def closure(self, names: Iterable[str]) -> list[Module]:
        """The requested modules plus everything they depend on, in runnable order."""
        wanted: set[str] = set()
        unknown = [n for n in names if n not in self._by_name]
        if unknown:
            raise InvalidInput(f"unknown module(s): {', '.join(unknown)}",
                               details={"available": [m.name for m in self.order]})
        stack = list(names)
        while stack:
            n = stack.pop()
            if n not in wanted:
                wanted.add(n)
                stack.extend(self._by_name[n].requires)
        return [m for m in self.order if m.name in wanted]
