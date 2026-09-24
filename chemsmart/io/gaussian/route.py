import logging
import re

from chemsmart.io.gaussian import (
    GAUSSIAN_AB_INITIO,
    GAUSSIAN_ADDITIONAL_OPT_OPTIONS,
    GAUSSIAN_ADDITIONAL_ROUTE_PARAMETERS,
    GAUSSIAN_BASES,
    GAUSSIAN_DIEZE_TAGS,
    GAUSSIAN_FUNCTIONALS,
    GAUSSIAN_SEMIEMPIRICAL,
)
from chemsmart.io.gaussian import (
    GAUSSIAN_SOLVATION_MODELS as gaussian_solvation_models,
)

logger = logging.getLogger(__name__)


GAUSSIAN_EMPIRICAL_DISPERSIONS = frozenset({"pfd", "gd2", "gd3", "gd3bj"})

#: A response calculation's route keyword: ``TD``, ``TDA`` (Gaussian's
#: Tamm-Dancoff keyword, which takes the same options) or ``CIS``.
_GAUSSIAN_RESPONSE_KEYWORD = re.compile(
    r"(?<![a-z0-9_])(td|tda|cis)(?![a-z0-9_])"
)


#: The mixing guess, however the route spells it: ``guess=mix``,
#: ``guess=(mix)`` or ``guess=(mix,always)``.
_GAUSSIAN_GUESS_MIX = re.compile(
    r"(?<![a-z0-9_])guess\s*=\s*\(?[^\s)]*(?<![a-z0-9_])mix(?![a-z0-9_])"
)


#: The spin prefixes a Gaussian method word can carry, longest first.
_GAUSSIAN_SPIN_PREFIXES = ("ro", "u", "r")


def _gaussian_functional_spin_prefix(word):
    """The prefix the route parser strips from a functional word, or None.

    The rule ``get_functional_and_basis`` applies when it reads the
    functional back -- a prefix followed by a word that names a functional
    fragment -- so what is read as the prefix is exactly what the parser
    removed from the functional, one rule for both.
    """

    for prefix in _GAUSSIAN_SPIN_PREFIXES:
        if word.startswith(prefix) and any(
            fragment in word[len(prefix) :]
            for fragment in GAUSSIAN_FUNCTIONALS
        ):
            return prefix
    return None


def gaussian_method_spin_prefix(route_string):
    """The spin prefix (``u``, ``r``, ``ro``) the route's method carries.

    ``None`` when the method is written bare, which leaves the choice to
    Gaussian: restricted for a singlet, unrestricted for an open shell.
    A functional is read by the parser's own stripping rule; an ab initio
    method is a prefix followed by exactly one of Gaussian's method words,
    so ``ultrafine`` or ``readfc`` never looks like a prefix.
    """

    ab_initio = tuple(
        word for word in GAUSSIAN_AB_INITIO if word not in {"rhf", "uhf"}
    )
    for word in str(route_string).lower().split():
        head = word.split("/")[0].lstrip("#")
        if not head or "=" in head:
            continue
        if any(fragment in head for fragment in GAUSSIAN_FUNCTIONALS):
            prefix = _gaussian_functional_spin_prefix(head)
            if prefix is not None:
                return prefix
            continue
        for prefix in _GAUSSIAN_SPIN_PREFIXES:
            if head.startswith(prefix) and head[len(prefix) :] in ab_initio:
                return prefix
    return None


def gaussian_route_broken_symmetry(route_string):
    """Whether the route is the broken-symmetry request ChemSmart writes.

    An unrestricted method started from ``guess=mix``: the two together
    are what ``broken_symmetry: true`` is written as, so the route reads
    back to the request and a native spelling of the same two words is
    read as that request too -- the review then says what runs.
    """

    route = str(route_string).lower()
    return (
        gaussian_method_spin_prefix(route) == "u"
        and _GAUSSIAN_GUESS_MIX.search(route) is not None
    )


def route_requests_response(route_string):
    """Whether a Gaussian route asks for a response (TD/TDA/CIS) calculation.

    A route carrying one and no job keyword is a fixed-geometry response
    calculation, which the route-word chain alone calls ``sp``.  One
    function answers for a written input and for a completed log, so the
    preview and the result reader cannot classify one route two ways.
    """

    return bool(
        _GAUSSIAN_RESPONSE_KEYWORD.search(str(route_string or "").lower())
    )


