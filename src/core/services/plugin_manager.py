import importlib
import inspect
import pkgutil
from typing import Dict, Any, Type

from ...core.ports.asset_ports import IAssetFormatPort
from ...core.ports.compute_ports import IComputeDriverPort
from ...core.ports.persistence_ports import IPersistencePort
from ...core.ports.data_fetcher_ports import IDataFetcherPlugin


class PluginManager:
	"""Simple plugin manager that discovers plugins inside `plugins` package
	and registers implementations for known ports.
	"""

	def __init__(self):
		self.formatters: Dict[str, Type[IAssetFormatPort]] = {}
		self.compute_drivers: Dict[str, Type[IComputeDriverPort]] = {}
		self.persistence_plugins: Dict[str, Type[IPersistencePort]] = {}
		self.data_fetchers: Dict[str, Type[IDataFetcherPlugin]] = {}

	def discover(self, package_name: str = "plugins"):
		# iterate subpackages/modules in plugins/
		try:
			package = importlib.import_module(package_name)
		except Exception:
			return

		prefix = package.__name__ + "."
		for finder, name, ispkg in pkgutil.iter_modules(package.__path__, prefix):
			try:
				module = importlib.import_module(name)
			except Exception:
				continue

			for _, obj in inspect.getmembers(module, inspect.isclass):
				# Check formatters
				if issubclass(obj, IAssetFormatPort) and obj is not IAssetFormatPort:
					key = getattr(obj, "NAME", obj.__name__)
					self.formatters[key] = obj

				if issubclass(obj, IComputeDriverPort) and obj is not IComputeDriverPort:
					key = getattr(obj, "NAME", obj.__name__)
					self.compute_drivers[key] = obj

				if issubclass(obj, IPersistencePort) and obj is not IPersistencePort:
					key = getattr(obj, "NAME", obj.__name__)
					self.persistence_plugins[key] = obj
				
				# Check data fetcher plugins
				if issubclass(obj, IDataFetcherPlugin) and obj is not IDataFetcherPlugin:
					key = getattr(obj, "NAME", obj.__name__)
					self.data_fetchers[key] = obj

	def register_formatter(self, name: str, cls: Type[IAssetFormatPort]):
		self.formatters[name] = cls

	def register_compute(self, name: str, cls: Type[IComputeDriverPort]):
		self.compute_drivers[name] = cls

	def register_persistence(self, name: str, cls: Type[IPersistencePort]):
		self.persistence_plugins[name] = cls
	
	def register_data_fetcher(self, name: str, cls: Type[IDataFetcherPlugin]):
		self.data_fetchers[name] = cls

	def get_persistence(self, name: str):
		return self.persistence_plugins.get(name)

	def get_formatter(self, name: str):
		return self.formatters.get(name)

	def get_compute(self, name: str):
		return self.compute_drivers.get(name)
	
	def get_data_fetcher(self, name: str):
		"""Get a data fetcher plugin by name."""
		plugin_class = self.data_fetchers.get(name)
		if plugin_class:
			return plugin_class()
		return None
	
	def list_data_fetchers(self) -> Dict[str, Dict[str, Any]]:
		"""List all available data fetcher plugins with their methods."""
		fetchers_info = {}
		
		for name, plugin_class in self.data_fetchers.items():
			try:
				plugin_instance = plugin_class()
				fetchers_info[name] = {
					"name": name,
					"class": plugin_class.__name__,
					"methods": plugin_instance.get_available_methods()
				}
			except Exception as e:
				fetchers_info[name] = {
					"name": name,
					"class": plugin_class.__name__,
					"error": f"Failed to instantiate: {e}",
					"methods": {}
				}
		
		return fetchers_info

