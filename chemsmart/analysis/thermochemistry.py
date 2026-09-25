import logging
import math
import os
from dataclasses import dataclass
from functools import cached_property

import numpy as np
from ase import units

from chemsmart.analysis.aggregation import boltzmann_populations
from chemsmart.io.gaussian.output import Gaussian16Output
from chemsmart.io.molecules.structure import Molecule
from chemsmart.io.orca.output import ORCAOutput
from chemsmart.io.xtb.output import XTBOutput
from chemsmart.utils.constants import (
    R,
    atm_to_pa,
    energy_conversion,
    hartree_to_joules,
)
from chemsmart.utils.geometry import clean_rotational_constants_by_geometry
from chemsmart.utils.io import get_program_type_from_file
from chemsmart.utils.references import (
    grimme_quasi_rrho_entropy_ref,
    head_gordon_damping_function_ref,
    head_gordon_quasi_rrho_enthalpy_ref,
    qrrho_header,
    truhlar_quasi_rrho_entropy_ref,
)

logger = logging.getLogger(__name__)


#: A Hessian's six translational and rotational modes come out numerically
#: near zero rather than exactly zero, and a floppy torsion can push one of
#: them slightly below it.  A mode of a few wavenumbers on the wrong side of
#: zero is that numerical noise, not a reaction coordinate: a genuine
#: imaginary mode of a saddle point is hundreds of wavenumbers.  xTB draws the
#: same line at 20 cm^-1 and reports such a structure as having no imaginary
#: modes, so treat that as the shared convention rather than contradicting the
#: program that produced the Hessian.
NEAR_ZERO_FREQUENCY_TOLERANCE_CM = 20.0

#: How far, in Angstrom, an atom may sit from the image of an equivalent
#: atom under a proper rotation and still count as mapped onto it, when the
#: host counts the rotational symmetry number.  An optimiser that ran
#: without symmetry leaves a symmetric minimum symmetric only to its own
#: convergence, about 1e-3 A; a genuine lower-symmetry structure moves atoms
#: by tenths of an Angstrom.
ROTATIONAL_SYMMETRY_TOLERANCE_ANGSTROM = 0.05


def _kabsch_rotation(source, target):
    """The proper rotation that best maps ``source`` rows onto ``target``."""

    covariance = source.T @ target
    u, _s, vt = np.linalg.svd(covariance)
    sign = np.sign(np.linalg.det(vt.T @ u.T)) or 1.0
    correction = np.diag([1.0, 1.0, sign])
    return vt.T @ correction @ u.T


def rotational_symmetry_number_from_geometry(
    symbols,
    positions,
    masses,
    *,
    linear=False,
    tolerance_angstrom=ROTATIONAL_SYMMETRY_TOLERANCE_ANGSTROM,
):
    """Count the proper rotations that map a structure onto itself.

    The rotational symmetry number is the order of the molecule's
    rotational subgroup -- 2 for water and for CO2, 3 for ammonia, 12 for
    methane and benzene -- and it divides the rotational partition
    function, so a wrong one moves every Gibbs energy by RT ln(sigma).
    Every program answers it differently: ORCA 6.0.1 printed 1 for CO2
    (D-infinity-h) and C1 for a C2v phenolate its own optimiser had
    converged, while Gaussian and xTB printed 2 for the same CO2.  Counting
    the rotations here makes it one number per structure, whichever
    program computed the frequencies.

    Each candidate rotation is fixed by where it sends two reference atoms
    (the rarest element-and-radius classes, so the candidates are few),
    refined by a least-squares fit over every atom it matched, and kept
    when every atom lands within ``tolerance_angstrom`` of an equivalent
    one.  A linear structure is 2 when inversion maps it onto itself and 1
    otherwise.  Returns ``(sigma, rotations_found)``; the identity counts.
    """

    symbols = [str(symbol) for symbol in symbols]
    positions = np.asarray(positions, dtype=float)
    masses = np.asarray(masses, dtype=float)
    if len(symbols) < 2:
        return 1, 1
    tolerance = float(tolerance_angstrom)
    relative = positions - (positions * masses[:, None]).sum(axis=0) / (
        masses.sum()
    )
    elements = np.array(symbols)

    def _maps_onto_itself(image):
        for element in set(symbols):
            chosen = elements == element
            moved = image[chosen]
            fixed = relative[chosen]
            distances = np.linalg.norm(
                moved[:, None, :] - fixed[None, :, :], axis=2
            )
            nearest = distances.argmin(axis=1)
            if len(set(nearest.tolist())) != len(nearest):
                return False
            if float(distances.min(axis=1).max()) > tolerance:
                return False
        return True

    if linear:
        return (2, 2) if _maps_onto_itself(-relative) else (1, 1)

    radii = np.linalg.norm(relative, axis=1)
    off_centre = [index for index in range(len(symbols)) if radii[index] > 0.1]

    def _class(index):
        return [
            other
            for other in off_centre
            if symbols[other] == symbols[index]
            and abs(radii[other] - radii[index]) < 2.0 * tolerance
        ]

    anchor = min(
        off_centre, key=lambda index: (len(_class(index)), -radii[index])
    )
    axis = relative[anchor] / radii[anchor]

    def _perpendicular(index):
        return float(np.linalg.norm(np.cross(axis, relative[index])))

    partners = [
        index
        for index in off_centre
        if index != anchor and _perpendicular(index) > 0.1
    ]
    if not partners:
        return (2, 2) if _maps_onto_itself(-relative) else (1, 1)
    partner = min(
        partners,
        key=lambda index: (len(_class(index)), -_perpendicular(index)),
    )

    def _frame(first, second):
        e1 = first / np.linalg.norm(first)
        e2 = second - float(second @ e1) * e1
        e2 = e2 / np.linalg.norm(e2)
        return np.column_stack([e1, e2, np.cross(e1, e2)])

    reference = _frame(relative[anchor], relative[partner])
    separation = float(np.linalg.norm(relative[anchor] - relative[partner]))
    found = 0
    for image_anchor in _class(anchor):
        for image_partner in _class(partner):
            if image_partner == image_anchor:
                continue
            distance = float(
                np.linalg.norm(
                    relative[image_anchor] - relative[image_partner]
                )
            )
            if abs(distance - separation) > 4.0 * tolerance:
                continue
            if _perpendicular_to(relative, image_anchor, image_partner) < 0.05:
                continue
            guess = (
                _frame(relative[image_anchor], relative[image_partner])
                @ reference.T
            )
            moved = relative @ guess.T
            # Correspond every atom under the first guess, then refit on
            # all of them: two reference atoms fix the rotation only as
            # well as their own coordinates are symmetric.
            order = []
            for index, row in enumerate(moved):
                same = [
                    other
                    for other in range(len(symbols))
                    if symbols[other] == symbols[index]
                ]
                order.append(
                    min(
                        same,
                        key=lambda other: float(
                            np.linalg.norm(row - relative[other])
                        ),
                    )
                )
            if len(set(order)) != len(order):
                continue
            fitted = _kabsch_rotation(relative, relative[order])
            if _maps_onto_itself(relative @ fitted.T):
                found += 1
    return max(found, 1), max(found, 1)


def _quasi_linear_padding(frequencies, num_atoms):
    """The mode a quasi-linear rotor is missing, or None.

    A program that treats a nearly linear structure as nonlinear prints
    3N-6 modes; a linear rotor has 3N-5, the missing one the degenerate
    partner of the lowest bend.  One function, because the formulas and
    the receipt's statement both ask it.
    """

    expected = 3 * int(num_atoms) - 5
    if frequencies and len(frequencies) == expected - 1:
        return min(f for f in frequencies if f > 0)
    return None


def _perpendicular_to(relative, first, second):
    """|a x b| / |a| for two rows: how far ``second`` sits off ``first``'s axis."""

    a = relative[first]
    norm = float(np.linalg.norm(a))
    if norm == 0.0:
        return 0.0
    return float(np.linalg.norm(np.cross(a / norm, relative[second])))


#: The internal coordinates a projected analysis removes, by atom count --
#: the rows a constrained optimisation (``modred``) holds.
INTERNAL_COORDINATE_KINDS = {2: "bond", 3: "angle", 4: "dihedral"}

#: The wavenumber (cm^-1) of a unit eigenvalue of a mass-weighted Cartesian
#: Hessian in Eh / (amu Bohr^2).
HESSIAN_EIGENVALUE_TO_CM1 = math.sqrt(
    units.Hartree * units._e / (units._amu * (units.Bohr * 1e-10) ** 2)
) / (2.0 * math.pi * units._c * 100.0)


def internal_coordinate_value(positions, atoms):
    """One internal coordinate: a length, or an angle in radians.

    ``atoms`` are zero-based: two for a bond, three for an angle with its
    vertex in the middle, four for a dihedral about the middle pair.
    """

    x = np.asarray(positions, dtype=float)
    atoms = [int(index) for index in atoms]
    if len(atoms) == 2:
        return float(np.linalg.norm(x[atoms[0]] - x[atoms[1]]))
    if len(atoms) == 3:
        u = x[atoms[0]] - x[atoms[1]]
        v = x[atoms[2]] - x[atoms[1]]
        cosine = float(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)))
        return math.acos(max(-1.0, min(1.0, cosine)))
    if len(atoms) == 4:
        b0 = x[atoms[0]] - x[atoms[1]]
        b1 = x[atoms[2]] - x[atoms[1]]
        b2 = x[atoms[3]] - x[atoms[2]]
        axis = b1 / np.linalg.norm(b1)
        v = b0 - (b0 @ axis) * axis
        w = b2 - (b2 @ axis) * axis
        return math.atan2(float(np.cross(axis, v) @ w), float(v @ w))
    raise ValueError(
        "an internal coordinate names two, three or four atoms, not "
        f"{len(atoms)}"
    )


def internal_coordinate_gradient(positions, atoms):
    """The Cartesian gradient of one internal coordinate, shape (N, 3).

    Its direction, mass-weighted, is the normal of the surface on which the
    coordinate keeps its value, which is what a projection removes.  Units
    follow ``positions``: dimensionless for a bond, radians per length for
    an angle or a dihedral.  Refused where the coordinate has no direction
    -- a linear angle, or a dihedral one of whose angles is linear.
    """

    x = np.asarray(positions, dtype=float)
    atoms = [int(index) for index in atoms]
    if len(set(atoms)) != len(atoms):
        raise ValueError(f"atoms {atoms} name one atom twice")
    gradient = np.zeros_like(x)
    if len(atoms) == 2:
        a, b = atoms
        u = x[a] - x[b]
        u = u / np.linalg.norm(u)
        gradient[a] = u
        gradient[b] = -u
        return gradient
    if len(atoms) == 3:
        a, b, c = atoms
        u = x[a] - x[b]
        v = x[c] - x[b]
        lu = float(np.linalg.norm(u))
        lv = float(np.linalg.norm(v))
        eu = u / lu
        ev = v / lv
        cosine = float(eu @ ev)
        sine = math.sqrt(max(0.0, 1.0 - cosine * cosine))
        if sine < 1e-6:
            raise ValueError(
                f"the angle {atoms} is linear and has no direction to hold"
            )
        gradient[a] = (cosine * eu - ev) / (lu * sine)
        gradient[c] = (cosine * ev - eu) / (lv * sine)
        gradient[b] = -(gradient[a] + gradient[c])
        return gradient
    if len(atoms) == 4:
        a, b, c, d = atoms
        f = x[a] - x[b]
        g = x[b] - x[c]
        h = x[d] - x[c]
        first = np.cross(f, g)
        second = np.cross(h, g)
        a2 = float(first @ first)
        b2 = float(second @ second)
        lg = float(np.linalg.norm(g))
        if a2 < 1e-12 * lg**4 or b2 < 1e-12 * lg**4:
            raise ValueError(
                f"the dihedral {atoms} has a linear angle and no direction "
                "to hold"
            )
        fg = float(f @ g)
        hg = float(h @ g)
        gradient[a] = -lg / a2 * first
        gradient[d] = lg / b2 * second
        gradient[b] = (lg / a2 + fg / (a2 * lg)) * first - hg / (
            b2 * lg
        ) * second
        gradient[c] = (
            -(lg / b2 - hg / (b2 * lg)) * second - fg / (a2 * lg) * first
        )
        return gradient
    raise ValueError(
        "an internal coordinate names two, three or four atoms, not "
        f"{len(atoms)}"
    )


def _translation_rotation_vectors(positions, masses):
    """The six mass-weighted rigid motions (one may vanish for a linear rotor)."""

    x = np.asarray(positions, dtype=float)
    m = np.asarray(masses, dtype=float)
    relative = x - (x * m[:, None]).sum(axis=0) / m.sum()
    root = np.sqrt(m)
    vectors = []
    for axis in range(3):
        translation = np.zeros_like(x)
        translation[:, axis] = root
        vectors.append(translation.ravel())
    for axis in range(3):
        unit = np.zeros(3)
        unit[axis] = 1.0
        vectors.append((np.cross(unit, relative) * root[:, None]).ravel())
    return vectors


@dataclass(frozen=True)
class ProjectedSpectrumV1:
    """What a projected harmonic analysis kept and what it removed.

    ``frequencies_cm1`` ascending, an imaginary mode negative;
    ``external`` the translations and rotations removed (6, or 5 for a
    linear rotor); ``internal`` the held coordinates removed.
    """

    frequencies_cm1: tuple[float, ...]
    external: int
    internal: int
    atoms: int

    @property
    def kept(self) -> int:
        return len(self.frequencies_cm1)