def modredundant_rows_drive_a_scan(rows):
    """Whether ModRedundant rows drive a coordinate rather than hold one.

    ``opt=modredundant`` is written for a relaxed scan and for a
    constrained optimisation alike, so the rows decide: a scan row ends
    ``S <steps> <size>`` and a frozen row ends ``F``.  The test is
    positional, on a row's own trailing tokens, because the bare letter
    ``S`` is also an element symbol a row may carry.  An input writes the
    same grammar a log echoes after "The following ModRedundant input
    section has been read:", so one function reads both.
    """

    for line in rows or ():
        tokens = str(line).split()
        for index, token in enumerate(tokens):
            if token.upper() == "S" and len(tokens) - index >= 3:
                return True
    return False


def normalize_gaussian_dispersion(value):
    """Return the Gaussian-native empirical-dispersion value."""

    if value is None:
        return None
    literal = str(value).strip().lower()
    if literal.startswith("empiricaldispersion="):
        literal = literal.split("=", 1)[1].strip()
    aliases = {
        "d2": "gd2",
        "d3": "gd3",
        "d3zero": "gd3",
        "d3bj": "gd3bj",
    }
    literal = aliases.get(literal, literal)
    if not literal or not re.fullmatch(r"[a-z0-9_-]+", literal):
        raise ValueError(f"Invalid Gaussian dispersion literal: {value!r}")
    if literal not in GAUSSIAN_EMPIRICAL_DISPERSIONS:
        supported = ", ".join(sorted(GAUSSIAN_EMPIRICAL_DISPERSIONS))
        raise ValueError(
            f"Unsupported Gaussian dispersion {value!r}; supported: {supported}"
        )
    return literal


def split_gaussian_dispersion_tokens(route_text):
    """Remove route-level dispersion tokens and return their one meaning."""

    if route_text is None:
        return None, None
    original = str(route_text)
    retained = []
    observed = []
    for token in original.split():
        if token.lower().startswith("empiricaldispersion="):
            observed.append(normalize_gaussian_dispersion(token))
        else:
            retained.append(token)
    if not observed:
        return original, None
    if len(set(observed)) != 1:
        raise ValueError(
            "Conflicting Gaussian EmpiricalDispersion declarations: "
            + ", ".join(observed)
        )
    return " ".join(retained), observed[0]


def gaussian_frequency_token(route_text):
    """Return an explicit ``freq`` request written in a route parameter.

    The route-parameter channel is appended verbatim, so a keyword the
    project section already emits is written twice -- and Gaussian answers
    a route naming ``freq`` twice by running no frequency step and
    terminating normally.  Measured on this exact case (CUHK Slurm
    2142393): ``# opt freq b3lyp 6-31G* freq=hpmodes`` produced an FOpt
    archive with no ``Frequencies --`` line anywhere in the log, so a run
    asked for a Hessian returned none and neither program said so.

    The dispersion channel one function above already reconciles rather
    than appends; this answers the same question for the frequency
    keyword, and the caller writes the explicit spelling in place of the
    bare one.  ``None`` means the parameter names no frequency step, which
    is the ordinary case.
    """

    if route_text is None:
        return None
    observed = [
        token
        for token in str(route_text).split()
        if token.lower() == "freq" or token.lower().startswith("freq=")
    ]
    if not observed:
        return None
    if len({token.lower() for token in observed}) != 1:
        raise ValueError(
            "Conflicting Gaussian frequency declarations in the route "
            "parameters: " + ", ".join(observed)
        )
    return observed[0]


_FUNCTIONAL_SUFFIX_DISPERSION = (
    ("d3zero", "gd3"),
    ("d3bj", "gd3bj"),
    ("d3", "gd3"),
    ("d2", "gd2"),
)


def split_gaussian_functional_dispersion_shorthand(functional):
    """Split a common ``functional-Dn`` shorthand into native settings."""

    if functional is None:
        return None, None
    layers = str(functional).split(":")
    for layer in layers[1:]:
        lowered_layer = layer.lower()
        if any(
            lowered_layer.endswith(f"-{suffix}")
            for suffix, _dispersion in _FUNCTIONAL_SUFFIX_DISPERSION
        ):
            raise ValueError(
                "Gaussian dispersion shorthand is supported only on the "
                "first functional layer"
            )
    first = layers[0]
    lowered = first.lower()
    for suffix, dispersion in _FUNCTIONAL_SUFFIX_DISPERSION:
        marker = f"-{suffix}"
        if lowered.endswith(marker):
            without_shorthand = first[: -len(marker)]
            lowered_without = without_shorthand.lower()
            if any(
                lowered_without.endswith(f"-{other_suffix}")
                for other_suffix, _other_dispersion in _FUNCTIONAL_SUFFIX_DISPERSION
            ):
                raise ValueError(
                    "Multiple Gaussian functional dispersion shorthands "
                    "are not allowed"
                )
            layers[0] = without_shorthand
            return ":".join(layers), dispersion
    return functional, None


