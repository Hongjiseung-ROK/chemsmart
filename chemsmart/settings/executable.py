import logging
import os.path
import platform
import re
import shutil
import sys
from typing import Optional

from chemsmart.io.yaml import YAMLFile
from chemsmart.settings.user import CHEMSMARTUserSettings
from chemsmart.utils.mixins import RegistryMixin
from chemsmart.utils.utils import strip_out_comments

user_settings = CHEMSMARTUserSettings()

logger = logging.getLogger(__name__)

#: The references a declared value may make to another variable: ``$NAME``,
#: ``${NAME}`` and ``${NAME:-default}``.  Nothing else a shell can do is
#: interpreted; a command substitution stays the text it was written as.
_REFERENCE = re.compile(r"\$(?:(\w+)|\{(\w+)(?::-([^}]*))?\})")


def _resolve_declared_value(raw, known):
    """One declared value as a shell would hand it to a process.

    A single-quoted value is taken as written.  Otherwise surrounding double
    quotes are dropped, each reference is replaced from ``known`` (an unset
    name is empty, or its ``:-`` default, as it is in a shell), and a leading
    ``~`` is expanded.
    """

    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1]

    def replace(match):
        name = match.group(1) or match.group(2)
        found = known.get(name)
        if found:
            return str(found)
        return match.group(3) or ""

    return os.path.expanduser(_REFERENCE.sub(replace, value))