def projected_harmonic_frequencies(hessian, positions, masses, directions=()):
    """Harmonic wavenumbers with rigid motions and ``directions`` removed.

    ``hessian`` is the Cartesian Hessian in Eh/Bohr^2 (3N x 3N),
    ``positions`` are in Bohr, ``masses`` in amu, and each direction is a
    Cartesian (N x 3) vector -- the gradient of a coordinate held fixed.
    Each direction is mass-weighted (M^-1/2 b, the normal of the surface on
    which that coordinate is constant), the space it spans with the
    translations and rotations is removed, and the mass-weighted Hessian is
    diagonalised in what remains: (I - P) H (I - P), the projection of
    Baboul and Schlegel (J. Chem. Phys. 107, 9413 (1997), Eq. 4) with a
    held coordinate's normal where they take the reaction-path tangent.
    With no direction this is the ordinary analysis every program prints.
    """

    x = np.asarray(positions, dtype=float)
    atoms = x.shape[0]
    h = np.asarray(hessian, dtype=float).reshape(3 * atoms, 3 * atoms)
    h = 0.5 * (h + h.T)
    inverse_root = 1.0 / np.sqrt(np.repeat(np.asarray(masses, float), 3))
    weighted = h * np.outer(inverse_root, inverse_root)

    def _independent(vectors):
        kept = []
        for vector in vectors:
            norm = float(np.linalg.norm(vector))
            if norm > 1e-8:
                kept.append(vector / norm)
        if not kept:
            return np.zeros((3 * atoms, 0)), 0
        basis, singular, _ = np.linalg.svd(
            np.array(kept).T, full_matrices=True
        )
        rank = int((singular > 1e-6).sum())
        return basis, rank

    rigid = _translation_rotation_vectors(x, masses)
    _basis, external = _independent(rigid)
    held = [np.asarray(b, float).ravel() * inverse_root for b in directions]
    basis, rank = _independent(rigid + held)
    if rank != external + len(held):
        raise ValueError(
            "the held coordinates are not independent of each other and of "
            "the rigid motions: removing them removes "
            f"{rank - external} direction(s), not {len(held)}"
        )
    complement = basis[:, rank:]
    eigenvalues = np.linalg.eigvalsh(complement.T @ weighted @ complement)
    frequencies = tuple(
        float(np.sign(value) * math.sqrt(abs(value)))
        * HESSIAN_EIGENVALUE_TO_CM1
        for value in eigenvalues
    )
    return ProjectedSpectrumV1(
        frequencies_cm1=frequencies,
        external=external,
        internal=len(held),
        atoms=atoms,
    )


# ---------------------------------------------------------------------------
# Internal rotation: the one-dimensional hindered rotor
# ---------------------------------------------------------------------------
#
# A torsion about a single bond is a harmonic oscillator only near the
# bottom of a deep well.  H2O2 has two mirror-image wells over one turn and
# a trans barrier of about 1.9 kT at 298 K; methanol's methyl barrier is
# about 1.8 kT.  A harmonic mode counts one well and a parabola that never
# ends, so the entropy it gives misses by several J/(K mol).  The treatment
# below is the one NIST-JANAF and Gurvich use for their own tables (Dorofeeva,
# Novikov & Neumann, JPCRD 30, 475 (2001)): the internal-rotation levels are
# the eigenvalues of the one-dimensional Hamiltonian -B d2/dphi2 + V(phi) on a
# Fourier potential, with B from the reduced moment of the rotating top, and
# the partition function sums every level over one full turn and divides by
# the rotor's own symmetry number.

#: B (cm^-1) = ROTOR_CONSTANT_CM1_AMU_A2 / I for a rotor of moment I (amu A^2).
ROTOR_CONSTANT_CM1_AMU_A2 = units._hplanck / (
    8.0 * math.pi**2 * units._c * 100.0 * units._amu * 1e-20
)

#: k / (h c): a temperature in kelvin times this is kT in cm^-1.
BOLTZMANN_CM1_PER_K = units._k / (units._hplanck * units._c * 100.0)

#: J/mol per cm^-1.
CM1_TO_J_PER_MOL = units._hplanck * units._c * 100.0 * units._Nav

#: How far (Angstrom) an atom of a rotating top may sit from the image of an
#: equivalent atom under a turn about the bond it rotates on, and the turn
#: still count as a symmetry of the top.  Wider than the whole-molecule
#: tolerance above because the axis is the bond, not the top's own axis: a
#: methyl group's local three-fold axis tilts a few degrees off the bond it
#: turns about, which moves the image of each hydrogen by a few hundredths
#: of an Angstrom, while a top that is not symmetric (OH, CH2CH3) misses by
#: several tenths.  The deviation found is stated on every receipt.
ROTOR_TOP_SYMMETRY_TOLERANCE_ANGSTROM = 0.15

#: A top whose every atom lies within this distance (Angstrom) of the axis
#: has nothing to turn: a linear group (C#N, C#CH) has no torsion.
ROTOR_AXIS_OFFSET_ANGSTROM = 0.1


@dataclass(frozen=True)
class InternalRotorTopsV1:
    """The two ends of a bond a torsion turns about.

    ``axis`` is the bond as zero-based atoms ``(b, c)`` of a torsion
    a-b-c-d; ``top`` is every atom on ``c``'s side (``c`` included) and
    ``frame`` every atom on ``b``'s side, split by the host's adjacency
    (``chemsmart.io.molecules.perception``).  ``top_order`` and
    ``frame_order`` are the orders of the rotations about the bond that map
    each end onto itself, with the largest atom displacement those
    rotations leave (``top_deviation``, ``frame_deviation``, Angstrom).
    """

    axis: tuple[int, int]
    top: tuple[int, ...]
    frame: tuple[int, ...]
    top_order: int
    frame_order: int
    top_deviation: float
    frame_deviation: float

    @property
    def symmetry_number(self) -> int:
        """The rotor's internal symmetry number, lcm of the two orders.

        Turning one end by 2 pi / n_top or the other by 2 pi / n_frame gives
        an indistinguishable molecule, so the potential repeats every
        2 pi / lcm(n_top, n_frame): 3 for ethane and methanol, 1 for
        H2O2, 6 for nitromethane's methyl against its NO2.
        """

        return math.lcm(int(self.top_order), int(self.frame_order))


def _rotor_axis(positions, axis):
    x = np.asarray(positions, dtype=float)
    b, c = (int(index) for index in axis)
    direction = x[c] - x[b]
    length = float(np.linalg.norm(direction))
    if length == 0.0:
        raise ValueError(f"atoms {b + 1} and {c + 1} coincide")
    return x[c], direction / length


def _rotation_matrix(unit, angle):
    """Right-handed rotation by ``angle`` (radians) about ``unit``."""

    ux, uy, uz = unit
    k = np.array([[0.0, -uz, uy], [uz, 0.0, -ux], [-uy, ux, 0.0]])
    return np.eye(3) + math.sin(angle) * k + (1.0 - math.cos(angle)) * (k @ k)


def _end_rotational_order(symbols, positions, atoms, point, unit, tolerance):
    """Order of the largest C_n about the axis mapping ``atoms`` onto
    themselves, and the largest displacement that rotation leaves."""

    x = np.asarray(positions, dtype=float)
    members = [int(index) for index in atoms]
    relative = x[members] - point
    radial = relative - np.outer(relative @ unit, unit)
    off_axis = [
        position
        for position, row in enumerate(radial)
        if float(np.linalg.norm(row)) > ROTOR_AXIS_OFFSET_ANGSTROM
    ]
    if not off_axis:
        raise ValueError(
            "every atom of one end lies on the bond axis, so turning it "
            "about the bond moves nothing: a linear group has no torsion"
        )
    labels = [str(symbols[index]) for index in members]
    best = (1, 0.0)
    for order in range(2, len(off_axis) + 1):
        image = relative @ _rotation_matrix(unit, 2.0 * math.pi / order).T
        worst = 0.0
        taken = set()
        for position, row in enumerate(image):
            candidates = [
                (float(np.linalg.norm(row - relative[other])), other)
                for other in range(len(members))
                if labels[other] == labels[position] and other not in taken
            ]
            distance, other = min(candidates)
            taken.add(other)
            worst = max(worst, distance)
        if worst <= tolerance:
            best = (order, worst)
    return best


def internal_rotor_tops(
    symbols,
    positions,
    axis,
    *,
    tolerance_angstrom=ROTOR_TOP_SYMMETRY_TOLERANCE_ANGSTROM,
):
    """Split a structure at the bond ``axis`` (zero-based ``(b, c)``).

    Refused when the two atoms are not adjacent under the host's declared
    convention, when the bond is in a ring (its torsion is not an internal
    rotation of one part against the rest), and when an end is linear.
    ``positions`` are in Angstrom.
    """

    import networkx as nx

    from chemsmart.io.molecules.perception import adjacency_graph

    b, c = (int(index) for index in axis)
    graph = adjacency_graph(symbols, positions)
    if not graph.has_edge(b, c):
        raise ValueError(
            f"atoms {b + 1} and {c + 1} are not bonded under the host's "
            "adjacency convention, so no internal rotation turns about them"
        )
    graph.remove_edge(b, c)
    top = nx.node_connected_component(graph, c)
    if b in top:
        raise ValueError(
            f"the {b + 1}-{c + 1} bond is in a ring: turning one side "
            "about it is not an internal rotation of a rigid top"
        )
    frame = nx.node_connected_component(graph, b)
    if len(top) + len(frame) != len(list(symbols)):
        raise ValueError(
            "the structure is in more than two pieces once the bond is "
            "cut, so the two ends of the rotor are not the whole molecule"
        )
    point, unit = _rotor_axis(positions, (b, c))
    top_order, top_deviation = _end_rotational_order(
        symbols, positions, sorted(top), point, unit, tolerance_angstrom
    )
    frame_order, frame_deviation = _end_rotational_order(
        symbols, positions, sorted(frame), point, unit, tolerance_angstrom
    )
    return InternalRotorTopsV1(
        axis=(b, c),
        top=tuple(sorted(top)),
        frame=tuple(sorted(frame)),
        top_order=int(top_order),
        frame_order=int(frame_order),
        top_deviation=float(top_deviation),
        frame_deviation=float(frame_deviation),
    )


def internal_rotation_displacement(positions, axis, turning):
    """Cartesian displacement (N x 3) per radian of turning ``turning``
    rigidly about the bond ``axis``; every other atom stands still."""

    x = np.asarray(positions, dtype=float)
    point, unit = _rotor_axis(x, axis)
    displacement = np.zeros_like(x)
    for index in turning:
        displacement[int(index)] = np.cross(unit, x[int(index)] - point)
    return displacement


def _rigid_motion_basis(positions, masses):
    vectors = np.array(
        [
            vector / np.linalg.norm(vector)
            for vector in _translation_rotation_vectors(positions, masses)
            if float(np.linalg.norm(vector)) > 1e-10
        ]
    ).T
    basis, singular, _ = np.linalg.svd(vectors, full_matrices=False)
    return basis[:, singular > 1e-8]


def internal_rotation_moment(positions, masses, axis, turning):
    """The reduced moment of one internal rotation, I(3,4) of East & Radom.

    The kinetic energy of turning ``turning`` rigidly about the bond at
    zero total linear and angular momentum: the turn is written in
    mass-weighted Cartesian coordinates and its translation and rotation
    components are removed, which is exactly the counter-rotation a free
    molecule makes.  Exact within the rigid-rotor model for one internal
    rotation and the same from either end (East & Radom, J. Chem. Phys.
    106, 6655 (1997), Sec. IV.B: methanol 0.6348 amu A^2 at MP2/6-31G(d)).
    Units follow the inputs: amu A^2 for amu and Angstrom.
    """

    x = np.asarray(positions, dtype=float)
    m = np.asarray(masses, dtype=float)
    weighted = (
        internal_rotation_displacement(x, axis, turning) * np.sqrt(m)[:, None]
    ).ravel()
    basis = _rigid_motion_basis(x, m)
    internal = weighted - basis @ (basis.T @ weighted)
    return float(internal @ internal)


