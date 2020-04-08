"""
Solve Helmholtz equation on the unit disc

Using polar coordinates and numerical method from:

"Efficient spectral-Galerkin methods III: Polar and cylindrical geometries",
J Shen, SIAM J. Sci Comput. 18, 6, 1583-1604

Using shenfun to map coordinates instead of
directly applying r = (t+1)/2, as in the SIAM paper.

"""

import matplotlib.pyplot as plt
import functools
from mpi4py import MPI
from shenfun import *
from shenfun.la import Solver2D, SolverGeneric1NP
import sympy as sp

by_parts = True

# Define polar coordinates using angle along first axis and radius second
theta, r = psi = sp.symbols('x,y', real=True, positive=True)
rv = (r*sp.cos(theta), r*sp.sin(theta))

alpha = 2

# Manufactured solution
ue = (r*(1-r))**2*sp.cos(8*theta)-0.1*(r-1)
f = -ue.diff(r, 2) - (1/r)*ue.diff(r, 1) - (1/r**2)*ue.diff(theta, 2) + alpha*ue

N = 32
F = Basis(N, 'F', dtype='d')
F0 = Basis(1, 'F', dtype='d')
L = Basis(N, 'L', bc='Dirichlet', domain=(0, 1))
L0 = Basis(N, 'L', bc='UpperDirichlet', domain=(0, 1))
T = TensorProductSpace(comm, (F, L), axes=(1, 0), measures=(psi, rv))
T0 = TensorProductSpace(MPI.COMM_SELF, (F0, L0), axes=(1, 0), measures=(psi, rv))

v = TestFunction(T)
u = TrialFunction(T)
v0 = TestFunction(T0)
u0 = TrialFunction(T0)

# Compute the right hand side on the quadrature mesh
fj = Array(T, buffer=f)

# Take scalar product
f_hat = Function(T)
f_hat = inner(v, fj, output_array=f_hat)
if comm.Get_rank() == 0:
    f_hat[0] = 0 # Not using this basis for m=0, so this makes sure u_hat[0] is zero

# For m=0 we solve only a 1D equation. Do the scalar product fo Fourier coefficient 0 by hand (or sympy)
# Since F0 only has one item, it is not sufficient to do a regular inner product.
if comm.Get_rank() == 0:
    f0_hat = Function(T0)
    gt = sp.lambdify(r, sp.integrate(f, (theta, 0, 2*sp.pi))/2/sp.pi)(L0.mesh())
    f0_hat = L0.scalar_product(gt, f0_hat)

# Assemble matrices.
if by_parts:
    mats = inner(grad(v), grad(u))
    mats += [inner(v, alpha*u)]
    # case m=0
    if comm.Get_rank() == 0:
        mats0 = inner(grad(v0), grad(u0))
        mats0 += [inner(v0, alpha*u0)]
else:
    mats = inner(v, -div(grad(u))+alpha*u)
    # case m=0
    if comm.Get_rank() == 0:
        mats0 = inner(v0, -div(grad(u0))+alpha*u0)

# Solve
# case m > 0
u_hat = Function(T)
Sol1 = SolverGeneric1NP(mats)
u_hat = Sol1(f_hat, u_hat)

# case m = 0
u0_hat = Function(T0)
if comm.Get_rank() == 0:
    Sol0 = SolverGeneric1NP(mats0)
    u0_hat = Sol0(f0_hat, u0_hat)
comm.Bcast(u0_hat, root=0)

# Transform back to real space. Broadcast 1D solution
sl = T.local_slice(False)
uj = u_hat.backward() + u0_hat.backward()[:, sl[1]]
ue = Array(T, buffer=ue)
X = T.local_mesh(True)
print('Error =', np.linalg.norm(uj-ue))

# Postprocess
# Refine for a nicer plot. Refine simply pads Functions with zeros, which
# gives more quadrature points. u_hat has NxN quadrature points, refine
# using any higher number.
u_hat2 = u_hat.refine([N*3, N*3])
u0_hat2 = u0_hat.refine([1, N*3])
sl = u_hat2.function_space().local_slice(False)
ur = u_hat2.backward() + u0_hat2.backward()[:, sl[1]]
Y = u_hat2.function_space().local_mesh(True)
thetaj, rj = Y[0], Y[1]

# Wrap periodic plot around since it looks nicer
xx, yy = rj*np.cos(thetaj), rj*np.sin(thetaj)
xp = np.vstack([xx, xx[0]])
yp = np.vstack([yy, yy[0]])
up = np.vstack([ur, ur[0]])

# plot
plt.figure()
plt.contourf(xp, yp, up)
plt.colorbar()
plt.title('Helmholtz - unitdisc')
plt.xticks([])
plt.yticks([])
plt.axis('off')
plt.show()