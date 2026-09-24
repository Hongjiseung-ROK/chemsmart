"""
User configuration management for CHEMSMART computational chemistry software.

This module provides comprehensive user
settings management including configuration
file handling, directory structure management,
and access to user-specific settings
for computational chemistry software
(Gaussian, ORCA) and server configurations.
Manages the ~/.chemsmart user configuration directory and associated files.

Classes:
    CHEMSMARTUserSettings: Main class for user configuration management

Dependencies:
    - chemsmart.io.yaml: YAML file handling utilities

Configuration Structure:
    ~/.chemsmart/
    ├── usersettings.yaml
    ├── server/
    │   └── server.yaml
    ├── gaussian/
    │   └── aussian_project_settings.yaml
    └── orca/
        └── orca_project_settings.yaml
"""

import glob
import logging
import os

from chemsmart.io.yaml import YAMLFile

logger = logging.getLogger(__name__)


class CHEMSMARTUserSettings:
    """
    User configuration settings manager for CHEMSMART.

    Manages user-specific configuration files, directories, and settings for
    computational chemistry software. Provides access to configuration paths,
    environment variables, and user-defined project settings.

    Every path and value is resolved when it is read, never when an instance
    is made: six modules hold an instance made at import, and a directory
    bound then was fixed before any caller -- a test's HOME fence included --
    could say which home is meant (R10 Q25).

    Attributes:
        USER_YAML_FILE (str): Name of the main user settings YAML file.
        yaml (str): Full path to the user settings YAML file.
        config_dir (str): User configuration directory path.
        data (dict): The user settings YAML's contents, read at each access.
    """

    USER_YAML_FILE = "usersettings.yaml"

    @classmethod
    def resolve_config_dir(cls):
        """The user configuration directory, resolved at this call:
        ``CHEMSMART_CONFIG_DIR`` when it is set, else ``~/.chemsmart`` of
        the home this process has now."""
        return os.path.expanduser(
            os.environ.get("CHEMSMART_CONFIG_DIR", "~/.chemsmart")
        )

    def __init__(self):
        """A view of the user's settings; nothing is read until it is used."""
        # Values assigned to ``data``, each held for the settings file it
        # was assigned under.
        self._assigned_data = {}

    @property
    def config_dir(self):
        """The user configuration directory, resolved at this access."""
        return self.resolve_config_dir()

    @property
    def yaml(self):
        """Path to the user settings YAML file, resolved at this access."""
        return os.path.join(self.config_dir, self.USER_YAML_FILE)

    @property
    def data(self):
        """The user settings YAML's contents ({} when there is no file)."""
        yaml_path = self.yaml
        if yaml_path in self._assigned_data:
            return self._assigned_data[yaml_path]
        try:
            return YAMLFile(filename=yaml_path).yaml_contents_dict
        except FileNotFoundError:
            return {}

    @data.setter
    def data(self, value):
        # An assignment holds for the settings file it was made under, so a
        # value supplied for one configuration never answers for another.
        self._assigned_data[self.yaml] = value

    @property
    def user_server_dir(self):
        """
        Get the user server configurations directory.

        Returns:
            str: Path to the directory containing user server configurations.
        """
        return os.path.join(self.config_dir, "server")

    @property
    def user_gaussian_settings_dir(self):
        """
        Get the user Gaussian settings directory.

        Returns:
            str: Path to the directory containing Gaussian-specific settings.
        """
        return os.path.join(self.config_dir, "gaussian")

    @property
    def user_gaussian_envars(self):
        """
        Get the path to Gaussian environment variables file.

        Returns:
            str: Path to the file containing Gaussian environment variables.
        """
        return os.path.join(self.user_gaussian_settings_dir, "gaussian.envars")

    @property
    def user_gaussian_modules(self):
        """
        Get the path to Gaussian modules file.

        Returns:
            str: Path to the file containing Gaussian module loading commands.
        """
        return os.path.join(
            self.user_gaussian_settings_dir, "gaussian.modules"
        )

    @property
    def user_gaussian_script(self):
        """
        Get the path to Gaussian execution script.

        Returns:
            str: Path to the Gaussian execution script file.
        """
        return os.path.join(self.user_gaussian_settings_dir, "gaussian.sh")

    @property
    def user_orca_envars(self):
        """
        Get the path to ORCA environment variables file.

        Returns:
            str: Path to the file containing ORCA environment variables.
        """
        return os.path.join(self.user_orca_settings_dir, "orca.envars")

    @property
    def user_orca_modules(self):
        """
        Get the path to ORCA modules file.

        Returns:
            str: Path to the file containing ORCA module loading commands.
        """
        return os.path.join(self.user_orca_settings_dir, "orca.modules")

    @property
    def user_orca_script(self):
        """
        Get the path to ORCA execution script.

        Returns:
            str: Path to the ORCA execution script file.
        """
        return os.path.join(self.user_orca_settings_dir, "orca.sh")

    @property
    def user_orca_settings_dir(self):
        """
        Get the user ORCA settings directory.

        Returns:
            str: Path to the directory containing ORCA-specific settings.
        """
        return os.path.join(self.config_dir, "orca")

    @property
    def user_pyscf_settings_dir(self):
        """
        Get the user PySCF settings directory.

        Returns:
            str: Path to the directory containing PySCF-specific settings.
        """
        return os.path.join(self.config_dir, "pyscf")

    @property
    def user_xtb_settings_dir(self):
        """Directory containing user xTB project YAML files."""

        return os.path.join(self.config_dir, "xtb")

    @property
    def server_yaml_files(self):
        """
        Get list of server YAML configuration files.

        Returns:
            list: List of paths to server configuration YAML files.
        """
        return glob.glob(os.path.join(self.user_server_dir, "*.yaml"))

    @property
    def gaussian_project_yaml_files(self):
        """
        Get list of Gaussian project YAML configuration files.

        Returns:
            list: List of paths to Gaussian project configuration YAML files.
        """
        return glob.glob(
            os.path.join(self.user_gaussian_settings_dir, "*.yaml")
        )

    @property
    def orca_project_yaml_files(self):
        """
        Get list of ORCA project YAML configuration files.

        Returns:
            list: List of paths to ORCA project configuration YAML files.
        """
        return glob.glob(os.path.join(self.user_orca_settings_dir, "*.yaml"))

    @property
    def pyscf_project_yaml_files(self):
        """
        Get list of PySCF project YAML configuration files.

        Returns:
            list: List of paths to PySCF project configuration YAML files.
        """
        return glob.glob(os.path.join(self.user_pyscf_settings_dir, "*.yaml"))

    @property
    def xtb_project_yaml_files(self):
        """Return user xTB project YAML files."""

        return glob.glob(os.path.join(self.user_xtb_settings_dir, "*.yaml"))

    @property
    def scratch(self):
        """
        Get scratch directory configuration.

        Returns:
            str or None: Path to scratch directory or None if not configured.
        """
        return self.data.get("SCRATCH", None)

    @property
    def email(self):
        """
        Get user email configuration.

        Returns:
            str or None: User email address or None if not configured.
        """
        return self.data.get("EMAIL", None)

    @property
    def project(self):
        """
        Get default project configuration.

        Returns:
            str or None: Default project name or None if not configured.
        """
        return self.data.get("PROJECT", None)

    @property
    def all_available_servers(self):
        """
        Get list of all available server configurations.

        Returns:
            list: List of server names (without .yaml extension) available
                  in the user server directory.
        """
        return [
            os.path.basename(s).removesuffix(".yaml")
            for s in self.server_yaml_files
        ]

    @property
    def all_available_gaussian_projects(self):
        """
        Get list of all available Gaussian project configurations.

        Returns:
            list: List of Gaussian project names (without .yaml extension)
                  available in the user Gaussian settings directory.
        """
        gaussian_project_settings = [
            os.path.basename(g).removesuffix(".yaml")  # python 3.9+
            # os.path.basename(g).strip(".yaml") does not work since
            # m062x.yaml gets stripped to 062x
            for g in self.gaussian_project_yaml_files
        ]
        return gaussian_project_settings

    @property
    def all_available_orca_projects(self):
        """
        Get list of all available ORCA project configurations.

        Returns:
            list: List of ORCA project names (without .yaml extension)
                  available in the user ORCA settings directory.
        """
        return [
            os.path.basename(o).removesuffix(".yaml")
            for o in self.orca_project_yaml_files
        ]

    @property
    def all_available_pyscf_projects(self):
        """
        Get list of all available PySCF project configurations.

        Returns:
            list: List of PySCF project names (without .yaml extension)
                  available in the user PySCF settings directory.
        """
        return [
            os.path.basename(p).removesuffix(".yaml")
            for p in self.pyscf_project_yaml_files
        ]

    @property
    def all_available_xtb_projects(self):
        """Return user xTB project names without their YAML suffix."""

        return [
            os.path.basename(path).removesuffix(".yaml")
            for path in self.xtb_project_yaml_files
        ]