@dataclass(frozen=True)
class TorsionalPotentialV1:
    """A torsional potential V(phi) as a Fourier series over one period.

    ``V(phi) = constant + sum_k cosine[k-1] cos(k w phi)
    + sine[k-1] sin(k w phi)`` in cm^-1, with ``w = 2 pi / period`` and phi
    in radians the dihedral as the scan drove it.  ``points`` samples were
    fitted by least squares, ``rms_residual_cm1`` is how closely.
    """

    period_rad: float
    constant: float
    cosine: tuple[float, ...]
    sine: tuple[float, ...]
    points: int
    rms_residual_cm1: float

    @property
    def order(self) -> int:
        return len(self.cosine)

    @property
    def frequency(self) -> float:
        return 2.0 * math.pi / self.period_rad

    def value(self, phi):
        phi = np.asarray(phi, dtype=float)
        total = np.full_like(phi, self.constant, dtype=float)
        for k, (a, b) in enumerate(zip(self.cosine, self.sine), start=1):
            total = total + a * np.cos(k * self.frequency * phi)
            total = total + b * np.sin(k * self.frequency * phi)
        return total

    def second_derivative(self, phi):
        phi = np.asarray(phi, dtype=float)
        total = np.zeros_like(phi, dtype=float)
        for k, (a, b) in enumerate(zip(self.cosine, self.sine), start=1):
            w = k * self.frequency
            total = total - w * w * (a * np.cos(w * phi) + b * np.sin(w * phi))
        return total

    def stationary_points(self, samples=7200):
        """Minima and maxima over one period, refined on a fine grid.

        Returns ``(minima, maxima)``, each a tuple of ``(phi_rad,
        value_cm1)`` in ascending phi.
        """

        grid = np.linspace(0.0, self.period_rad, samples, endpoint=False)
        values = self.value(grid)
        before = np.roll(values, 1)
        after = np.roll(values, -1)
        minima = tuple(
            (float(grid[i]), float(values[i]))
            for i in range(samples)
            if values[i] < before[i] and values[i] <= after[i]
        )
        maxima = tuple(
            (float(grid[i]), float(values[i]))
            for i in range(samples)
            if values[i] > before[i] and values[i] >= after[i]
        )
        return minima, maxima

    @property
    def minimum(self):
        """``(phi_rad, value_cm1)`` of the lowest point over one period."""

        grid = np.linspace(0.0, self.period_rad, 7200, endpoint=False)
        values = self.value(grid)
        lowest = int(np.argmin(values))
        return float(grid[lowest]), float(values[lowest])


#: The highest harmonic of the period a scan's potential is fitted with, at
#: most; fewer when the scan has fewer points than twice this plus one.
TORSIONAL_FOURIER_ORDER = 6


