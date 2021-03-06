""" Implements WENO method used in Dumbser et al, DOI 10.1016/j.cma.2013.09.022
"""
from itertools import product

from numpy import ceil, floor, multiply, prod, zeros
from scipy.linalg import solve

from ader.etc.basis import Basis
from ader.weno.utils import oscillation_indicator, weno_matrices


class WENOSolver():

    def __init__(self, N, NV, NDIM, λc=1e5, λs=1, r=8, ε=1e-14):

        self.N = N
        self.NV = NV
        self.NDIM = NDIM

        self.Λ = [λs, λs, λc, λc]
        self.fN = int(floor((N - 1) / 2))
        self.cN = int(ceil((N - 1) / 2))
        self.r = r
        self.ε = ε

        basis = Basis(N)
        self.W = weno_matrices(N, basis.ψ)
        self.Σ = oscillation_indicator(N, basis.dψ)

    def calculate_coeffs(self, uList):
        """ Calculate coefficients of basis polynomials and weights
        """
        n = len(uList)
        wList = [solve(self.W[i], uList[i], overwrite_b=1) for i in range(n)]
        σList = [((w.T).dot(self.Σ).dot(w)).diagonal() for w in wList]
        oList = [self.Λ[i] / (abs(σList[i]) + self.ε)**self.r for i in range(n)]

        oSum = zeros(self.NV)
        numerator = zeros([self.N, self.NV])
        for i in range(n):
            oSum += oList[i]
            numerator += multiply(wList[i], oList[i])

        return numerator / oSum

    def coeffs(self, ret, uL, uR, uCL, uCR):

        if self.N == 2:
            ret[:] = self.calculate_coeffs([uL, uR])
        elif self.N % 2:
            ret[:] = self.calculate_coeffs([uL, uR, uCL])
        else:
            ret[:] = self.calculate_coeffs([uL, uR, uCL, uCR])

    def stencils(self, strip, ind):
        """ Returns the set of stencils along strip at position ind
        """
        uL = strip[ind - self.N + 1: ind + 1]
        uR = strip[ind: ind + self.N]
        uCL = strip[ind - self.cN: ind + self.fN + 1]
        uCR = strip[ind - self.fN: ind + self.cN + 1]
        return uL, uR, uCL, uCR

    def solve(self, uBC):
        """ Find reconstruction coefficients of uBC to order N
        """
        if self.N == 1:  # No reconstruction necessary
            shape = uBC.shape[:self.NDIM] + (1,) * self.NDIM + (self.NV,)
            return uBC.reshape(shape)

        rec = uBC
        # The reconstruction is built up along each dimension. At each step,
        # rec holds the reconstruction so far, and tmp holds the new
        # reconstruction along dimension d.
        for d in range(self.NDIM):

            # We are reconstructing along dimension d and so we lose N-1 cells
            # in this dimension at each end. We group the remaining dimensions.
            shape = rec.shape
            shape0 = shape[:d]
            shape1 = shape[d + 1: self.NDIM]

            n1 = int(prod(shape0))
            n2 = shape[d] - 2 * (self.N - 1)
            n3 = int(prod(shape1))
            n4 = self.N**d

            tmp = zeros([n1, n2, n3, n4, self.N, self.NV])
            rec_ = rec.reshape(n1, shape[d], n3, n4, self.NV)

            for i, j, k, a in product(range(n1), range(n2), range(n3), range(n4)):
                strip = rec_[i, :, k, a]
                uL, uR, uCL, uCR = self.stencils(strip, j + self.N - 1)
                self.coeffs(tmp[i, j, k, a], uL, uR, uCL, uCR)

            rec = tmp.reshape(shape0 + (n2,) + shape1 +
                              (self.N,) * (d + 1) + (self.NV,))

        return rec