class Executable(RegistryMixin):
    """
    Abstract base class for obtaining program
    executable paths and configurations.

    This class provides a framework for managing executable configurations for
    different computational chemistry programs. It reads configuration from
    server YAML files and handles environment
    setup including conda environments,
    modules, scripts, and environment variables.
    """

    PROGRAM: Optional[str] = None
    EXEFOLDER_REQUIRED = True
    #: The companion binary a program starts its own parallel ranks with, if
    #: it has one. ChemSmart never launches it; the program does, from the
    #: search path it is given.
    PARALLEL_LAUNCHER: Optional[str] = None

    def __init__(
        self,
        executable_folder=None,
        local_run=False,
        conda_env=None,
        modules=None,
        scripts=None,
        envars=None,
    ):
        """
        Initialize the Executable instance.

        Args:
            executable_folder (str, optional): Path to executable directory.
            local_run (bool): Whether to run locally. Defaults to False.
            conda_env (str, optional): Conda environment configuration.
            modules (str, optional): Module loading commands.
            scripts (str, optional): Additional script commands.
            envars (str, optional): Environment variable export commands.
        """
        self.executable_folder = executable_folder
        self.local_run = local_run
        self.conda_env = conda_env
        self.modules = modules
        self.scripts = scripts
        self.envars = envars

    @classmethod
    def from_servername(cls, servername):
        """
        Create an Executable instance from server configuration file.

        Reads configuration from a YAML file in the user's server directory
        and creates an instance with the appropriate settings for the specified
        computational chemistry program.

        Args:
            servername (str): Name of the server configuration file (with or
                            without .yaml extension).

        Returns:
            Executable: An instance configured with server-specific settings.
        """
        # Ensure .yaml extension is present
        if servername.endswith(".yaml"):
            server_yaml = servername
        else:
            server_yaml = f"{servername}.yaml"
        # Load server configuration from YAML file
        server_yaml_file = os.path.join(
            user_settings.user_server_dir, server_yaml
        )
        server_yaml = YAMLFile(filename=server_yaml_file)

        # Extract configuration for the specific program.
        # EXEFOLDER is optional: a library backend such as PySCF has no
        # executable folder, and its subclass resolves an interpreter
        # instead. Every sibling key already uses .get().
        program_config = server_yaml.yaml_contents_dict[cls.PROGRAM]
        if cls.EXEFOLDER_REQUIRED:
            executable_folder = program_config["EXEFOLDER"]
        else:
            executable_folder = program_config.get("EXEFOLDER")
        if executable_folder is not None:
            executable_folder = os.path.expanduser(executable_folder)
        local_run = server_yaml.yaml_contents_dict[cls.PROGRAM].get(
            "LOCAL_RUN", False
        )
        conda_env = server_yaml.yaml_contents_dict[cls.PROGRAM].get(
            "CONDA_ENV", None
        )
        modules = server_yaml.yaml_contents_dict[cls.PROGRAM].get(
            "MODULES", None
        )
        scripts = server_yaml.yaml_contents_dict[cls.PROGRAM].get(
            "SCRIPTS", None
        )
        envars = server_yaml.yaml_contents_dict[cls.PROGRAM].get(
            "ENVARS", None
        )

        # Strip comments from configuration strings
        if conda_env is not None:
            conda_env = strip_out_comments(conda_env)
        if modules is not None:
            modules = strip_out_comments(modules)
        if scripts is not None:
            scripts = strip_out_comments(scripts)
        if envars is not None:
            envars = strip_out_comments(envars)
        return cls(
            executable_folder=executable_folder,
            local_run=local_run,
            conda_env=conda_env,
            modules=modules,
            scripts=scripts,
            envars=envars,
        )

    @classmethod
    def program_scratch_from_servername(cls, servername):
        """Return program-block ``SCRATCH`` from server YAML, or None if unset.

        Reads the boolean ``SCRATCH`` key under this executable's program
        block (for example ``GAUSSIAN`` or ``ORCA``). Used by
        ``JobRunner.from_job`` when the CLI omits ``--scratch`` /
        ``--no-scratch``: an explicit YAML ``True``/``False`` overrides the
        job-runner class default; a missing key or ``null`` value leaves the
        class default in place.

        Args:
            servername (str): Server config name, or path to a ``.yaml`` file.

        Returns:
            bool or None: YAML ``SCRATCH`` value, or None if missing, null,
            or unreadable.
        """
        if cls.PROGRAM is None or not servername:
            return None

        servername = str(servername)
        if os.path.isfile(servername):
            server_yaml_file = servername
        else:
            server_yaml = (
                servername
                if servername.endswith(".yaml")
                else f"{servername}.yaml"
            )
            server_yaml_file = os.path.join(
                user_settings.user_server_dir, server_yaml
            )
        try:
            contents = YAMLFile(filename=server_yaml_file).yaml_contents_dict
            program_cfg = contents.get(cls.PROGRAM)
            if not program_cfg or "SCRATCH" not in program_cfg:
                return None
            value = program_cfg["SCRATCH"]
            if value is None:
                return None
            return bool(value)
        except (FileNotFoundError, OSError, TypeError, ValueError) as e:
            logger.debug(
                f"Could not read {cls.PROGRAM} SCRATCH from "
                f"{server_yaml_file}: {e}"
            )
            return None

    @property
    def available_servers(self):
        """
        Get list of available server configurations.

        Returns:
            list: List of available server configuration names.
        """
        return user_settings.all_available_servers

    @property
    def scratch_dir(self):
        """
        The scratch directory this program's ``ENVARS`` declare.

        Read through the same parser a process is given, so ``SCRATCH`` is
        the variable of that name and its value is resolved.

        Returns:
            str or None: Path to scratch directory if defined, None otherwise.
        """
        return self.resolved_env().get("SCRATCH") or None

    @property
    def env(self):
        """
        The ``export`` lines of ``ENVARS``, exactly as they were written.

        This is the rendering a job script needs: the compute node's shell
        expands ``$PATH`` when the job starts, so expanding it here would
        freeze the submitting host's value into a script that runs somewhere
        else.  A process needs :meth:`resolved_env` instead.

        Returns:
            dict or None: Declared names to their written values, in
                         declaration order, if envars is set; None otherwise.
        """
        if self.envars is not None:
            env = {}
            for line in self.envars.split("\n"):
                line = line.split("#")[0].strip()  # Remove comments
                if line.startswith("export "):
                    key, _, value = line[7:].partition("=")
                    if key.strip():
                        env[key.strip()] = value
            return env
        return None

    def resolved_env(self, base=None):
        """
        The declared variables as a process must receive them.

        No shell stands between ``subprocess`` and the engine, so nothing
        expands ``export PATH=/opt/openmpi/bin:$PATH`` unless this does; the
        engine would start with the literal text and ORCA would not find
        ``mpirun``.  Lines are resolved in declaration order against ``base``
        (the inherited environment by default) and against the lines before
        them, which is what a shell reading the block would do.

        Args:
            base (Mapping, optional): The environment the process inherits.

        Returns:
            dict: Declared names to their resolved values; empty if none.
        """
        known = dict(os.environ if base is None else base)
        resolved = {}
        for key, raw in (self.env or {}).items():
            known[key] = resolved[key] = _resolve_declared_value(raw, known)
        return resolved

    def resolve_in_program_path(self, name, base=None):
        """
        Locate a companion binary where this program's engine will look.

        That is the search path the program's own ``ENVARS`` build on top of
        the inherited one -- not the controller's, which is what a bare
        ``shutil.which`` would ask and which can differ in exactly the
        directory that matters. Nothing is launched.

        Args:
            name (str): The binary's name, e.g. ``mpirun``.
            base (Mapping, optional): The environment the engine inherits.

        Returns:
            str: The resolved path, or an empty string when it is not found.
        """
        inherited = os.environ if base is None else base
        search_path = self.resolved_env(inherited).get(
            "PATH", inherited.get("PATH", "")
        )
        return shutil.which(name, path=search_path) or ""