def fit_torsional_potential(
    phi_rad, energies_cm1, period_rad, max_order=TORSIONAL_FOURIER_ORDER
):
    """Least-squares Fourier series of one period of a torsional potential.

    ``phi_rad`` are the dihedral values of the samples (any origin; each is
    taken modulo the period), ``energies_cm1`` their energies on any common
    zero.  Cosine and sine terms up to ``max_order`` harmonics of the
    period, fewer when the samples cannot determine them.
    """

    phi = np.asarray(phi_rad, dtype=float)
    energy = np.asarray(energies_cm1, dtype=float)
    if phi.shape != energy.shape or phi.ndim != 1:
        raise ValueError("one energy per dihedral value")
    order = min(int(max_order), (len(phi) - 1) // 2)
    if order < 1:
        raise ValueError(
            f"{len(phi)} point(s) cannot determine a torsional potential"
        )
    w = 2.0 * math.pi / float(period_rad)
    columns = [np.ones_like(phi)]
    for k in range(1, order + 1):
        columns.append(np.cos(k * w * phi))
        columns.append(np.sin(k * w * phi))
    design = np.column_stack(columns)
    coefficients, *_ = np.linalg.lstsq(design, energy, rcond=None)
    residual = energy - design @ coefficients
    return TorsionalPotentialV1(
        period_rad=float(period_rad),
        constant=float(coefficients[0]),
        cosine=tuple(float(value) for value in coefficients[1::2]),
        sine=tuple(float(value) for value in coefficients[2::2]),
        points=int(len(phi)),
        rms_residual_cm1=float(np.sqrt(np.mean(residual * residual))),
    )


@dataclass(frozen=True)
class HinderedRotorV1:
    """The levels of one internal rotation on its potential.

    ``levels_cm1`` are the eigenvalues of -B d2/dphi2 + V(phi) over one full
    turn, measured from the potential's minimum, so the lowest is the
    rotor's zero-point energy.  ``symmetry_number`` divides the sum over
    every level (the classical count of indistinguishable orientations);
    ``basis`` is the largest |m| of the free-rotor basis exp(i m phi).
    """

    rotational_constant_cm1: float
    symmetry_number: int
    levels_cm1: tuple[float, ...]
    basis: int
    harmonic_frequency_cm1: float

    @property
    def zero_point_cm1(self) -> float:
        return float(self.levels_cm1[0])

    def thermodynamics(self, temperature_k):
        """``(q, S, U, Cv)`` at T: S and Cv in J/(K mol), U in J/mol from
        the potential minimum (zero-point energy included)."""

        kt = BOLTZMANN_CM1_PER_K * float(temperature_k)
        levels = np.asarray(self.levels_cm1, dtype=float)
        weights = np.exp(-(levels - levels[0]) / kt)
        z = float(weights.sum())
        mean = float((weights * levels).sum() / z)
        second = float((weights * levels * levels).sum() / z)
        q = z * math.exp(-levels[0] / kt) / self.symmetry_number
        entropy = R * (math.log(q) + mean / kt)
        energy = mean * CM1_TO_J_PER_MOL
        heat_capacity = R * (second - mean * mean) / (kt * kt)
        return q, entropy, energy, heat_capacity

    def harmonic_thermodynamics(self, temperature_k):
        """``(S, U, Cv)`` of the harmonic oscillator this rotor replaces:
        the one with the same moment and the curvature at the minimum."""

        nu = float(self.harmonic_frequency_cm1)
        kt = BOLTZMANN_CM1_PER_K * float(temperature_k)
        x = nu / kt
        entropy = R * (x / math.expm1(x) - math.log1p(-math.exp(-x)))
        energy = (0.5 * nu + nu / math.expm1(x)) * CM1_TO_J_PER_MOL
        heat_capacity = R * x * x * math.exp(x) / math.expm1(x) ** 2
        return entropy, energy, heat_capacity


def hindered_rotor(potential, moment_amu_a2, symmetry_number, *, basis=None):
    """Solve the one-dimensional rotor on ``potential`` (see HinderedRotorV1).

    The potential is referred to its own minimum.  The free-rotor basis
    runs to |m| = ``basis``; by default far enough that B m^2 exceeds the
    potential's range by 60000 cm^-1, so every level a partition function
    below 2000 K can reach is converged.
    """

    moment = float(moment_amu_a2)
    if not moment > 0.0:
        raise ValueError("a rotor needs a positive reduced moment")
    sigma = int(symmetry_number)
    b_const = ROTOR_CONSTANT_CM1_AMU_A2 / moment
    fold = potential.frequency
    harmonics = int(round(fold))
    if abs(fold - harmonics) > 1e-9 or harmonics < 1:
        raise ValueError(
            "the potential's period must divide one full turn a whole "
            f"number of times, not {2.0 * math.pi / potential.period_rad:g}"
        )
    phi_min, v_min = potential.minimum
    grid = np.linspace(0.0, potential.period_rad, 3600, endpoint=False)
    v_range = float(potential.value(grid).max()) - v_min
    if basis is None:
        basis = int(math.ceil(math.sqrt((v_range + 60000.0) / b_const))) + 10
    size = 2 * basis + 1
    hamiltonian = np.zeros((size, size), dtype=complex)
    ms = np.arange(-basis, basis + 1)
    hamiltonian[np.diag_indices(size)] = b_const * ms * ms + (
        potential.constant - v_min
    )
    for k, (a, b) in enumerate(zip(potential.cosine, potential.sine), start=1):
        shift = k * harmonics
        if shift >= size:
            continue
        upper = 0.5 * (a - 1j * b)
        for row in range(shift, size):
            hamiltonian[row, row - shift] += upper
            hamiltonian[row - shift, row] += np.conj(upper)
    levels = np.linalg.eigvalsh(hamiltonian)
    curvature = float(potential.second_derivative(phi_min))
    harmonic = math.sqrt(2.0 * b_const * curvature) if curvature > 0 else 0.0
    return HinderedRotorV1(
        rotational_constant_cm1=float(b_const),
        symmetry_number=sigma,
        levels_cm1=tuple(float(value) for value in levels),
        basis=int(basis),
        harmonic_frequency_cm1=float(harmonic),
    )


class Thermochemistry:
    """Class for thermochemistry analysis using SI units.

    Requires filename from which thermochemistry data is extracted.

    Args:
        filename: str. Filepath to the file from which thermochemistry
            data is extracted.
        temperature: float. Temperature of the system, in K.
        concentration: float. Concentration of the system, in mol/L.
        pressure: float. Pressure of the system, in atm.
        use_weighted_mass: bool. If True, use natural abundance weighted
            masses; otherwise, use most abundant masses.
        alpha: int. Interpolator exponent used in the quasi-RRHO
            approximation.
        s_freq_cutoff: float. The cutoff frequency of the damping function
            used in calculating entropy.
        h_freq_cutoff: float. The cutoff frequency of the damping function
            used in calculating enthalpy.
        frequency_scale_factor: float. Positive factor multiplied into all
            parsed vibrational frequencies before thermochemical corrections.
        energy_units: str. The energy units to use for output. Default is
            "hartree".
        outputfile: str. The output file to save the thermochemistry
            results.
        check_imaginary_frequencies: bool. If True, checks for imaginary
            frequencies in the vibrational analysis.
        rotational_mode: str. ``"physical"`` treats linear and quasi-linear
            rotors physically from geometry-derived constants, while
            ``"gaussian"`` preserves Gaussian-style constants when possible
            and falls back to geometry-derived constants if Gaussian printed
            overflow tokens.
    """

    def __init__(
        self,
        filename,
        temperature=None,
        concentration=None,
        pressure=1.0,
        use_weighted_mass=False,
        alpha=4,
        s_freq_cutoff=None,
        entropy_method=None,
        h_freq_cutoff=None,
        frequency_scale_factor=1.0,
        energy_units="hartree",
        check_imaginary_frequencies=True,
        reaction_coordinate_mode=0,
        near_zero_frequency_tolerance_cm=None,
        rotational_mode="physical",
        projected_frequencies=None,
        internal_rotors=(),
        **kwargs,
    ):
        # Internal rotations counted as hindered rotors
        # (:class:`HinderedRotorV1`) beside the vibrational modes.  Their
        # harmonic modes must already be absent from ``projected_frequencies``
        # -- the caller projects each rotor's turn out of the Hessian -- or
        # the torsion is counted twice.  None leaves every number as it was.
        self.internal_rotors = tuple(internal_rotors or ())
        # The kept modes of a projected analysis
        # (:func:`projected_harmonic_frequencies`), in cm^-1, used in place
        # of the program's printed spectrum: a held coordinate removed is
        # a mode the partition functions never see, rather than a
        # frequency to clean.
        self.projected_frequencies = (
            None
            if projected_frequencies is None
            else tuple(float(value) for value in projected_frequencies)
        )
        self.filename = filename
        self.program = get_program_type_from_file(self.filename)
        if self.program == "orca":
            self.molecule = self.file_object.thermochemistry_molecule
        else:
            self.molecule = Molecule.from_filepath(filename)
        self.energy_units = energy_units
        self.check_imaginary_frequencies = check_imaginary_frequencies
        # Which printed mode the session says is the reaction coordinate,
        # 1-based, 0 meaning "the first genuine imaginary one".
        #
        # The public schema has promised a mode *index* since it was
        # added, and the analysis layer used it as a boolean: non-zero
        # switched the strict frequency check off and the index was
        # discarded, so the permissive branch below always removed
        # `(genuine or all)[0]`. Selections 1 and 2 produced identical
        # quantity vectors and identical receipt hashes. A selection that
        # is secretly a flag tells a session it chose something it did
        # not choose, on a structure with six imaginary modes.
        self.reaction_coordinate_mode = int(reaction_coordinate_mode or 0)
        self.near_zero_frequency_tolerance_cm = (
            NEAR_ZERO_FREQUENCY_TOLERANCE_CM
            if near_zero_frequency_tolerance_cm is None
            else float(near_zero_frequency_tolerance_cm)
        )
        self.rotational_mode = rotational_mode
        # Keep original cm^-1 values for replacing imaginary frequencies
        self.s_freq_cutoff_cm = s_freq_cutoff
        self.h_freq_cutoff_cm = h_freq_cutoff
        self.temperature = temperature
        self.pressure = pressure
        self.use_weighted_mass = use_weighted_mass
        self.m = (
            self.mass
            * units._amu  # converts mass from g/mol to kg/molecule
            # units._amu is same as divide by Avogadro's number then by 1000
            # (g to kg)
        )  # convert the unit of mass of the molecule
        # from amu to kg
        self.T = self.temperature  # temperature in K
        self.P = self.pressure * atm_to_pa  # convert the unit of pressure
        # from atm to Pascal
        self.concentration = concentration
        self.alpha = alpha
        self.s_freq_cutoff = (
            s_freq_cutoff * units._c * 1e2 if s_freq_cutoff else None
        )  # convert the unit of cutoff frequency
        # from cm^-1 to Hz
        self.entropy_method = entropy_method
        self.frequency_scale_factor = float(frequency_scale_factor)
        if (
            not math.isfinite(self.frequency_scale_factor)
            or self.frequency_scale_factor <= 0.0
        ):
            raise ValueError(
                "frequency_scale_factor must be finite and positive"
            )
        self.h_freq_cutoff = (
            h_freq_cutoff * units._c * 1e2 if h_freq_cutoff else None
        )  # convert the unit of cutoff frequency
        # from cm^-1 to Hz
        self.c = (
            self.concentration * 1000 * units._Nav
            if self.concentration is not None
            else None
        )  # convert the unit of concentration
        # from mol/L to Particle/m^3

        self.I = [
            i * (units._amu * (units.Ang / units.m) ** 2)
            for i in self.moments_of_inertia
        ]

        # convert the unit of moments of inertia
        # from amu Ang^2 to kg m^2
        self.Bav = (
            (units._hplanck / self.average_rotational_constant)
            if self.average_rotational_constant
            else None
        )

        # convert the unit of vibrational frequencies from cm^-1 to Hz
        # avoid calling self.cleaned_frequencies twice
        cleaned_frequencies = self.cleaned_frequencies
        self.v = (
            [k * units._c * 1e2 for k in cleaned_frequencies]
            if cleaned_frequencies is not None
            else None
        )

        # Calculate the characteristic vibrational temperature, theta,
        # for each vibrational mode
        self.theta = (
            [units._hplanck * vk / units._k for vk in self.v]
            if self.v is not None
            else None
        )

    @cached_property
    def file_object(self):
        """Open the file and return the file object."""
        program = self.program
        if program == "gaussian":
            output = Gaussian16Output(self.filename)
        elif program == "orca":
            output = ORCAOutput(self.filename)
        elif program == "xtb":
            # The main output identifies the xTB calculation directory;
            # auxiliary files in that directory will provide additional data.
            folder = os.path.dirname(os.path.abspath(self.filename))
            output = XTBOutput(folder)
        elif program == "pyscf":
            # PySCF results are read from the structured sibling .h5 file;
            # the .out log only identifies the program.
            from chemsmart.io.pyscf.output import PySCFOutput

            output = PySCFOutput(self.filename)
        else:
            # can be added in future to parse other file formats
            raise ValueError("Unsupported file format.")
        if not output.normal_termination:
            raise ValueError(
                f"File '{self.filename}' did not terminate normally. "
                "Skipping thermochemistry calculation for this file."
            )
        return output

    @property
    def applied_conventions(self):
        """Return the convention rules in force for this analysis.

        Domain-knowledge skills declare how a quantity is expressed -- its
        standard state, its symmetry number, its sign orientation.  Recording
        them beside the numbers makes the convention in force auditable rather
        than implicit in whichever default happened to apply.

        These are disclosure only.  They do not alter any computed value and
        they carry no accuracy or readiness authority, so a run with skills
        disabled produces identical numbers.
        """

        from chemsmart.agent.skills.conventions import conventions_for_scope

        return tuple(
            item.as_dict() for item in conventions_for_scope("thermochemistry")
        )

    @property
    def jobtype(self):
        if self.program == "orca":
            return self.file_object.thermochemistry_jobtype
        return self.file_object.jobtype

    @property
    def mass(self):
        """Obtain the molecular mass."""
        if self.use_weighted_mass:
            return self.molecule.natural_abundance_weighted_mass
        return self.molecule.most_abundant_mass

    @property
    def moments_of_inertia(self):
        """Obtain the moments of inertia of the molecule along principal axes.

        Direct calculation from molecular structure, since sometimes Gaussian
        output does not print it properly (prints as ***** if values too large)
        """
        if self.use_weighted_mass:
            return self.molecule.moments_of_inertia_weighted_mass
        return self.molecule.moments_of_inertia_most_abundant_mass

    @property
    def average_rotational_constant(self):
        if self.molecule.is_monoatomic:
            return None
        rotational_constants = self.effective_rotational_constants_in_Hz
        if rotational_constants is None or len(rotational_constants) == 0:
            return None
        return sum(rotational_constants) / len(rotational_constants)

    @cached_property
    def geometry_rotational_constants_in_Hz(self):
        if self.molecule.is_monoatomic:
            return None
        rotational_constants = []
        # The axial moment of a linear molecule is zero, and diagonalising
        # the inertia tensor returns it as floating-point noise of either
        # sign. A negative one became a huge negative rotational constant,
        # the rotor was taken for nonlinear, and the rotational entropy was
        # the square root of a negative number: every PySCF CO2 and H2 of
        # oracle O1 (CUHK 2149909) and xTB's H2 derived a NaN Gibbs
        # energy. A moment that is noise beside the largest is zero.
        largest = max((abs(float(moment)) for moment in self.I), default=0.0)
        for moment in self.I:
            if moment <= 1e-10 * largest:
                rotational_constants.append(np.inf)
            else:
                rotational_constants.append(
                    units._hplanck / (8 * np.pi**2 * moment)
                )
        return np.array(rotational_constants, dtype=float)

    @cached_property
    def gaussian_rotational_constants_in_Hz(self):
        if not isinstance(self.file_object, Gaussian16Output):
            return None
        all_constants = self.file_object.all_rotational_constants(
            mode="gaussian"
        )
        if not all_constants:
            return None
        return np.asarray(all_constants[-1], dtype=float)

    @cached_property
    def effective_rotational_constants_in_Hz(self):
        if self.molecule.is_monoatomic:
            return None
        if self.rotational_mode == "physical":
            return clean_rotational_constants_by_geometry(
                self.geometry_rotational_constants_in_Hz,
                mode="physical",
            )
        if self.rotational_mode == "gaussian":
            if self.gaussian_rotational_constants_in_Hz is None:
                logger.warning(
                    "Gaussian rotational constants are unavailable; using "
                    "geometry-derived rotational constants instead."
                )
                return np.asarray(
                    self.geometry_rotational_constants_in_Hz, dtype=float
                )
            if np.isinf(self.gaussian_rotational_constants_in_Hz).any():
                logger.warning(
                    "Cannot recompute Gaussian-style nonlinear rotational "
                    "thermochemistry from printed rotational constants "
                    "because Gaussian overflowed one or more values as "
                    "********."
                )
                logger.info(
                    "Recomputing Gaussian-mode rotational constants from "
                    "molecular geometry."
                )
                return np.asarray(
                    self.geometry_rotational_constants_in_Hz, dtype=float
                )
            return np.asarray(
                self.gaussian_rotational_constants_in_Hz, dtype=float
            )
        raise ValueError(
            f"Unsupported rotational thermochemistry mode: "
            f"{self.rotational_mode!r}."
        )

    @cached_property
    def effective_rotational_temperatures(self):
        rotational_constants = self.effective_rotational_constants_in_Hz
        if rotational_constants is None:
            return None
        rotational_temperatures = []
        for rotational_constant in rotational_constants:
            if np.isinf(rotational_constant):
                rotational_temperatures.append(np.inf)
            else:
                rotational_temperatures.append(
                    units._hplanck * rotational_constant / units._k
                )
        return np.array(rotational_temperatures, dtype=float)

    @property
    def is_linear_rotor(self):
        rotational_constants = self.effective_rotational_constants_in_Hz
        return (
            rotational_constants is not None and len(rotational_constants) == 1
        )

    @property
    def program_rotational_symmetry_number(self):
        """The rotational symmetry number the program itself stated.

        ORCA, Gaussian and xTB print one from their own symmetry detection;
        PySCF's is derived from the point group PySCF detected.  Kept as
        evidence beside the host's count, never used by the formulas.
        """
        if self.program == "orca":
            section = self.file_object._last_complete_thermochemistry_section
            if (
                section is not None
                and section.rotational_symmetry_number is not None
            ):
                return section.rotational_symmetry_number
        return getattr(self.file_object, "rotational_symmetry_number", None)

    @cached_property
    def rotational_symmetry_number(self):
        """The rotational symmetry number, counted by the host.

        Counted from the geometry the frequencies belong to, so one
        structure has one number whichever program computed its Hessian;
        see :func:`rotational_symmetry_number_from_geometry`.
        """
        if self.molecule.is_monoatomic:
            return 1
        sigma, _rotations = rotational_symmetry_number_from_geometry(
            self.molecule.chemical_symbols,
            self.molecule.positions,
            self.molecule.most_abundant_masses,
            linear=self.is_linear_rotor,
        )
        return sigma

    @property
    def convention_statements(self):
        """What this derivation decided that a program may decide otherwise.

        Stated beside the numbers a receipt carries, because each one moves
        a Gibbs energy by an amount a reader cannot recover from the
        number: the symmetry number by RT ln(sigma), the rotor treatment of
        a quasi-linear molecule by kcal/mol.
        """

        statements = []
        if self.molecule.is_monoatomic:
            return (
                "monoatomic: no rotational or vibrational partition",
                "monoatomic electronic partition function: the spin "
                "multiplicity 2S+1 alone; the orbital degeneracy and "
                "spin-orbit levels of an open-shell atomic term (2P, 3P) "
                "are not included",
            )
        sigma = self.rotational_symmetry_number
        text = (
            f"rotational symmetry number {sigma}, counted by the host from "
            "the geometry the frequencies belong to (proper rotations "
            "mapping it onto itself within "
            f"{ROTATIONAL_SYMMETRY_TOLERANCE_ANGSTROM:g} A)"
        )
        try:
            printed = self.program_rotational_symmetry_number
        except Exception:  # noqa: BLE001 - evidence only, never a formula
            printed = None
        if printed is not None and int(printed) != int(sigma):
            text += f"; the program itself stated {int(printed)}"
        statements.append(text)
        if self.is_linear_rotor:
            padded = self.quasi_linear_padded_mode_cm1
            if padded is not None:
                statements.append(
                    "quasi-linear structure treated as a linear rotor: two "
                    "rotational degrees of freedom, and the lowest bending "
                    f"mode ({padded:.1f} cm^-1) supplied twice for the "
                    "missing degenerate partner"
                )
            else:
                statements.append("linear rotor: two rotational degrees")
        return tuple(statements)

    @property
    def quasi_linear_padded_mode_cm1(self):
        """The bending mode duplicated for a quasi-linear rotor, or None."""

        if self.vibrational_frequencies is None:
            return None
        if not (self.rotational_mode == "physical" and self.is_linear_rotor):
            return None
        if getattr(self, "projected_frequencies", None) is not None:
            return None
        return _quasi_linear_padding(
            [
                float(frequency) * float(self.frequency_scale_factor)
                for frequency in self.vibrational_frequencies
            ],
            self.molecule.num_atoms,
        )

    @property
    def vibrational_frequencies(self):
        """Obtain the vibrational frequencies of the molecule.

        ``None`` means the result carries no Hessian, which leaves a
        molecule without thermochemistry.  An atom has no vibrational (or
        rotational) degree of freedom, so it has none to be missing: its
        partition function is translational and electronic, from its
        energy, mass and multiplicity alone, and a single point is all it
        needs.  A live goal asked for an H atom's free energy from an ORCA
        single point and was refused as an unconverged optimisation (R10
        Q9 G1, CUHK Slurm 2150438).
        """
        projected = getattr(self, "projected_frequencies", None)
        if projected is not None:
            return list(projected)
        if self.molecule.is_monoatomic:
            return []
        if self.program == "orca":
            # ``frequencies`` is None when ORCA printed no table for the
            # Hessian its last thermochemistry block describes (a ScanTS
            # with Freq prints one for scan point 1 only; R10 Q31).
            section = self.file_object._last_complete_thermochemistry_section
            if section is None or section.frequencies is None:
                return None
            return [
                frequency
                for frequency in section.frequencies
                if frequency != 0.0
            ]
        if not self.file_object.freq:
            return None
        return self.file_object.vibrational_frequencies

    @property
    def real_frequencies(self):
        """Obtain the real vibrational frequencies of the molecule."""
        if self.vibrational_frequencies is None:
            return None
        return [k for k in self.vibrational_frequencies if k >= 0.0]

    @property
    def imaginary_frequencies(self):
        """Obtain the genuine imaginary vibrational frequencies.

        A mode is imaginary when it lies below
        ``-near_zero_frequency_tolerance_cm``.  A value a few wavenumbers on
        the wrong side of zero is numerical noise in one of the six modes that
        should be exactly zero, not a reaction coordinate, and calling it
        imaginary would contradict the program that produced the Hessian.
        """
        if self.vibrational_frequencies is None:
            return None
        tolerance = abs(self.near_zero_frequency_tolerance_cm)
        return [k for k in self.vibrational_frequencies if k < -tolerance]

    @property
    def near_zero_mode_count(self):
        """How many real modes lie below the near-zero tolerance.

        A harmonic oscillator is not a meaningful description of a mode of a
        few wavenumbers: its entropy diverges as the frequency goes to zero, so
        one such mode can contribute more to a free-energy difference than the
        electronic structure being compared.  The count is reported as typed
        evidence rather than silently corrected, because damping those modes is
        a convention choice the scientist owns -- ``entropy_method`` already
        offers the quasi-harmonic treatments.
        """

        if self.vibrational_frequencies is None:
            return None
        tolerance = abs(self.near_zero_frequency_tolerance_cm)
        return sum(
            1
            for frequency in self.vibrational_frequencies
            if -tolerance < frequency < tolerance
        )

    @property
    def cleaned_frequencies(self):
        """Clean up vibrational frequencies for thermochemical calculations.

        Frequencies returned by this property remain in cm^-1.

        When rotational_mode="physical" and the molecule is treated as a linear
        rotor but has fewer than 3N-5 vibrational frequencies (quasi-linear case),
        the lowest positive frequency is duplicated to supply the missing
        degenerate bending mode(s).

        If self.check_imaginary_frequencies is True:
            - TS jobs must have exactly one imaginary frequency.
            - Non-TS jobs must have no imaginary frequencies.

        If self.check_imaginary_frequencies is False:
            - TS jobs remove the first imaginary frequency as the reaction coordinate.
            - Extra imaginary frequencies are replaced by a positive cutoff.
            - Non-TS jobs replace all imaginary frequencies by a positive cutoff.

        The replacement cutoff is:
            - s_freq_cutoff if provided
            - otherwise h_freq_cutoff if provided
            - otherwise 100.0 cm^-1
        """
        if self.vibrational_frequencies is None:
            return None

        frequencies = [
            float(frequency)
            * float(getattr(self, "frequency_scale_factor", 1.0))
            for frequency in self.vibrational_frequencies
        ]

        # A projected spectrum is already the set of modes the partition
        # functions count: its held coordinates are gone, so nothing is
        # padded and no mode is removed as a reaction coordinate below.
        projected = getattr(self, "projected_frequencies", None) is not None

        # Quasi-linear correction: Gaussian gives 3N-6 frequencies for
        # non-linear molecules; pad to 3N-5 for linear treatment.
        if (
            self.rotational_mode == "physical"
            and self.is_linear_rotor
            and not projected
        ):
            lowest = _quasi_linear_padding(
                frequencies, self.molecule.num_atoms
            )
            if lowest is not None:
                frequencies.append(lowest)
                logger.info(
                    f"Quasi-linear molecule: padded one degenerate bending "
                    f"mode at {lowest:.1f} cm^-1 for linear treatment."
                )

        imaginary_indices = [
            i for i, freq in enumerate(frequencies) if freq < 0.0
        ]
        # Only a mode well below zero is a real imaginary mode, on the same
        # definition as :attr:`imaginary_frequencies`.  The rest are near-zero
        # noise, still replaced by the cutoff below so the partition functions
        # stay defined, but never a reason to refuse the result.
        genuine_imaginary_indices = [
            i
            for i, freq in enumerate(frequencies)
            if freq < -abs(self.near_zero_frequency_tolerance_cm)
        ]

        if not imaginary_indices:
            return frequencies

        # IMPORTANT:
        # cleaned_frequencies is still in cm^-1.
        # Do not use self.s_freq_cutoff/self.h_freq_cutoff here because those
        # have already been converted to Hz.
        if self.s_freq_cutoff_cm is not None:
            freq_cutoff = self.s_freq_cutoff_cm
        elif self.h_freq_cutoff_cm is not None:
            freq_cutoff = self.h_freq_cutoff_cm
        else:
            freq_cutoff = 100.0

        # check against non-positive cutoff value
        # before using it to replace imaginary frequencies
        if freq_cutoff <= 0.0:
            raise ValueError(
                f"Imaginary-frequency replacement cutoff must be positive. "
                f"Got {freq_cutoff} cm^-1."
            )

        # A mode the session named as the reaction coordinate is removed
        # whatever the program's job label says. The branch below used to
        # be reached by the label alone, so a saddle an ``opt`` had landed
        # on kept its named mode as the 100 cm^-1 cutoff while the receipt
        # said the mode was "excluded from the vibrational partition
        # function": ORCA's trans H2O2 saddle (R10 Q21 g1-hooh opt180,
        # CUHK 2153623) carried ZPE 0.026027 Eh = its five real modes
        # plus 50 cm^-1, a free energy 0.43 kcal/mol below the same saddle
        # found by OptTS (Q24 g2r: dG(trans) -0.079 against 0.345).
        if (
            self.jobtype == "ts" or self.reaction_coordinate_mode
        ) and not projected:
            # Valid TS: exactly one genuine imaginary frequency.
            # Remove it from thermochemistry.  Any remaining negative is
            # near-zero noise by construction -- a genuine second imaginary
            # mode would have made this an invalid TS -- and it still has to be
            # replaced by the cutoff, because the partition functions take the
            # logarithm of 1 - exp(-theta/T) and a negative frequency makes
            # that undefined.
            if len(genuine_imaginary_indices) == 1 and (
                not self.reaction_coordinate_mode
                or self.reaction_coordinate_mode - 1
                == genuine_imaginary_indices[0]
            ):
                reaction_coordinate_index = genuine_imaginary_indices[0]
                return [
                    freq_cutoff if freq < 0.0 else freq
                    for i, freq in enumerate(frequencies)
                    if i != reaction_coordinate_index
                ]

            # Invalid TS: not exactly one genuine imaginary frequency.
            if self.check_imaginary_frequencies and genuine_imaginary_indices:
                raise ValueError(
                    f"!! ERROR: Detected multiple imaginary frequencies in "
                    f"TS calculation for {self.filename}. Only one "
                    f"imaginary frequency is allowed for a valid TS. "
                    f"Please re-optimize the geometry to locate a true TS."
                )

            # Permissive mode:
            # remove first imaginary frequency as reaction coordinate;
            # replace all remaining imaginary frequencies by cutoff.
            available = genuine_imaginary_indices or imaginary_indices
            if self.reaction_coordinate_mode:
                wanted = self.reaction_coordinate_mode - 1
                if wanted < 0 or wanted >= len(frequencies):
                    raise ValueError(
                        f"reaction_coordinate_mode "
                        f"{self.reaction_coordinate_mode} is not a mode "
                        f"this result printed ({len(frequencies)} modes)"
                    )
                if wanted not in available:
                    raise ValueError(
                        f"reaction_coordinate_mode "
                        f"{self.reaction_coordinate_mode} names a real "
                        "mode; the reaction coordinate must be one of the "
                        "imaginary modes this result printed, which are "
                        f"{[index + 1 for index in available]}"
                    )
                reaction_coordinate_index = wanted
            else:
                reaction_coordinate_index = available[0]

            return [
                freq_cutoff if freq < 0.0 else freq
                for i, freq in enumerate(frequencies)
                if i != reaction_coordinate_index
            ]

        # Non-TS jobs: a genuine imaginary frequency is invalid in strict
        # mode; near-zero noise is replaced by the cutoff instead.
        if self.check_imaginary_frequencies and genuine_imaginary_indices:
            raise ValueError(
                f"!! ERROR: Detected imaginary frequencies in geometry "
                f"optimization for {self.filename}. A valid optimized "
                f"geometry should not contain imaginary frequencies. "
                f"Please re-optimize the geometry to locate a true minimum."
            )

        # Permissive mode:
        # replace all imaginary frequencies by cutoff.
        return [freq_cutoff if freq < 0.0 else freq for freq in frequencies]

    @property
    def electronic_energy(self):
        """Obtain the total electronic energy in J mol^-1."""
        if self.program == "orca":
            energy = self.file_object.thermochemistry_electronic_energy
        else:
            energy = self.file_object.energies[-1]
        return energy * hartree_to_joules * units._Nav

    @property
    def multiplicity(self):
        """Obtain the multiplicity of the molecule."""
        if self.program == "orca":
            return self.file_object.thermochemistry_multiplicity
        return self.file_object.multiplicity

    @property
    def translational_partition_function(self):
        """Obtain the translational partition function.

        Formula in gas phase:
            q_t = (2 * pi * m * k_B * T / h^2)^(3/2) * (k_B * T / P)
        In solution, uses concentration instead of pressure. Formula:
            q_t = (2 * pi * m * k_B * T / h^2)^(3/2) * (1 / c)
        where:
            m = mass of the molecule (kg)
            k_B = Boltzmann constant (J K^-1)
            T = temperature (K)
            h = Planck constant (J s)
            P = pressure of the system (Pa)
            c = pressure of the system (m^-3)
        """
        if self.c is not None:
            return (
                2 * np.pi * self.m * units._k * self.T / units._hplanck**2
            ) ** (3 / 2) * (1 / self.c)
        else:
            return (
                2 * np.pi * self.m * units._k * self.T / units._hplanck**2
            ) ** (3 / 2) * (units._k * self.T / self.P)

    @property
    def translational_entropy(self):
        """Obtain the translational entropy in J mol^-1 K^-1.
        Formula:
            S_t = R * [ln(q_t) + 1 + 3/2]
        where:
            R = gas constant (J mol^-1 K^-1)
        """
        return R * (np.log(self.translational_partition_function) + 1 + 3 / 2)

    @property
    def translational_internal_energy(self):
        """Obtain the translational internal energy J mol^-1.

        Same for all types of molecules, whether linear, non-linear or
        monoatomic.
        Formula:
            E_t = 3/2 * R * T
        """
        return 3 / 2 * R * self.T

    @property
    def translational_heat_capacity(self):
        """Obtain the constant volume heat capacity in J mol^-1 K^-1.
        Formula:
            C_t = 3/2 * R
        """
        return 3 / 2 * R

    @property
    def electronic_partition_function(self):
        """Obtain the electronic partition function.

        Gaussian assumes first electronic excitation energy is much greater
        than k_B * T. Thus, first and higher excited states assumed
        inaccessible at any temperature. Further, energy of ground state is
        set to zero.
        Formula:
            q_e = ω_0
        where:
            ω_0 = degeneracy of the ground state,
            which is simply the electronic spin multiplicity of the molecule.
        """
        return self.multiplicity

    @property
    def electronic_entropy(self):
        """Obtain the electronic entropy in J mol^-1 K^-1.
        Formula:
            S_e = R * ln(q_e)
        """
        return R * np.log(self.electronic_partition_function)

    @property
    def electronic_internal_energy(self):
        """The internal thermal energy due to electronic motion is zero.

        Since there are no temperature dependent terms in electronic
        partition function
        """
        return 0

    @property
    def electronic_heat_capacity(self):
        r"""The electronic heat capacity is zero for all types of molecules.

        C_V = (\partial U_e / \partial T)_V = 0
        """
        return 0

    def _calculate_rotational_partition_function_for_linear_molecule(self):
        """Calculate the rotational partition function of a linear molecule.

        Formula:
            q_r = 1 / σ_r * (T / Θ_r)
        where:
            σ_r = symmetry number for rotation
            Θ_r = h^2 / (8 * pi^2 * I * k_B)
            I = moment of inertia (kg m^2)
        """
        theta_r = self.effective_rotational_temperatures[0]
        logger.debug(f"Rotational temperature Θ_r = {theta_r:.4f} K")
        return (1 / self.rotational_symmetry_number) * (self.T / theta_r)

    def _calculate_rotational_partition_function_for_nonlinear_polyatomic_molecule(
        self,
    ):
        """Calculate the rotational partition
        function of a nonlinear polyatomic molecule.

        Formula:
            q_r = pi^(1/2) / σ_r * (T^(3/2) / (Θ_r,x * Θ_r,y * Θ_r,z)^(1/2))
        where:
            σ_r = symmetry number for rotation
            Θ_r,i = h^2 / (8 * pi^2 * I_i * k_B) for i = x, y, z
        """
        theta_ri = self.effective_rotational_temperatures
        return (
            np.pi ** (1 / 2)
            / self.rotational_symmetry_number
            * (self.T ** (3 / 2) / np.prod(theta_ri) ** (1 / 2))
        )

    @property
    def rotational_partition_function(self):
        """Obtain the rotational partition function.

        For a single atom, q_r = 1. Since q_r does not depend on temperature,
        contribution of rotation to internal thermal energy, heat capacity and
        entropy are all identically zero.
        """
        if self.molecule.is_monoatomic:
            return 1
        elif self.is_linear_rotor:
            logger.debug(
                "Calculate rotational partition function for linear molecule."
            )
            return (
                self._calculate_rotational_partition_function_for_linear_molecule()
            )
        else:
            logger.debug(
                "Calculate rotational partition function for non-linear molecule."
            )
            return (
                self._calculate_rotational_partition_function_for_nonlinear_polyatomic_molecule()
            )

    @property
    def rotational_entropy(self):
        """Obtain the rotational entropy in J mol^-1 K^-1.

        Formula:
            S_r = 0 for monoatomic molecules
                = R * (ln(q_r) + 1) for linear molecules
                = R * (ln(q_r) + 3/2) for nonlinear polyatomic molecules
        """
        if self.molecule.is_monoatomic:
            return 0
        elif self.is_linear_rotor:
            logger.debug("Calculate rotational entropy for linear molecule.")
            return R * (np.log(self.rotational_partition_function) + 1)
        else:
            logger.debug(
                "Calculate rotational entropy for non-linear molecule."
            )
            return R * (np.log(self.rotational_partition_function) + 3 / 2)

    @property
    def rotational_internal_energy(self):
        """Obtain the rotational internal energy J mol^-1.
        Formula:
            E_r = 0 for monoatomic molecules
                = R * T for linear molecules
                = 3/2 * R * T for nonlinear polyatomic molecules
        """
        if self.molecule.is_monoatomic:
            return 0
        elif self.is_linear_rotor:
            return R * self.T
        else:
            return 3 / 2 * R * self.T

    @property
    def rotational_heat_capacity(self):
        """Obtain the rotational contribution
        to the heat capacity in J mol^-1 K^-1.

        Formula:
            C_r = 0 for monoatomic molecules
                = R for linear molecules
                = 3/2 * R for nonlinear polyatomic molecules
        """
        if self.molecule.is_monoatomic:
            return 0
        elif self.is_linear_rotor:
            return R
        else:
            return 3 / 2 * R

    @property
    def vibrational_partition_function_by_mode_bot(self):
        """
        Obtain the partition function for each vibrational mode.
        The zero reference point is the bottom of the well (BOT).
        Formula:
            q_v,K = exp(-Θ_v,K / (2 * T)) / (1 - exp(-Θ_v,K / T))
        where:
            Θ_v,K = h * v_K / k_B
            v_K = vibrational frequency for mode K (Hz)
        """
        return (
            [
                math.exp(-t / (2 * self.T)) / (1 - math.exp(-t / self.T))
                for t in self.theta
            ]
            if self.theta is not None
            else None
        )

    @property
    def vibrational_partition_function_bot(self):
        """Obtain the overall vibrational partition function with BOT.
        Formula:
            q_v = q_1 * q_2 * ... * q_vDOF
        where:
            vDOF = vibrational degrees of freedom
                 = 3 * N - 5 for linear molecules
                 = 3 * N - 6 for nonlinear polyatomic molecules
            N = number of atoms in molecule
        """
        if self.vibrational_partition_function_by_mode_bot is None:
            return None
        return np.prod(self.vibrational_partition_function_by_mode_bot)

    @property
    def vibrational_partition_function_by_mode_v0(self):
        """
        Obtain the partition function for each vibrational mode.
        The zero reference point is the first vibrational energy level (V=0).
        Formula:
            q_v,K = 1 / (1 - exp(-Θ_v,K / T))
        """
        return (
            [1 / (1 - math.exp(-t / self.T)) for t in self.theta]
            if self.theta is not None
            else None
        )

    @property
    def vibrational_partition_function_v0(self):
        """Obtain the overall vibrational partition function with V=0."""
        if self.vibrational_partition_function_by_mode_v0 is None:
            return None
        return np.prod(self.vibrational_partition_function_by_mode_v0)

    @property
    def vibrational_entropy(self):
        """Obtain the vibrational entropy in J mol^-1 K^-1.

        Formula:
            S_v = R * Σ((Θ_v,K / T) / (exp(Θ_v,K / T) - 1)
                      - ln(1 - exp(-Θ_v,K / T)))
        """
        if self.theta is None:
            return None
        s = [
            (t / self.T) / (math.exp(t / self.T) - 1)
            - np.log(1 - math.exp(-t / self.T))
            for t in self.theta
        ]
        return R * sum(s)

    @cached_property
    def internal_rotor_terms(self):
        """Summed ``(q, S, U, Cv, ZPE)`` of the hindered rotors at T.

        S and Cv in J/(K mol), U and ZPE in J/mol from each potential's
        minimum; ``q`` is the product of the rotor partition functions on
        that zero.  All zero (and q one) when no rotor is treated.
        """

        q, entropy, energy, heat_capacity, zero_point = 1.0, 0.0, 0.0, 0.0, 0.0
        for rotor in getattr(self, "internal_rotors", ()) or ():
            rq, rs, ru, rc = rotor.thermodynamics(self.T)
            q *= rq
            entropy += rs
            energy += ru
            heat_capacity += rc
            zero_point += rotor.zero_point_cm1 * CM1_TO_J_PER_MOL
        return q, entropy, energy, heat_capacity, zero_point

    @property
    def zero_point_energy(self):
        """Obtain the vibrational zero-point energy (ZPE) in J mol^-1.
        Formula:
            E_ZPE = R * Σ(1/2 * Θ_v,K)
        plus each hindered rotor's lowest level above its potential minimum.
        """
        if self.theta is None:
            return None
        u = [1 / 2 * t for t in self.theta]
        return R * sum(u) + self.internal_rotor_terms[4]

    @property
    def vibrational_internal_energy(self):
        """Obtain the vibrational internal energy in J mol^-1.
        Formula:
            E_v = R * Σ(Θ_v,K * (1/2 + 1 / (exp(Θ_v,K / T) - 1)))
        """
        if self.theta is None:
            return None
        u = [t * (1 / 2 + 1 / (math.exp(t / self.T) - 1)) for t in self.theta]
        return R * sum(u)

    @property
    def vibrational_heat_capacity(self):
        """Obtain the vibrational contribution
        to the heat capacity in J mol^-1 K^-1.

        Formula:
            C_v = R * Σ(exp(-Θ_v,K / T) *
                       ((Θ_v,K / T) / (exp(-Θ_v,K / T) - 1))^2)
        """
        if self.theta is None:
            return None
        c = [
            math.exp(-t / self.T)
            * ((t / self.T) / (math.exp(-t / self.T) - 1)) ** 2
            for t in self.theta
        ]
        return R * sum(c)

    @property
    def total_partition_function(self):
        """Obtain the total partition function.
        Formula:
            q_tot = q_t * q_r * q_v * q_e
        """
        if self.vibrational_partition_function_v0 is None:
            return None
        total = (
            self.translational_partition_function
            * self.rotational_partition_function
            * self.electronic_partition_function
            * self.vibrational_partition_function_v0
        )
        rotors = getattr(self, "internal_rotors", ()) or ()
        if rotors:
            # The v=0 convention: each rotor counted from its lowest level.
            kt = BOLTZMANN_CM1_PER_K * self.T
            for rotor in rotors:
                total *= rotor.thermodynamics(self.T)[0] * math.exp(
                    rotor.zero_point_cm1 / kt
                )
        return total

    @property
    def total_entropy(self):
        """Obtain the total entropy in J mol^-1 K^-1.
        Formula:
            S_tot = S_t + S_r + S_v + S_e (+ S of each hindered rotor)
        """
        if self.vibrational_entropy is None:
            return None
        return (
            self.translational_entropy
            + self.rotational_entropy
            + self.electronic_entropy
            + self.vibrational_entropy
            + self.internal_rotor_terms[1]
        )

    @property
    def total_internal_energy(self):
        """Obtain the total internal energy in J mol^-1.
        Formula:
            E_tot = E_t + E_r + E_v + E_e (+ U of each hindered rotor)
        """
        if self.vibrational_internal_energy is None:
            return None
        return (
            self.translational_internal_energy
            + self.rotational_internal_energy
            + self.electronic_internal_energy
            + self.vibrational_internal_energy
            + self.internal_rotor_terms[2]
        )

    @property
    def total_heat_capacity(self):
        """Obtain the total heat capacity in J mol^-1 K^-1.
        Formula:
            C_tot = C_t + C_r + C_v + C_e (+ Cv of each hindered rotor)
        """
        if self.vibrational_heat_capacity is None:
            return None
        return (
            self.translational_heat_capacity
            + self.rotational_heat_capacity
            + self.electronic_heat_capacity
            + self.vibrational_heat_capacity
            + self.internal_rotor_terms[3]
        )

    def _calculate_damping_function(self, freq_cutoff):
        """Calculate the damping function of Head-Gordon.

        Interpolates between the RRHO and the free rotor entropy.
        Formula:
            w(v_K) = 1 / (1 + (v_0 / v_K)^α)
        where:
            v_0 = cutoff frequency in Hz, default is 100 cm^-1
                  (already converted to Hz)
            α = dimensionless interpolator exponent, default value is 4
        """
        if freq_cutoff is None or self.v is None:
            return None
        damp = [1 / (1 + (freq_cutoff / vk) ** self.alpha) for vk in self.v]
        return damp

    @property
    def entropy_damping_function(self):
        return self._calculate_damping_function(self.s_freq_cutoff)

    @property
    def enthalpy_damping_function(self):
        return self._calculate_damping_function(self.h_freq_cutoff)

    @property
    def free_rotor_entropy(self):
        """Obtain the free rotor entropy in J mol^-1 K^-1.

        Used to treat low frequency modes below cutoff.
        Formula:
            S_R,K = R * (1/2 + ln((8 * pi^3 * u'_K * k_B * T / h^2)^(1/2)))
        where:
            u'_K = u_K * B_av / (u_K + B_av)
            u_K = h / (8 * pi^2 * v_K)
            B_av = average molecular moment of inertia (kg m^2)
        """
        if self.v is None:
            return None
        bav = self.Bav
        if bav is None:
            return []
        mu = [units._hplanck / (8 * np.pi**2 * vk) for vk in self.v]
        mu_prime = [mu_k * bav / (mu_k + bav) for mu_k in mu]
        entropy = [
            R
            * (
                1 / 2
                + np.log(
                    (
                        8
                        * np.pi**3
                        * mu_prime_k
                        * units._k
                        * self.T
                        / units._hplanck**2
                    )
                    ** (1 / 2)
                )
            )
            for mu_prime_k in mu_prime
        ]
        return entropy

    @property
    def rrho_entropy(self):
        """Obtain Harmonic Oscillator vibrational entropy in J mol^-1 K^-1.

        (within RRHO approximation)
        Formula:
            S^rrho_v,K = R * [(Θ_v,K / T) / (exp(Θ_v,K / T) - 1)
                             - ln(1 - exp(-Θ_v,K / T))]
        """
        if self.theta is None:
            return None
        entropy = [
            R
            * (
                (t / self.T) / (math.exp(t / self.T) - 1)
                - np.log(1 - math.exp(-t / self.T))
            )
            for t in self.theta
        ]
        return entropy

    @property
    def qrrho_vibrational_entropy(self):
        """Obtain vibrational entropy with quasi-RRHO approximation.

        In J mol^-1 K^-1.
        Grimme's Formula:
            S^qrrho_v = Σ(w(v_K) * S^rrho_v,K + (1 - w(v_K)) * S_R,K)
        Truhlar's Formula:
            S^qrrho_v = ΣS^rrho_v,K if v_k > v_cutoff
                      = ΣS^rrho_v,cutoff if v_k <= v_cutoff
        """
        if self.s_freq_cutoff is None or self.v is None:
            return None
        vib_entropy = []
        if self.entropy_method == "grimme":
            assert len(self.v) == len(self.entropy_damping_function), (
                f"The length of vibrational frequencies and damping function "
                f"must be equal.\n"
                f"The damping function is {self.entropy_damping_function}.\n"
            )
            for j in range(0, len(self.v)):
                vib_entropy.append(
                    self.entropy_damping_function[j] * self.rrho_entropy[j]
                    + (1 - self.entropy_damping_function[j])
                    * self.free_rotor_entropy[j]
                )
        elif self.entropy_method == "truhlar":
            v_cutoff = self.s_freq_cutoff
            theta_cutoff = units._hplanck * v_cutoff / units._k
            rrho_entropy_cutoff = R * (
                (theta_cutoff / self.T) / (math.exp(theta_cutoff / self.T) - 1)
                - np.log(1 - math.exp(-theta_cutoff / self.T))
            )
            for j in range(0, len(self.v)):
                vib_entropy.append(
                    self.rrho_entropy[j]
                    if self.v[j] > v_cutoff
                    else rrho_entropy_cutoff
                )
        return sum(vib_entropy)

    @property
    def rrho_internal_energy(self):
        """Obtain the Harmonic Oscillator (within RRHO approximation)
         vibrational internal energy in J mol^-1.
        Formula:
            E^rrho_v,K = R * Θ_v,K * (1/2 + 1 / (exp(Θ_v,K / T) - 1))
        """
        if self.theta is None:
            return None
        energy = [
            R * t * (1 / 2 + 1 / (math.exp(t / self.T) - 1))
            for t in self.theta
        ]
        return energy

    @property
    def qrrho_vibrational_internal_energy(self):
        """Obtain vibrational internal energy with quasi-RRHO approximation.

        Head-Gordon's method, in J mol^-1.
        Formula:
            E^qrrho_v = Σ(w(v_K) * E^rrho_v,K + (1 - w(v_K)) * 1/2 * R * T)
        """
        if self.h_freq_cutoff is None or self.v is None:
            return None
        vib_energies = []
        assert len(self.v) == len(self.enthalpy_damping_function), (
            f"The length of vibrational frequencies and damping function "
            f"must be equal.\n"
            f"The damping function is {self.enthalpy_damping_function}.\n"
        )
        for j in range(0, len(self.v)):
            vib_energies.append(
                self.enthalpy_damping_function[j]
                * self.rrho_internal_energy[j]
                + (1 - self.enthalpy_damping_function[j]) * 1 / 2 * R * self.T
            )
        return sum(vib_energies)

    @property
    def enthalpy(self):
        """Obtain the enthalpy in J mol^-1.
        Formula:
            H = E0 + E_tot + R * T
        where:
            E0 = the total electronic energy (J mol^-1)
        """
        if self.total_internal_energy is None:
            return None
        return self.electronic_energy + self.total_internal_energy + R * self.T

    @property
    def qrrho_total_entropy(self):
        """Obtain the quasi-RRHO total entropy in J mol^-1 K^-1.
        Formula:
            S^qrrho_tot = S_t + S_r + S^qrrho_v + S_e
        """
        if self.qrrho_vibrational_entropy is None:
            return None
        return (
            self.translational_entropy
            + self.rotational_entropy
            + self.electronic_entropy
            + self.qrrho_vibrational_entropy
            + self.internal_rotor_terms[1]
        )

    @property
    def entropy_times_temperature(self):
        """Obtain the total entropy times temperature in J mol^-1.
        Formula:
            T * S_tot
        """
        if self.total_entropy is None:
            return None
        return self.T * self.total_entropy

    @property
    def qrrho_entropy_times_temperature(self):
        """Obtain the quasi-RRHO entropy times temperature in J mol^-1.
        Formula:
            T * S^qrrho_tot
        """
        if self.qrrho_total_entropy is None:
            return None
        return self.T * self.qrrho_total_entropy

    @property
    def gibbs_free_energy(self):
        """Obtain the Gibbs free energy in J mol^-1 .
        Formula:
            G = H - T * S_tot
        """
        if self.entropy_times_temperature is None or self.enthalpy is None:
            return None
        return self.enthalpy - self.entropy_times_temperature

    @property
    def qrrho_total_internal_energy(self):
        """Obtain the quasi-RRHO total internal energy in J mol^-1.
        Formula:
            E^qrrho_tot = E_t + E_r + E^qrrho_v + E_e
        """
        if self.qrrho_vibrational_internal_energy is None:
            return None
        return (
            self.translational_internal_energy
            + self.rotational_internal_energy
            + self.electronic_internal_energy
            + self.qrrho_vibrational_internal_energy
            + self.internal_rotor_terms[2]
        )

    @property
    def qrrho_enthalpy(self):
        """Obtain the quasi-RRHO enthalpy in J mol^-1.
        Formula:
            H^qrrho = E0 + H^qrrho_corr
                    = E0 + E^qrrho_tot + R * T
        where:
            E0 = the total electronic energy (J mol^-1)
        """
        if self.qrrho_total_internal_energy is None:
            return None
        return (
            self.electronic_energy
            + self.qrrho_total_internal_energy
            + R * self.T
        )

    @property
    def qrrho_gibbs_free_energy(self):
        """Obtain the Gibbs free energy in J mol^-1.

        Uses quasi-RRHO corrections to both entropy and enthalpy.
        Formula:
            G^qrrho_q = H^qrrho - T * S^qrrho_tot
        """
        if (
            self.qrrho_enthalpy is None
            or self.qrrho_entropy_times_temperature is None
        ):
            return None
        return self.qrrho_enthalpy - self.qrrho_entropy_times_temperature

    @property
    def qrrho_gibbs_free_energy_qs(self):
        """Obtain the Gibbs free energy in J mol^-1.

        Uses quasi-RRHO correction to entropy only.
        Formula:
            G^qrrho_qs = H - T * S^qrrho_tot
        """
        if (
            self.qrrho_entropy_times_temperature is None
            or self.enthalpy is None
        ):
            return None
        return self.enthalpy - self.qrrho_entropy_times_temperature

    @property
    def qrrho_gibbs_free_energy_qh(self):
        """Obtain the Gibbs free energy in J mol^-1.

        Uses quasi-RRHO correction to enthalpy only.
        Formula:
            G^qrrho_qh = H^qrrho - T * S_tot
        """
        if (
            self.qrrho_enthalpy is None
            or self.entropy_times_temperature is None
        ):
            return None
        return self.qrrho_enthalpy - self.entropy_times_temperature

    def compute_thermochemistry(self):
        """Compute Boltzmann-averaged properties."""
        logger.debug(f"Computing thermochemistry for {self.filename}...")
        return self._compute_thermochemistry()

    def _compute_thermochemistry(self):
        """Calculate thermochemical properties based on the parsed data."""
        # Check for imaginary frequencies if required
        if self.check_imaginary_frequencies:
            logger.debug("Checking imaginary frequencies.")
            self.check_frequencies()
        # convert energies to specified units
        logger.debug(f"Converting to energy units: {self.energy_units}")
        (
            electronic_energy,
            zero_point_energy,
            enthalpy,
            qrrho_enthalpy,
            entropy_times_temperature,
            qrrho_entropy_times_temperature,
            gibbs_free_energy,
            qrrho_gibbs_free_energy,
        ) = self.convert_energy_units()
        logger.debug(f"Finished converting energies to {self.energy_units}.")

        # Log the results to the output file or console
        structure = os.path.splitext(os.path.basename(self.filename))[0]
        return (
            structure,
            electronic_energy,
            zero_point_energy,
            enthalpy,
            qrrho_enthalpy,
            entropy_times_temperature,
            qrrho_entropy_times_temperature,
            gibbs_free_energy,
            qrrho_gibbs_free_energy,
        )

    def check_frequencies(self):
        """Check for imaginary frequencies and raise an error if found."""
        if self.imaginary_frequencies:
            if self.jobtype == "ts":
                if len(self.imaginary_frequencies) == 1:
                    logger.info(
                        f"Correct Transition State detected: only 1 imaginary "
                        f"frequency\nImaginary frequency excluded for "
                        f"thermochemistry calculation in {self.filename}."
                    )
                else:
                    raise ValueError(
                        f"Invalid number of imaginary frequencies for "
                        f"{self.filename}. Expected 0 for optimization or 1 "
                        f"for TS, but found "
                        f"{len(self.imaginary_frequencies)} for job: "
                        f"{self.jobtype}!"
                    )
            else:
                raise ValueError(
                    f"Invalid geometry optimization for {self.filename}. "
                    f"A valid optimized geometry should not contain "
                    f"imaginary frequencies. Please re-optimize the geometry "
                    f"to locate a true minimum."
                )

    def convert_energy_units(self):
        """Convert all energies to the specified units."""
        electronic_energy = energy_conversion(
            "j/mol", self.energy_units, self.electronic_energy
        )
        zero_point_energy = energy_conversion(
            "j/mol", self.energy_units, self.zero_point_energy
        )
        enthalpy = energy_conversion("j/mol", self.energy_units, self.enthalpy)
        qrrho_enthalpy = (
            energy_conversion("j/mol", self.energy_units, self.qrrho_enthalpy)
            if self.qrrho_enthalpy
            else None
        )
        entropy_times_temperature = energy_conversion(
            "j/mol", self.energy_units, self.entropy_times_temperature
        )
        qrrho_entropy_times_temperature = (
            energy_conversion(
                "j/mol",
                self.energy_units,
                self.qrrho_entropy_times_temperature,
            )
            if self.qrrho_entropy_times_temperature
            else None
        )
        gibbs_free_energy = energy_conversion(
            "j/mol", self.energy_units, self.gibbs_free_energy
        )

        if self.s_freq_cutoff and self.h_freq_cutoff:
            qrrho_gibbs_free_energy = energy_conversion(
                "j/mol", self.energy_units, self.qrrho_gibbs_free_energy
            )
        elif self.s_freq_cutoff and not self.h_freq_cutoff:
            qrrho_gibbs_free_energy = energy_conversion(
                "j/mol", self.energy_units, self.qrrho_gibbs_free_energy_qs
            )
        elif not self.s_freq_cutoff and self.h_freq_cutoff:
            qrrho_gibbs_free_energy = energy_conversion(
                "j/mol", self.energy_units, self.qrrho_gibbs_free_energy_qh
            )
        else:
            qrrho_gibbs_free_energy = None

        return (
            electronic_energy,
            zero_point_energy,
            enthalpy,
            qrrho_enthalpy,
            entropy_times_temperature,
            qrrho_entropy_times_temperature,
            gibbs_free_energy,
            qrrho_gibbs_free_energy,
        )

    def __str__(self):
        """String representation of the thermochemistry results."""
        filename = getattr(self, "filename", "Unknown")
        temperature = getattr(self, "temperature", None)
        concentration = getattr(self, "concentration", None)
        pressure = getattr(self, "pressure", None)
        use_weighted_mass = getattr(self, "use_weighted_mass", False)
        energy_units = getattr(self, "energy_units", "Unknown")

        temperature_str = (
            f"{temperature:.2f} K" if temperature is not None else "N/A"
        )
        concentration_str = (
            f"{concentration:.1f} mol/L"
            if concentration is not None
            else "N/A"
        )
        pressure_str = f"{pressure:.1f} atm" if pressure is not None else "N/A"
        mass_weighted_str = (
            "Most Abundant Masses"
            if not use_weighted_mass
            else "Natural Abundance Weighted Masses"
        )

        return (
            f"Thermochemistry Results for {filename}:\n"
            f"Temperature: {temperature_str}\n"
            f"Concentration: {concentration_str}\n"
            f"Pressure: {pressure_str}\n"
            f"Mass Weighted: {mass_weighted_str}\n"
            f"Energy Unit: {energy_units}\n"
        )

    def log_results_to_file(
        self,
        structure,
        electronic_energy,
        zero_point_energy,
        enthalpy,
        qrrho_enthalpy,
        entropy_times_temperature,
        qrrho_entropy_times_temperature,
        gibbs_free_energy,
        qrrho_gibbs_free_energy,
        outputfile=None,
        overwrite=False,
        write_header=True,
    ):
        """
        Log thermochemistry results to a structured output file.

        This function records computed thermochemical data (energies,
        enthalpies, entropies, and free energies) for a given molecular
        structure. Results are written in a tabular format with headers that
        adapt automatically depending on whether quasi-harmonic (qh)
        corrections are applied for enthalpy and/or entropy.

        Behavior:
            - If the output file does not exist:
                * A detailed header is written, including run conditions
                  (temperature, pressure/concentration, frequency cutoffs,
                  etc.) and appropriate column labels depending on qh
                  corrections.
                * The first row of results is written after the header.
            - If the output file exists:
                * A warning is logged.
                * By default, results are appended to the file and the
                  header is written again (ensuring consistency if conditions
                  differ between runs).
                * If `overwrite=True`, the file is replaced, and both the
                  header and new results are written.

        Parameters
        ----------
        structure : str
            Label or identifier of the molecular structure.
        electronic_energy : float
            The computed electronic energy (in chosen units).
        zero_point_energy : float or None
            Zero-point vibrational energy. If None, frequency data is
            assumed unavailable.
        enthalpy : float or None
            Thermal enthalpy contribution (without qh correction).
        qrrho_enthalpy : float or None
            Thermal enthalpy contribution with qh correction, if applicable.
        entropy_times_temperature : float or None
            Entropy (multiplied by T) without qh correction.
        qrrho_entropy_times_temperature : float or None
            Entropy (multiplied by T) with qh correction, if applicable.
        gibbs_free_energy : float or None
            Gibbs free energy (without qh correction).
        qrrho_gibbs_free_energy : float or None
            Gibbs free energy (with qh correction, if applicable).
        outputfile : str, optional
            Path to the output file. If not provided, defaults to
            `<input_filename>.dat`.
        overwrite : bool, default=False
            If True, existing files are replaced. If False, results are
            appended
            (header is repeated to reflect possible changes in conditions).
        write_header : bool, default=True
            If True, writes the header block before results. Set to False
            to skip header writing (useful when appending multiple times
            without changing conditions).

        Notes
        -----
        - The header block includes metadata such as temperature, pressure
          or concentration, entropy/enthalpy frequency cutoffs, damping
          function exponent, and chosen mass weighting scheme.
        - When all thermochemical quantities are None, a placeholder row
          indicating missing frequency data is written instead of numerical
          results.
        - Column structure automatically adjusts to include or exclude
          qh-corrected values depending on whether entropy and/or enthalpy
          cutoffs were applied.
        """

        # Default output file
        if outputfile is None:
            outputfile = os.path.splitext(self.filename)[0] + ".dat"

        # Check if all thermochemistry values are None
        all_none = all(
            x is None
            for x in [
                zero_point_energy,
                enthalpy,
                qrrho_enthalpy,
                entropy_times_temperature,
                qrrho_entropy_times_temperature,
                gibbs_free_energy,
                qrrho_gibbs_free_energy,
            ]
        )
        no_freq = "{:39} {:13.6f}   {:<69}\n".format(
            structure,
            electronic_energy,
            "--- [NO FREQ INFO] Thermochemistry skipped. ---",
        )

        def build_header():
            """Return appropriate header string depending on qh corrections."""
            used_mass = (
                "Most Abundant Masses"
                if not self.use_weighted_mass
                else "Natural Abundance Weighted Masses"
            )
            header = f"\nTemperature: {self.temperature:.2f} K\n"
            if self.concentration is not None:
                header += f"Concentration: {self.concentration:.1f} mol/L\n"
            else:
                header += f"Pressure: {self.pressure:.1f} atm\n"

            if self.s_freq_cutoff:
                header += (
                    f"Entropy Frequency Cut-off: "
                    f"{(self.s_freq_cutoff / (units._c * 1e2)):.1f} cm^-1\n"
                )
            if self.h_freq_cutoff:
                header += (
                    f"Enthalpy Frequency Cut-off: "
                    f"{(self.h_freq_cutoff / (units._c * 1e2)):.1f} cm^-1\n"
                )
            if self.s_freq_cutoff or self.h_freq_cutoff:
                header += f"Damping Function Exponent: {self.alpha}\n"

            header += f"Mass Weighted: {used_mass}\n"
            header += f"Energy Unit: {self.energy_units}\n\n"

            if self.h_freq_cutoff or self.s_freq_cutoff:
                header += qrrho_header
                header += head_gordon_damping_function_ref
            if self.s_freq_cutoff and self.entropy_method == "grimme":
                header += grimme_quasi_rrho_entropy_ref
            if self.s_freq_cutoff and self.entropy_method == "truhlar":
                header += truhlar_quasi_rrho_entropy_ref
            if self.h_freq_cutoff:
                header += head_gordon_quasi_rrho_enthalpy_ref
            header += "\n"

            # Column headers based on corrections
            if self.h_freq_cutoff and self.s_freq_cutoff:
                header += "{:<39} {:>13} {:>10} {:>13} {:>13} {:>10} {:>10} {:>13} {:>13}\n".format(
                    "Structure",
                    "E",
                    "ZPE",
                    "H",
                    "qh-H",
                    "T.S",
                    "T.qh-S",
                    "G(T)",
                    "qh-G(T)",
                )
                header += "=" * 142 + "\n"
            elif self.s_freq_cutoff:
                header += "{:<39} {:>13} {:>10} {:>13} {:>10} {:>10} {:>13} {:>13}\n".format(
                    "Structure",
                    "E",
                    "ZPE",
                    "H",
                    "T.S",
                    "T.qh-S",
                    "G(T)",
                    "qh-G(T)",
                )
                header += "=" * 128 + "\n"
            elif self.h_freq_cutoff:
                header += "{:<39} {:>13} {:>10} {:>13} {:>13} {:>10} {:>13} {:>13}\n".format(
                    "Structure",
                    "E",
                    "ZPE",
                    "H",
                    "qh-H",
                    "T.S",
                    "G(T)",
                    "qh-G(T)",
                )
                header += "=" * 131 + "\n"
            else:
                header += "{:<39} {:>13} {:>10} {:>13} {:>10} {:>13}\n".format(
                    "Structure", "E", "ZPE", "H", "T.S", "G(T)"
                )
                header += "=" * 103 + "\n"
            return header

        def build_row():
            """Return formatted data row string depending on corrections."""
            if all_none:
                return no_freq

            if self.h_freq_cutoff and self.s_freq_cutoff:
                return "{:39} {:13.6f} {:10.6f} {:13.6f} {:13.6f} {:10.6f} {:10.6f} {:13.6f} {:13.6f}\n".format(
                    structure,
                    electronic_energy,
                    zero_point_energy,
                    enthalpy,
                    qrrho_enthalpy,
                    entropy_times_temperature,
                    qrrho_entropy_times_temperature,
                    gibbs_free_energy,
                    qrrho_gibbs_free_energy,
                )
            elif self.s_freq_cutoff:
                return "{:39} {:13.6f} {:10.6f} {:13.6f} {:10.6f} {:10.6f} {:13.6f} {:13.6f}\n".format(
                    structure,
                    electronic_energy,
                    zero_point_energy,
                    enthalpy,
                    entropy_times_temperature,
                    qrrho_entropy_times_temperature,
                    gibbs_free_energy,
                    qrrho_gibbs_free_energy,
                )
            elif self.h_freq_cutoff:
                return "{:39} {:13.6f} {:10.6f} {:13.6f} {:13.6f} {:10.6f} {:13.6f} {:13.6f}\n".format(
                    structure,
                    electronic_energy,
                    zero_point_energy,
                    enthalpy,
                    qrrho_enthalpy,
                    entropy_times_temperature,
                    gibbs_free_energy,
                    qrrho_gibbs_free_energy,
                )
            else:
                return "{:39} {:13.6f} {:10.6f} {:13.6f} {:10.6f} {:13.6f}\n".format(
                    structure,
                    electronic_energy,
                    zero_point_energy,
                    enthalpy,
                    entropy_times_temperature,
                    gibbs_free_energy,
                )

        # Handle file writing
        if os.path.exists(outputfile):
            logger.warning(f"Output file {outputfile} already exists.")
            if overwrite:
                mode = "w"
                logger.info(f"Overwriting {outputfile}.")
            else:
                mode = "a"
                logger.info(f"Appending to {outputfile}.")
        else:
            mode = "w"

        with open(outputfile, mode) as out:
            if write_header:
                out.write(build_header())
            out.write(build_row())

        logger.info(f"Thermochemistry results saved to {outputfile}")


class BoltzmannAverageThermochemistry(Thermochemistry):
    """Class to compute Boltzmann-averaged
    thermochemical properties from a list of files."""

    def __init__(
        self, files, energy_type="gibbs", degeneracies=None, **kwargs
    ):
        super().__init__(
            filename=files[
                0
            ],  # No single file, we will take molecule from first filename
            **kwargs,
        )
        #: One multiplicity per conformer, in file order.  A pair of
        #: enantiomeric or symmetry-related wells contributes twice and
        #: omitting that is a scientific error rather than an approximation:
        #: counting n-butane's two gauche wells once gives 82% anti where the
        #: correct treatment gives 70%.  Defaults to one each, which is the
        #: previous behaviour, so a caller that does not know its degeneracies
        #: is no worse off than before -- but one that does can now say so.
        self.degeneracies = (
            tuple(float(item) for item in degeneracies)
            if degeneracies is not None
            else None
        )
        """
        Initialize with a list of Gaussian or ORCA output files.

        Parameters
        ----------
        files : list of str
            List of file paths containing thermochemistry data for conformers.
        energy_type : str, optional
            Energy type to use for Boltzmann weighting
            ("electronic" or "gibbs"). Default is "gibbs".
        """
        if not files:
            raise ValueError("List of files cannot be empty.")

        # Check that all files have the same molecular structure
        molecules = [Molecule.from_filepath(f) for f in files]
        if any(mol is None for mol in molecules):
            raise ValueError("Could not parse molecule from one or more files")
        formulae = {mol.empirical_formula for mol in molecules}
        if len(formulae) > 1:
            raise ValueError(
                "All files must contain the same molecular structure"
            )

        self.files = files
        self.energy_type = energy_type.lower()
        if self.energy_type not in ["electronic", "gibbs"]:
            raise ValueError("energy_type must be 'electronic' or 'gibbs'.")

        # Create Thermochemistry instances for each file
        self.thermochemistries = [
            Thermochemistry(filename=f, **kwargs) for f in files
        ]

    def compute_boltzmann_averages(self):
        """Compute Boltzmann-averaged properties."""
        # Check for imaginary frequencies if required
        if self.check_imaginary_frequencies:
            self.check_frequencies()

        self._compute_boltzmann_averages()

        # convert energies to specified units
        (
            electronic_energy,
            zero_point_energy,
            enthalpy,
            qrrho_enthalpy,
            entropy_times_temperature,
            qrrho_entropy_times_temperature,
            gibbs_free_energy,
            qrrho_gibbs_free_energy,
        ) = self.convert_energy_units()
        # Log the results to the output file or console
        structure = (
            os.path.commonprefix(
                [os.path.splitext(os.path.basename(f))[0] for f in self.files]
            )
            + f"_boltzmann_avg_by_{self.energy_type}"
        )

        return (
            structure,
            electronic_energy,
            zero_point_energy,
            enthalpy,
            qrrho_enthalpy,
            entropy_times_temperature,
            qrrho_entropy_times_temperature,
            gibbs_free_energy,
            qrrho_gibbs_free_energy,
        )

    def _compute_boltzmann_averages(self):
        """Compute Boltzmann-averaged thermochemical properties."""
        # Get temperature and units from settings
        temperature = self.temperature

        # Extract energies for Boltzmann weighting
        energies = []
        for thermo in self.thermochemistries:
            if self.energy_type == "electronic":
                energy = thermo.electronic_energy  # in J/mol
            else:  # gibbs
                if self.s_freq_cutoff and self.h_freq_cutoff:
                    energy = thermo.qrrho_gibbs_free_energy
                elif self.s_freq_cutoff and not self.h_freq_cutoff:
                    energy = thermo.qrrho_gibbs_free_energy_qs
                elif self.h_freq_cutoff and not self.s_freq_cutoff:
                    energy = thermo.qrrho_gibbs_free_energy_qh
                else:
                    energy = thermo.gibbs_free_energy
            if energy is None:
                raise ValueError(
                    f"Energy ({self.energy_type}) not available for file {thermo.filename}"
                )
            energies.append(energy)
        energies = np.array(energies)

        # One implementation of this weighting, not two.  This hand-rolled the
        # partition function and silently omitted per-state degeneracies, while
        # the shared routine documents that omission as a scientific error and
        # takes them as an argument.  Energies here are J/mol.
        weights = np.array(
            boltzmann_populations(
                tuple(float(value) / 1000.0 for value in energies),
                temperature=temperature,
                unit="kj/mol",
                degeneracies=self.degeneracies,
            )
        )

        # Compute weighted averages for thermochemical properties
        self._electronic_energy = np.sum(
            [
                t.electronic_energy * w
                for t, w in zip(self.thermochemistries, weights)
            ]
        )

        self._zero_point_energy = np.sum(
            [
                t.zero_point_energy * w
                for t, w in zip(self.thermochemistries, weights)
            ]
        )

        self._qrrho_enthalpy = (
            np.sum(
                [
                    t.qrrho_enthalpy * w
                    for t, w in zip(self.thermochemistries, weights)
                ]
            )
            if self.h_freq_cutoff
            else None
        )

        self._enthalpy = np.sum(
            [t.enthalpy * w for t, w in zip(self.thermochemistries, weights)]
        )

        self._qrrho_entropy = (
            np.sum(
                [
                    t.qrrho_total_entropy * w
                    for t, w in zip(self.thermochemistries, weights)
                ]
            )
            if self.s_freq_cutoff
            else None
        )

        self._entropy = np.sum(
            [
                t.total_entropy * w
                for t, w in zip(self.thermochemistries, weights)
            ]
        )

        self._qrrho_gibbs_free_energy = (
            np.sum(
                [
                    (
                        t.qrrho_gibbs_free_energy
                        if (self.s_freq_cutoff and self.h_freq_cutoff)
                        else (
                            t.qrrho_gibbs_free_energy_qs
                            if (self.s_freq_cutoff and not self.h_freq_cutoff)
                            else (
                                t.qrrho_gibbs_free_energy_qh
                                if (
                                    self.h_freq_cutoff
                                    and not self.s_freq_cutoff
                                )
                                else t.gibbs_free_energy
                            )
                        )
                    )
                    * w
                    for t, w in zip(self.thermochemistries, weights)
                ]
            )
            if not (self.h_freq_cutoff is None and self.s_freq_cutoff is None)
            else None
        )

        self._gibbs_free_energy = np.sum(
            [
                t.gibbs_free_energy * w
                for t, w in zip(self.thermochemistries, weights)
            ]
        )

    @property
    def boltzmann_electronic_energy(self):
        """Boltzmann-averaged electronic energy."""
        return self._electronic_energy

    @property
    def boltzmann_zero_point_energy(self):
        """Boltzmann-averaged zero-point energy."""
        return self._zero_point_energy

    @property
    def boltzmann_qrrho_enthalpy(self):
        """Boltzmann-averaged enthalpy."""
        return self._qrrho_enthalpy

    @property
    def boltzmann_enthalpy(self):
        """Boltzmann-averaged enthalpy."""
        return self._enthalpy

    @property
    def boltzmann_entropy(self):
        """Boltzmann-averaged entropy."""
        return self._entropy

    @property
    def boltzmann_qrrho_entropy(self):
        """Boltzmann-averaged entropy."""
        return self._qrrho_entropy

    @property
    def boltzmann_entropy_times_temperature(self):
        """Boltzmann-averaged entropy."""
        return self._entropy * self.temperature

    @property
    def boltzmann_qrrho_entropy_times_temperature(self):
        """Boltzmann-averaged entropy times temperature."""
        return self._qrrho_entropy * self.temperature

    @property
    def boltzmann_gibbs_free_energy(self):
        """Boltzmann-averaged Gibbs free energy."""
        return self._gibbs_free_energy

    @property
    def boltzmann_qrrho_gibbs_free_energy(self):
        """Boltzmann-averaged Gibbs free energy."""
        return self._qrrho_gibbs_free_energy

    def convert_energy_units(self):
        """Convert all energies to the specified units."""
        boltzmann_electronic_energy = energy_conversion(
            "j/mol", self.energy_units, self.boltzmann_electronic_energy
        )
        boltzmann_zero_point_energy = energy_conversion(
            "j/mol", self.energy_units, self.boltzmann_zero_point_energy
        )
        boltzmann_enthalpy = energy_conversion(
            "j/mol", self.energy_units, self.boltzmann_enthalpy
        )
        boltzmann_qrrho_enthalpy = (
            energy_conversion(
                "j/mol", self.energy_units, self.boltzmann_qrrho_enthalpy
            )
            if self.h_freq_cutoff
            else None
        )
        boltzmann_entropy_times_temperature = energy_conversion(
            "j/mol",
            self.energy_units,
            self.boltzmann_entropy_times_temperature,
        )
        boltzmann_qrrho_entropy_times_temperature = (
            energy_conversion(
                "j/mol",
                self.energy_units,
                self.boltzmann_qrrho_entropy_times_temperature,
            )
            if self.s_freq_cutoff
            else None
        )
        boltzmann_gibbs_free_energy = energy_conversion(
            "j/mol", self.energy_units, self.boltzmann_gibbs_free_energy
        )
        boltzmann_qrrho_gibbs_free_energy = energy_conversion(
            "j/mol", self.energy_units, self.boltzmann_qrrho_gibbs_free_energy
        )

        return (
            boltzmann_electronic_energy,
            boltzmann_zero_point_energy,
            boltzmann_enthalpy,
            boltzmann_qrrho_enthalpy,
            boltzmann_entropy_times_temperature,
            boltzmann_qrrho_entropy_times_temperature,
            boltzmann_gibbs_free_energy,
            boltzmann_qrrho_gibbs_free_energy,
        )

    def __str__(self):
        """String representation of the Boltzmann-averaged thermochemistry."""
        energy_units = self.energy_units
        return (
            f"Boltzmann-Averaged Thermochemistry (using {self.energy_type} energy)\n"
            f"Temperature: {self.temperature:.2f} K\n"
            f"Electronic Energy: {self._electronic_energy:.6f} {energy_units}\n"
            f"Enthalpy: {self._enthalpy:.6f} {energy_units}\n"
            f"Entropy: {self._entropy:.6f} {energy_units}/K\n"
            f"Gibbs Free Energy: {self._gibbs_free_energy:.6f} {energy_units}"
        )