def gaussian_functional_without_dispersion_shorthand(functional, dispersion):
    """Strip only the parser shorthand bound to the same dispersion."""

    if functional is None or dispersion is None:
        return functional
    native_dispersion = normalize_gaussian_dispersion(dispersion)
    without_shorthand, shorthand_dispersion = (
        split_gaussian_functional_dispersion_shorthand(functional)
    )
    if shorthand_dispersion is not None:
        if shorthand_dispersion != native_dispersion:
            raise ValueError(
                "Gaussian functional dispersion shorthand conflicts with "
                f"dispersion={native_dispersion}"
            )
        return without_shorthand
    return functional


class GaussianRoute:
    """Parser and analyzer for Gaussian route sections.

    This class provides comprehensive parsing of Gaussian route sections,
    extracting and organizing information about computational methods,
    basis sets, job types, and various calculation options.

    The route section (starting with # or #P, #T, etc.) specifies:
    - Computational method (HF, DFT functional, MP2, etc.)
    - Basis set specification
    - Job type (opt, freq, scan, sp, etc.)
    - Solvation models and parameters
    - Additional calculation options

    Args:
        route_string (str): The complete route section string from
                           a Gaussian input file. Multi-line routes
                           are automatically joined.

    Attributes:
        route_string (str): Processed route string in lowercase
        route_inputs (list): Individual route keywords/options

    Example:
        >>> route = GaussianRoute("#P B3LYP/6-31G(d) opt freq")
        >>> route.method  # 'b3lyp'
        >>> route.basis   # '6-31g(d)'
        >>> route.jobtype  # 'opt'
    """

    def __init__(self, route_string):
        """
        Initialize the route parser.
        """
        # Handle multi-line routes by joining with spaces
        if "\n" in route_string:
            route_string = route_string.replace("\n", " ")
        self.route_string = route_string.lower()
        self.route_inputs = self.route_string.split()

    @property
    def dieze_tag(self):
        """
        Extract the route prefix tag (#, #P, #T, etc.).
        """
        return self.get_dieze_tag()

    @property
    def jobtype(self):
        """
        Extract the primary job type from the route.
        """
        return self.get_jobtype()

    @property
    def freq(self):
        """
        Check if frequency calculation is requested.
        """
        return self.get_frequency()

    @property
    def numfreq(self):
        """
        Extract numerical frequency specification.
        """
        return self.get_numfreq()

    @property
    def force(self):
        """
        Check if force calculation is requested.
        """
        return "force" in self.route_string

    @property
    def ab_initio(self):
        """
        Extract ab initio method specification.
        """
        return self.get_ab_initio()

    @property
    def functional(self):
        """
        Extract DFT functional from the route.
        """
        functional, _ = self.get_functional_and_basis()
        return functional

    @property
    def basis(self):
        """
        Extract basis set specification from the route.
        """
        _, basis = self.get_functional_and_basis()
        return basis

    @property
    def dispersion(self):
        """Extract the independent empirical-dispersion setting."""

        _, dispersion = split_gaussian_dispersion_tokens(self.route_string)
        return dispersion

    @property
    def method(self):
        """
        Extract the computational method (functional or ab initio).
        """
        return self.functional or self.ab_initio or self.semiempirical

    @property
    def semiempirical(self):
        """
        Extract semi-empirical method specification.
        """
        oniom_method, _ = self._get_oniom_layer_methods_and_bases()
        if oniom_method is not None:
            high_layer_method = oniom_method.split(":")[0]
            if any(
                semiemp.lower() in high_layer_method
                for semiemp in GAUSSIAN_SEMIEMPIRICAL
            ):
                return oniom_method.upper()
            return None

        for each_input in self.route_inputs:
            if any(
                semiemp.lower() in each_input
                for semiemp in GAUSSIAN_SEMIEMPIRICAL
            ):
                return each_input.upper()
        return None

    @property
    def solvent_model(self):
        """
        Extract solvation model from SCRF specification.
        """
        return self.get_solvent_model()

    @property
    def solvent_id(self):
        """
        Extract solvent identity from SCRF specification.
        """
        return self.get_solvent_id()

    @property
    def additional_solvent_options(self):
        """
        Extract additional solvation options.
        """
        return self.get_additional_solvent_options()

    @property
    def solv(self):
        """
        Check if solvation is specified.
        """
        return self.solvent_model is not None and self.solvent_id is not None

    @property
    def additional_opt_options_in_route(self):
        """
        Extract additional optimization options.
        """
        return self.get_additional_opt_options()

    @property
    def additional_route_parameters(self):
        """
        Extract additional route parameters.
        """
        return self.get_additional_route_parameters()

    @property
    def broken_symmetry(self):
        """Whether this route is the broken-symmetry request.

        See :func:`gaussian_route_broken_symmetry`: the unrestricted method
        and its ``guess=mix`` are the request, and they read back as it.
        """
        return gaussian_route_broken_symmetry(self.route_string)

    def get_dieze_tag(self):
        """
        Extract the job priority tag from route string.
        """
        dieze_tag = None
        # dieze_tag '# ', '#N', '#P' '#T'
        if "#" in self.route_string and any(
            self.route_string.startswith(tag) for tag in GAUSSIAN_DIEZE_TAGS
        ):
            dieze_tag = self.route_string[0:2]
        return dieze_tag

    def get_jobtype(self):
        """
        Extract job type from route specification.
        """
        # Match whole route keywords and resolve IRC before TS.  A raw
        # substring check misclassified ``maxpoints`` in every IRC route as
        # the two letters ``ts``.
        if "irc" in self.route_string and "forward" in self.route_string:
            jobtype = "ircf"
        elif "irc" in self.route_string and "reverse" in self.route_string:
            jobtype = "ircr"
        elif re.search(r"(?<![a-z0-9_])irc(?![a-z0-9_])", self.route_string):
            jobtype = "irc"
        elif re.search(r"(?<![a-z0-9_])ts(?![a-z0-9_])", self.route_string):
            jobtype = "ts"
        elif (
            "opt" in self.route_string
            and not re.search(
                r"(?<![a-z0-9_])ts(?![a-z0-9_])", self.route_string
            )
            and "modred" not in self.route_string
            and "stable=opt" not in self.route_string
        ):
            jobtype = "opt"
        elif "modred" in self.route_string:
            # Any optimisation carrying modredundant coordinates, however
            # the route spells it.  This matched the literal ``opt=modred``
            # only, so ``opt=(modredundant,maxstep=10)`` -- one of the
            # legal spellings, and the one an archived real relaxed scan in
            # this repository uses -- fell past the ``opt`` branch (which
            # excludes any route naming modred) and out of the chain as
            # ``sp``: a completed relaxed scan classified as a
            # fixed-geometry single point.  Whether the coordinates are
            # frozen or driven is not in the route at all; the output
            # reader tells those apart from the ModRedundant section
            # Gaussian echoes.
            jobtype = "modred"
        elif "output=wfn" in self.route_string:
            jobtype = "nci"
        elif (
            "Pop=MK IOp(6/33=2,6/41=10,6/42=17,6/50=1)".lower()
            in self.route_string
        ):
            jobtype = "resp"
        elif "stable=opt" in self.route_string:
            jobtype = (
                "link"  # so far only using stable=opt to determine link job
            )
        else:
            jobtype = "sp"
        return jobtype

    def get_frequency(self):
        """
        Check for frequency calculation in route.

        Note: Method name has typo (freqeuncy instead of frequency)
        """
        # get freq: T/F
        return "freq" in self.route_string

    def get_numfreq(self):
        """
        Check for numerical frequency calculation.
        """
        return "freq=numer" in self.route_string

    def get_ab_initio(self):
        """
        Extract ab initio method from route specification.
        """
        oniom_method, _ = self._get_oniom_layer_methods_and_bases()
        if oniom_method is not None and any(
            ab in oniom_method for ab in GAUSSIAN_AB_INITIO
        ):
            return oniom_method
        # get ab initio method by looking through the route string
        ab_initio = None
        for each_input in self.route_inputs:
            if any(ab in each_input for ab in GAUSSIAN_AB_INITIO):
                ab_initio = each_input
        if (
            ab_initio is not None
            and ab_initio.startswith("u")
            and self.broken_symmetry
        ):
            # The unrestricted prefix is the broken-symmetry request's,
            # read back by ``broken_symmetry``; the method is its own word.
            ab_initio = ab_initio[1:]
        return ab_initio

    def _get_oniom_layer_methods_and_bases(self):
        """Return layer method/basis stacks from an ONIOM route."""
        marker = "oniom("
        start = self.route_string.find(marker)
        if start == -1:
            return None, None
        content = []
        depth = 0
        for char in self.route_string[start + len(marker) :]:
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            content.append(char)
        else:
            return None, None
        methods = []
        bases = []
        for layer in self._split_top_level("".join(content), sep=":"):
            method_basis = self._split_top_level(layer, sep="/")
            if method_basis:
                methods.append(method_basis[0])
                bases.append(
                    "/".join(method_basis[1:])
                    if len(method_basis) > 1
                    else "none"
                )
        if not methods:
            return None, None
        return ":".join(methods), ":".join(bases)

    @staticmethod
    def _split_top_level(text, sep):
        """Split text on a separator while ignoring nested parentheses."""
        parts = []
        start = 0
        depth = 0
        for i, char in enumerate(text):
            if char == "(":
                depth += 1
            elif char == ")" and depth > 0:
                depth -= 1
            elif char == sep and depth == 0:
                parts.append(text[start:i].strip())
                start = i + 1
        parts.append(text[start:].strip())
        return [part for part in parts if part]

    def get_functional_and_basis(self):
        """
        Extract DFT functional and basis set from route specification.
        """
        functional = None
        basis = None
        dispersion = None
        oniom_functional, oniom_basis = (
            self._get_oniom_layer_methods_and_bases()
        )
        if oniom_functional is not None:
            functional = oniom_functional
            basis = oniom_basis
        for each_input in self.route_inputs:
            if oniom_functional is not None and "oniom" in each_input:
                continue
            # Extract functional and basis from method/basis format
            if "/" in each_input:
                func_basis = each_input.split(
                    "/"
                )  # TODO # not necessarily for non-standard route e.g.
                # pbepbe 6-31g(d,p)/auto force
                # scrf=(dipole,solvent=water) pbc=gammaonly'
                if len(func_basis) == 2:
                    functional = func_basis[0]
                    basis = func_basis[1]
                elif len(func_basis) == 3:  # e.g., tpsstpss/def2tzvp/fit
                    functional = func_basis[0]
                    # note if the basis set for density fitting is written
                    basis = f"{func_basis[1]}/{func_basis[2]}"
                    # as 'def2tzvp fit', then the job fails to run
            else:  # '/' not in route
                if any(
                    functional in each_input
                    for functional in GAUSSIAN_FUNCTIONALS
                ):
                    functional = each_input
                if "empiricaldispersion" in each_input:
                    dispersion = each_input
                if (
                    any(
                        each_input.startswith(basisset)
                        for basisset in GAUSSIAN_BASES
                    )
                    and "generic" not in each_input
                ):
                    basis = each_input

        # non standard input by user e.g., `#wb897xd` without space
        if functional is not None and functional.startswith("#"):
            functional = functional[1:]

        # Strip spin prefix (u/r/ro) from DFT functional for consistency
        # across QM packages (e.g., Gaussian um062x -> m062x like ORCA)
        if functional is not None:
            parts = (
                functional.split(":") if ":" in functional else [functional]
            )
            stripped_parts = []
            for part in parts:
                prefix = _gaussian_functional_spin_prefix(part)
                stripped_parts.append(
                    part if prefix is None else part[len(prefix) :]
                )
            # The route word is Gaussian's and the answer is ChemSmart's:
            # ``pbe1pbe`` is the literal ``pbe0``, so a written input reads
            # back to what was requested and a Gaussian result names its
            # functional the way ORCA's and PySCF's do.
            from chemsmart.jobs.gaussian.settings import (
                gaussian_functional_literal,
            )

            functional = ":".join(
                gaussian_functional_literal(part) for part in stripped_parts
            )

        # Merge empirical dispersion into functional shorthand
        # e.g., b3lyp + empiricaldispersion=gd3bj -> b3lyp-d3bj
        if functional is not None and dispersion is not None:
            dispersion_suffix_map = {
                "gd3bj": "d3bj",
                "gd3": "d3",
                "gd2": "d2",
            }
            for key, suffix in dispersion_suffix_map.items():
                if key in dispersion:
                    if ":" in functional:
                        layers = functional.split(":")
                        functional = ":".join(
                            [f"{layers[0]}-{suffix}", *layers[1:]]
                        )
                    else:
                        functional = f"{functional}-{suffix}"
                    break

        return functional, basis

    def get_additional_route_parameters(self):
        """
        Extract additional route parameters.
        """
        broken_symmetry = self.broken_symmetry
        additional_route = [
            each_input
            for each_input in self.route_inputs
            if any(
                route_parameter in each_input
                for route_parameter in GAUSSIAN_ADDITIONAL_ROUTE_PARAMETERS
            )
            # The mixing guess of a broken-symmetry route belongs to that
            # request, which reads back under its own name.
            and not (
                broken_symmetry and _GAUSSIAN_GUESS_MIX.search(each_input)
            )
        ]

        return (
            " ".join(additional_route) if len(additional_route) != 0 else None
        )

    def get_additional_opt_options(self):
        """
        Extract additional optimization options from route.
        """
        additional_opt_options = []
        for each_input in self.route_inputs:
            if "opt" in each_input:
                opt_route = (
                    each_input.replace("opt=", "opt")
                    .split("opt")[-1]
                    .replace("(", "")
                    .replace(")", "")
                )
                if len(opt_route) != 0:
                    opt_options = opt_route.split(",")
                    for opt_option in opt_options:
                        # if 'eigentest' in opt_option and 'ts' in route_input:
                        # additional_opt_options.append(opt_option)
                        # # add `no/eigentest` only for ts jobs
                        # <-- `eigentest` already included in writing
                        # in GaussianSettings.write_gaussian_input()
                        if any(
                            option in opt_option
                            for option in GAUSSIAN_ADDITIONAL_OPT_OPTIONS
                        ):
                            additional_opt_options.append(
                                opt_option
                            )  # noqa: PERF401

        return (
            ",".join(additional_opt_options)
            if len(additional_opt_options) != 0
            else None
        )

    def get_solvent_model(self):
        """
        Extract solvation model from SCRF specification.
        """
        if "scrf" in self.route_string:
            scrf_string = ""
            for each_input in self.route_inputs:
                if "scrf" in each_input:
                    scrf_string = each_input

            # get solvation model e.g., scrf=(cpcm,solvent=toluene)
            # if none of the models are present, set
            # default model to pcm as in Gaussian
            if all(
                model not in scrf_string for model in gaussian_solvation_models
            ):
                solvent_model = "pcm"
            else:
                # some model is present, then parse route_input
                solvent_model = (
                    scrf_string.strip()
                    .split("(")[-1]
                    .strip()
                    .split(",")[0]
                    .strip()
                )
            return solvent_model
        return None

    def get_solvent_id(self):
        """
        Extract solvent identity from SCRF specification.
        """
        if "scrf" in self.route_string:
            scrf_string = ""
            for each_input in self.route_inputs:
                if "scrf" in each_input:
                    scrf_string = each_input

                    # get solvent identity
                    if "solvent" in scrf_string:
                        after_solvent = (
                            scrf_string.strip()
                            .split("solvent=")[-1]
                            .split(")")[0]
                        )
                        parts = after_solvent.split(",")
                        while (
                            len(parts) > 1
                            and parts[-1] != "read"
                            and parts[-1] not in gaussian_solvation_models
                            and "=" not in parts[-1]
                            and "-" not in parts[-1]
                        ):
                            parts.pop()
                        solvent_id = ",".join(parts)
                        if "read" in each_input and not solvent_id.endswith(
                            ",read"
                        ):
                            # include read in solvent_id
                            solvent_id = f"{solvent_id},read"
                        return solvent_id
            return None
        return None

    def get_additional_solvent_options(self):
        """
        Extract additional solvation options from SCRF specification.
        """
        if "scrf" in self.route_string:
            scrf_string = ""
            for each_input in self.route_inputs:
                if "scrf" in each_input:
                    scrf_string = each_input
                    scrf_line = scrf_string.split("(")[-1].split(")")[0]
                    scrf_line_elements = [
                        e.strip() for e in scrf_line.split(",")
                    ]
                    if len(scrf_line_elements) <= 2:
                        return None

                    # Identify elements to remove
                    elements_to_remove = set()

                    # Remove solvent model and solvent id
                    for element in scrf_line_elements:
                        if element in gaussian_solvation_models:
                            elements_to_remove.add(element)
                        if element.startswith(
                            "solvent="
                        ):  # Check if it's the solvent id
                            elements_to_remove.add(element)
                        if element == "read":
                            # included as part of solvent id
                            elements_to_remove.add(element)

                    # Remove identified elements
                    filtered_elements = [
                        e
                        for e in scrf_line_elements
                        if e not in elements_to_remove
                    ]
                    return (
                        ",".join(filtered_elements)
                        if filtered_elements
                        else None
                    )
        return None