class GaussianExecutable(Executable):
    """
    Executable handler for Gaussian quantum chemistry software.

    This class provides specific implementation for managing Gaussian 16
    executable paths and configurations.
    """

    PROGRAM = "GAUSSIAN"

    def __init__(self, executable_folder=None, **kwargs):
        """
        Initialize GaussianExecutable instance.

        Args:
            executable_folder (str, optional):
            Path to Gaussian executable directory.
            **kwargs: Additional arguments passed to parent Executable class.
        """
        super().__init__(executable_folder=executable_folder, **kwargs)

    def get_executable(self):
        """
        Get the full path to the Gaussian executable.

        Returns:
            str or None: Full path to g16
            executable if executable_folder is set,
                        None otherwise.
        """
        if self.executable_folder is not None:
            executable_path = os.path.join(self.executable_folder, "g16")
            return executable_path


class ORCAExecutable(Executable):
    """
    Executable handler for ORCA quantum chemistry software.

    This class provides specific implementation for managing ORCA
    executable paths and configurations.
    """

    PROGRAM = "ORCA"
    PARALLEL_LAUNCHER = "mpirun"

    def __init__(self, executable_folder=None, **kwargs):
        """
        Initialize ORCAExecutable instance.

        Args:
            executable_folder (str, optional):
            Path to ORCA executable directory.
            **kwargs: Additional arguments passed to parent Executable class.
        """
        super().__init__(executable_folder=executable_folder, **kwargs)

    def get_executable(self):
        """
        Get the full path to the ORCA executable.

        Returns:
            str or None: Full path to orca
            executable if executable_folder is set,
                        None otherwise.
        """
        if self.executable_folder is not None:
            executable_path = os.path.join(self.executable_folder, "orca")
            return executable_path


class NCIPLOTExecutable(Executable):
    """
    Executable handler for NCIPLOT non-covalent interaction analysis software.

    This class provides specific implementation for managing NCIPLOT
    executable paths and configurations.
    """

    PROGRAM = "NCIPLOT"

    def __init__(self, executable_folder=None, **kwargs):
        """
        Initialize NCIPLOTExecutable instance.

        Args:
            executable_folder (str, optional):
            Path to NCIPLOT executable directory.
            **kwargs: Additional arguments passed to parent Executable class.
        """
        super().__init__(executable_folder=executable_folder, **kwargs)

    def get_executable(self):
        """
        Get the full path to the NCIPLOT executable.

        Returns:
            str or None: Full path to nciplot
            executable if executable_folder is set,
                        None otherwise.
        """
        if self.executable_folder is not None:
            executable_path = os.path.join(self.executable_folder, "nciplot")
            return executable_path


