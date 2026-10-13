"""
Application logic tier — plugin registry.

Discovers every ServicePlugin subclass in data_access/plugins at import
time, so adding a service means dropping a file into that package. No
registration list is edited and no other tier changes.

This runtime discovery is the mechanism behind the project's extensibility
claim: the logic tier holds a collection of ServicePlugin objects and never
names a concrete service.
"""

import importlib
import inspect
import pkgutil

from ..data_access import plugins as plugins_package
from ..data_access.plugins.base import ServiceKind, ServicePlugin

# Modules in the plugins package that are infrastructure, not services.
_SKIP = {"base", "fixture_source"}


class PluginRegistry:
    """Holds the available plugins and selects among them."""

    def __init__(self) -> None:
        self._plugins: dict[str, ServicePlugin] = {}

    def discover(self) -> None:
        """Import every plugin module and instantiate what it defines."""
        for module_info in pkgutil.iter_modules(plugins_package.__path__):
            if module_info.name in _SKIP:
                continue

            module = importlib.import_module(
                f"{plugins_package.__name__}.{module_info.name}"
            )

            for _, candidate in inspect.getmembers(module, inspect.isclass):
                is_plugin = (
                    issubclass(candidate, ServicePlugin)
                    and candidate is not ServicePlugin
                    and not inspect.isabstract(candidate)
                    and candidate.__module__ == module.__name__
                )
                if is_plugin:
                    instance = candidate()
                    instance.connect()
                    self._plugins[instance.name] = instance

    def all_plugins(self) -> list[ServicePlugin]:
        """Every registered plugin, ordered by name for stable output."""
        return [self._plugins[name] for name in sorted(self._plugins)]

    def by_name(self, name: str) -> ServicePlugin | None:
        return self._plugins.get(name)

    def by_kinds(self, kinds: set[ServiceKind]) -> list[ServicePlugin]:
        """Plugins whose service category is in the requested set.

        An empty set means no filter, so every plugin is returned.
        """
        if not kinds:
            return self.all_plugins()
        return [p for p in self.all_plugins() if p.kind in kinds]


# One shared registry, populated on first import.
registry = PluginRegistry()
registry.discover()
