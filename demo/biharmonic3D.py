r"""
Solve Biharmonic equation in 2D with periodic bcs in one direction
and homogeneous Dirichlet and Neumann in the other

    \nabla^4 u = f,

Use Fourier basis for the periodic direction and Shen's Biharmonic
basis for the non-periodic direction.

"""
from sympy import symbols, cos, sin, exp, lambdify
import numpy as np
import matplotlib.pyplot as plt
from shenfun.fourier.bases import R2CBasis, C2CBasis
from shenfun.chebyshev.bases import ShenBiharmonicBasis
from shenfun.tensorproductspace import TensorProductSpace, Function,\
    BiharmonicOperator, inner_product
from shenfun.la import Biharmonic
from mpi4py import MPI

comm = MPI.COMM_WORLD

# Use sympy to compute a rhs, given an analytical solution
x, y, z = symbols("x,y,z")
u = (sin(4*np.pi*y)*sin(2*x)*cos(3*z))*(1-y**2)
f = u.diff(x, 4) + u.diff(y, 4) + u.diff(z, 4) + 2*u.diff(x, 2, y, 2) + 2*u.diff(x, 2, z, 2) + 2*u.diff(y, 2, z, 2)

# Lambdify for faster evaluation
ul = lambdify((x, y, z), u, 'numpy')
fl = lambdify((x, y, z), f, 'numpy')

# Size of discretization
N = (32, 32, 36)

SD = ShenBiharmonicBasis(N[0])
K1 = C2CBasis(N[1])
K2 = R2CBasis(N[2])
T = TensorProductSpace(comm, (K1, SD, K2))
X = T.local_mesh(True) # With broadcasting=True the shape of X is local_shape, even though the number of datapoints are still the same as in 1D

# Get f on quad points
fj = fl(X[0], X[1], X[2])

# Compute right hand side of Poisson equation
f_hat = Function(T)
f_hat = T.scalar_product(fj, f_hat)

# Get left hand side of Poisson equation
v = T.test_function()
matrices = inner_product(v, BiharmonicOperator(v))

# Create Helmholtz linear algebra solver
S, A, B = matrices['SBBmat'], matrices['ABBmat'], matrices['BBBmat']
H = Biharmonic(S, A, B, S.scale, A.scale, B.scale, T)

# Solve and transform to real space
u = Function(T, False)        # Solution real space
u_hat = Function(T)           # Solution spectral space
u_hat = H(u_hat, f_hat)       # Solve

u = T.backward(u_hat, u)

# Compare with analytical solution
uj = ul(X[0], X[1], X[2])
print(abs(uj-u).max())
#assert np.allclose(uj, u)

plt.figure()
plt.contourf(X[0][:,:,0], X[1][:,:,0], u[:, :, 8])
plt.colorbar()

plt.figure()
plt.contourf(X[0][:,:,0], X[1][:,:,0], uj[:, :, 8])
plt.colorbar()

plt.figure()
plt.contourf(X[0][:,:,0], X[1][:,:,0], u[:, :, 8]-uj[:, :, 8])
plt.colorbar()
plt.title('Error')
#plt.show()