class PySCFExecutable(Executable):
    """
    Executable handler for the PySCF library backend.

    PySCF is a Python library, not a binary, so the "executable" is the
    interpreter that owns it. ``EXEFOLDER`` is therefore optional and, when
    present, names the ``bin/`` of the environment PySCF is installed in --
    exactly as ``XTB: EXEFOLDER: /path/to/environment/bin`` already does.
    That is what lets a GPU4PySCF job run in a CUDA environment while ChemSmart
    stays in its own, whose numpy is pinned to 1.x by rdkit and pymol.

    The program block is still needed for ``CONDA_ENV``, ``MODULES``,
    ``ENVARS`` and ``SCRATCH``.
    """

    PROGRAM = "PYSCF"
    EXEFOLDER_REQUIRED = False

    @classmethod
    def from_servername(cls, servername):
        """Return the PySCF executable configuration for ``servername``.

        Unlike a binary backend, PySCF needs no server configuration at all:
        with no ``PYSCF:`` block it runs in ChemSmart's own interpreter,
        which is correct whenever PySCF shares that environment. Requiring a
        block would break every existing server YAML the first time someone
        ran a PySCF job, for no information we do not already have.

        A block is still read when present, and is the way to point a job at
        a different environment -- a CUDA one for GPU4PySCF, for instance.
        """
        try:
            return super().from_servername(servername)
        except KeyError:
            logger.debug(
                f"No PYSCF block in server '{servername}'; using the running "
                f"interpreter {sys.executable}."
            )
            return cls(executable_folder=None, local_run=True)

    def __init__(self, executable_folder=None, **kwargs):
        """
        Initialize PySCFExecutable instance.

        Args:
            executable_folder (str, optional): Path to the ``bin/`` directory
                of the Python environment that has PySCF installed.
            **kwargs: Additional arguments passed to parent Executable class.
        """
        super().__init__(executable_folder=executable_folder, **kwargs)

    def get_executable(self):
        """
        Get the Python interpreter used to run PySCF jobs.

        Returns:
            str: Path to the interpreter. Falls back to the interpreter
                running ChemSmart when ``EXEFOLDER`` is not configured, which
                is correct whenever PySCF shares ChemSmart's environment.
        """
        if self.executable_folder is not None:
            interpreter = (
                "python.exe" if platform.system() == "Windows" else "python"
            )
            return os.path.join(self.executable_folder, interpreter)
        return sys.executable


class XTBExecutable(Executable):
    """Resolve the external xTB binary without inferring readiness.

    An explicit ``EXEFOLDER`` is authoritative and therefore fails closed if
    it does not contain ``xtb``.  With no XTB server block, local execution may
    discover ``xtb`` on ``PATH``; the runner still performs its own preflight.
    """

    PROGRAM = "XTB"
    EXEFOLDER_REQUIRED = False

    @classmethod
    def from_servername(cls, servername):
        try:
            return super().from_servername(servername)
        except KeyError:
            logger.debug(
                "No XTB block in server %r; resolving the binary from PATH.",
                servername,
            )
            return cls(executable_folder=None, local_run=True)

    def get_executable(self):
        executable_name = (
            "xtb.exe" if platform.system() == "Windows" else "xtb"
        )
        if self.executable_folder is not None:
            candidate = os.path.join(self.executable_folder, executable_name)
            if not (
                os.path.isfile(candidate) and os.access(candidate, os.X_OK)
            ):
                raise FileNotFoundError(
                    "Configured xTB executable is missing or not executable: "
                    f"{candidate}"
                )
            return candidate
        candidate = shutil.which(executable_name)
        if candidate is None:
            raise FileNotFoundError(
                "xTB executable was not configured and is not available on "
                "PATH."
            )
        return candidate
